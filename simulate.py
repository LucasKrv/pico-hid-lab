#!/usr/bin/env python3
"""Validador de sintaxe, analisador ABNT2 e simulador desktop do Pico HID Lab.

Permite testar arquivos `payload.dd` no computador ANTES de gravá-los no
Raspberry Pi Pico, verificando:
  - Erros de sintaxe, comandos desconhecidos e limites USB HID
  - Caracteres não ASCII (incompatíveis com KeyboardLayoutUS)
  - Caracteres ASCII que produzem símbolos diferentes em teclados ABNT2 (PT-BR)
  - Linha do tempo simulada e prévia do texto que será digitado
"""

import argparse
import json
import sys
import time
from pathlib import Path

from ducky_parser import parse_payload

# Estimativa conservadora para simulação de duração da digitação via HID
ESTIMATED_MS_PER_CHAR = 15
ESTIMATED_MS_PER_KEY = 40


def format_timestamp(ms):
    total_seconds = ms / 1000.0
    minutes = int(total_seconds // 60)
    seconds = total_seconds - (minutes * 60)
    return "%02d:%06.3f" % (minutes, seconds)


def simulate_instructions(parse_result):
    """Expande instruções (incluindo REPEAT e DEFAULT_DELAY) em eventos simulados."""
    events = []
    typed_buffer = []
    current_ms = 0
    default_delay_ms = 0
    last_executable = None
    total_chars = 0
    total_key_combos = 0

    def emit_step(inst, is_repeat=False):
        nonlocal current_ms, total_chars, total_key_combos

        start_ms = current_ms
        if inst.kind == "DELAY":
            duration_ms = inst.value
            detail = "Aguardar %d ms" % inst.value
        elif inst.kind == "STRING":
            duration_ms = len(inst.value) * ESTIMATED_MS_PER_CHAR
            total_chars += len(inst.value)
            typed_buffer.append(inst.value)
            detail = "Digitar %r" % inst.value
        elif inst.kind == "STRINGLN":
            duration_ms = len(inst.value) * ESTIMATED_MS_PER_CHAR + ESTIMATED_MS_PER_KEY
            total_chars += len(inst.value)
            total_key_combos += 1
            typed_buffer.append(inst.value + "\n")
            detail = "Digitar %r + ENTER" % inst.value
        elif inst.kind == "KEY":
            duration_ms = ESTIMATED_MS_PER_KEY
            total_key_combos += 1
            combo = " + ".join(inst.value)
            if inst.value == ("ENTER",):
                typed_buffer.append("\n")
            elif inst.value == ("SPACE",):
                typed_buffer.append(" ")
            elif inst.value == ("TAB",):
                typed_buffer.append("\t")
            detail = "Pressionar [%s]" % combo
        else:
            duration_ms = 0
            detail = inst.kind

        current_ms += duration_ms
        events.append(
            {
                "line": inst.line_number,
                "timestamp_ms": start_ms,
                "duration_ms": duration_ms,
                "kind": inst.kind,
                "repeat": is_repeat,
                "detail": detail,
            }
        )

        if default_delay_ms > 0 and inst.kind != "DELAY":
            events.append(
                {
                    "line": inst.line_number,
                    "timestamp_ms": current_ms,
                    "duration_ms": default_delay_ms,
                    "kind": "DEFAULT_DELAY_WAIT",
                    "repeat": is_repeat,
                    "detail": "DEFAULT_DELAY (%d ms)" % default_delay_ms,
                }
            )
            current_ms += default_delay_ms

    for inst in parse_result.instructions:
        if inst.kind == "DEFAULT_DELAY":
            default_delay_ms = inst.value
            events.append(
                {
                    "line": inst.line_number,
                    "timestamp_ms": current_ms,
                    "duration_ms": 0,
                    "kind": "DEFAULT_DELAY",
                    "repeat": False,
                    "detail": "Definir DEFAULT_DELAY = %d ms" % inst.value,
                }
            )
            continue

        if inst.kind == "REPEAT":
            if last_executable is not None:
                for _ in range(inst.value):
                    emit_step(last_executable, is_repeat=True)
            continue

        emit_step(inst, is_repeat=False)
        last_executable = inst

    return {
        "events": events,
        "estimated_duration_ms": current_ms,
        "total_chars": total_chars,
        "total_key_combos": total_key_combos,
        "typed_preview": "".join(typed_buffer),
    }


def build_report(payload_path, content, include_abnt2_warnings=True):
    parsed = parse_payload(content)
    warnings = parsed.warnings
    if not include_abnt2_warnings:
        warnings = [w for w in warnings if w.code != "ABNT2_MISMATCH"]

    simulation = simulate_instructions(parsed) if parsed.is_valid else None

    return {
        "file": str(payload_path),
        "valid": parsed.is_valid,
        "instruction_count": len(parsed.instructions),
        "errors": [
            {
                "line": err.line_number,
                "code": err.code,
                "message": err.message,
                "raw_line": err.raw_line,
            }
            for err in parsed.errors
        ],
        "warnings": [
            {
                "line": warn.line_number,
                "code": warn.code,
                "message": warn.message,
                "raw_line": warn.raw_line,
            }
            for warn in warnings
        ],
        "simulation": simulation,
    }


def print_human_report(report, show_simulation=True, realtime=False, speed=1.0):
    print("=" * 72)
    print("Pico HID Lab - Validador e Simulador de Payload")
    print("=" * 72)
    print("Arquivo          : %s" % report["file"])
    print("Status           : %s" % ("VALIDO" if report["valid"] else "INVALIDO"))
    print("Instrucoes       : %d" % report["instruction_count"])
    print("Erros            : %d" % len(report["errors"]))
    print("Avisos           : %d" % len(report["warnings"]))

    if report["simulation"] is not None:
        sim = report["simulation"]
        print(
            "Duracao estimada : %.2f s (%d ms)"
            % (sim["estimated_duration_ms"] / 1000.0, sim["estimated_duration_ms"])
        )
        print(
            "Resumo HID       : %d caracteres, %d teclas/atalhos"
            % (sim["total_chars"], sim["total_key_combos"])
        )

    if report["errors"]:
        print("\n[ERROS ENCONTRADOS]")
        for err in report["errors"]:
            print("  Linha %3d [%s]: %s" % (err["line"], err["code"], err["message"]))
            if err["raw_line"]:
                print("            -> %s" % err["raw_line"])

    if report["warnings"]:
        print("\n[AVISOS]")
        for warn in report["warnings"]:
            line_label = "Linha %3d" % warn["line"] if warn["line"] > 0 else "Geral    "
            print("  %s [%s]: %s" % (line_label, warn["code"], warn["message"]))

    if show_simulation and report["simulation"] is not None:
        sim = report["simulation"]
        print("\n[SIMULACAO PASSO A PASSO]")
        for event in sim["events"]:
            tag = " (REPEAT)" if event["repeat"] else ""
            print(
                "  [%s] L%03d %-18s %s%s"
                % (
                    format_timestamp(event["timestamp_ms"]),
                    event["line"],
                    event["kind"],
                    event["detail"],
                    tag,
                )
            )
            if realtime and event["duration_ms"] > 0:
                time.sleep((event["duration_ms"] / 1000.0) / max(speed, 0.1))

        if sim["typed_preview"]:
            print("\n[PREVIA DO TEXTO DIGITADO (LAYOUT US)]")
            print("-" * 72)
            print(sim["typed_preview"].rstrip("\n"))
            print("-" * 72)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Valida e simula arquivos payload.dd do Pico HID Lab sem enviar teclas reais."
    )
    parser.add_argument(
        "payload",
        nargs="?",
        default="payload.dd",
        help="Caminho para o arquivo de payload (padrao: payload.dd).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Trata avisos (incluindo divergencias ABNT2) como falha (codigo de saida 2).",
    )
    parser.add_argument(
        "--no-abnt2-warn",
        action="store_true",
        help="Suprime avisos sobre diferencas entre KeyboardLayoutUS e ABNT2.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Valida sintaxe e compatibilidade sem imprimir o passo a passo da simulacao.",
    )
    parser.add_argument(
        "--realtime",
        action="store_true",
        help="Aguarda o tempo proporcional de cada DELAY/digitação durante a simulacao.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Fator de velocidade quando --realtime esta ativo (ex.: 2.0 = 2x mais rapido).",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emite o relatorio completo em formato JSON.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    payload_path = Path(args.payload)

    if not payload_path.is_file():
        message = "Arquivo nao encontrado: %s" % payload_path
        if args.as_json:
            print(json.dumps({"file": str(payload_path), "valid": False, "error": message}, indent=2))
        else:
            print("Erro: %s" % message, file=sys.stderr)
        return 1

    content = payload_path.read_text(encoding="utf-8")
    report = build_report(
        payload_path,
        content,
        include_abnt2_warnings=not args.no_abnt2_warn,
    )

    if args.as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_human_report(
            report,
            show_simulation=not args.validate_only,
            realtime=args.realtime,
            speed=args.speed,
        )

    if not report["valid"]:
        return 1
    if args.strict and report["warnings"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
