"""Parser compartilhado para scripts educacionais do Pico HID Lab.

Compatível tanto com CircuitPython (Raspberry Pi Pico) quanto com Python 3
(usado pelo validador/simulador `simulate.py`), sem dependências externas.
"""

MAX_SIMULTANEOUS_KEYS = 6
MAX_RECOMMENDED_DELAY_MS = 30000

MODIFIER_ALIASES = {
    "GUI": "GUI",
    "WINDOWS": "GUI",
    "SUPER": "GUI",
    "META": "GUI",
    "COMMAND": "GUI",
    "CTRL": "CTRL",
    "CONTROL": "CTRL",
    "ALT": "ALT",
    "SHIFT": "SHIFT",
}

SPECIAL_KEY_ALIASES = {
    "ENTER": "ENTER",
    "RETURN": "ENTER",
    "TAB": "TAB",
    "ESC": "ESCAPE",
    "ESCAPE": "ESCAPE",
    "SPACE": "SPACE",
    "BACKSPACE": "BACKSPACE",
    "DEL": "DELETE",
    "DELETE": "DELETE",
    "UP": "UP",
    "UPARROW": "UP",
    "DOWN": "DOWN",
    "DOWNARROW": "DOWN",
    "LEFT": "LEFT",
    "LEFTARROW": "LEFT",
    "RIGHT": "RIGHT",
    "RIGHTARROW": "RIGHT",
    "HOME": "HOME",
    "END": "END",
    "PAGEUP": "PAGEUP",
    "PAGEDOWN": "PAGEDOWN",
    "CAPSLOCK": "CAPSLOCK",
    "INSERT": "INSERT",
    "PRINTSCREEN": "PRINTSCREEN",
    "F1": "F1",
    "F2": "F2",
    "F3": "F3",
    "F4": "F4",
    "F5": "F5",
    "F6": "F6",
    "F7": "F7",
    "F8": "F8",
    "F9": "F9",
    "F10": "F10",
    "F11": "F11",
    "F12": "F12",
}

SINGLE_KEY_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

# Caracteres ASCII imprimíveis cujos scancodes do KeyboardLayoutUS produzem
# outro símbolo quando interpretados por um sistema operacional em ABNT2 (PT-BR).
US_TO_ABNT2_DIFF = {
    ";": "ç",
    ":": "Ç",
    "/": ";",
    "?": ":",
    "'": "~ (tecla morta)",
    '"': "^ (tecla morta)",
    "`": "'",
    "~": '"',
    "[": "´ (acento agudo - tecla morta)",
    "{": "` (acento grave - tecla morta)",
    "]": "[",
    "}": "{",
    "\\": "]",
    "|": "}",
    "^": "¨ (trema - tecla morta)",
}


class Instruction:
    """Representa uma instrução validada de um arquivo payload.dd."""

    def __init__(self, line_number, kind, value, raw_line):
        self.line_number = line_number
        self.kind = kind
        self.value = value
        self.raw_line = raw_line

    def __repr__(self):
        return "Instruction(line=%d, kind=%r, value=%r)" % (
            self.line_number,
            self.kind,
            self.value,
        )


class ParseIssue:
    """Representa um erro de sintaxe ou aviso encontrado durante o parsing."""

    def __init__(self, line_number, severity, code, message, raw_line=""):
        self.line_number = line_number
        self.severity = severity
        self.code = code
        self.message = message
        self.raw_line = raw_line

    def __repr__(self):
        return "ParseIssue(line=%d, severity=%r, code=%r, message=%r)" % (
            self.line_number,
            self.severity,
            self.code,
            self.message,
        )


class ParseResult:
    """Resultado completo da análise de um arquivo payload.dd."""

    def __init__(self, instructions, errors, warnings, default_delay_ms=0):
        self.instructions = instructions
        self.errors = errors
        self.warnings = warnings
        self.default_delay_ms = default_delay_ms

    @property
    def is_valid(self):
        return len(self.errors) == 0


def _split_command_and_arg(line):
    """Separa o comando inicial do restante da linha preservando espaços do argumento."""
    stripped_left = line.lstrip(" \t")
    for idx, ch in enumerate(stripped_left):
        if ch in (" ", "\t"):
            cmd = stripped_left[:idx]
            arg = stripped_left[idx + 1 :]
            return cmd, arg
    return stripped_left, ""


def _parse_non_negative_int(raw_value):
    text = raw_value.strip()
    if not text:
        return None
    for ch in text:
        if ch < "0" or ch > "9":
            return None
    return int(text)


def _resolve_key_token(token):
    upper = token.upper()
    if upper in MODIFIER_ALIASES:
        return MODIFIER_ALIASES[upper]
    if upper in SPECIAL_KEY_ALIASES:
        return SPECIAL_KEY_ALIASES[upper]
    if len(upper) == 1 and upper in SINGLE_KEY_CHARS:
        return upper
    return None


def _check_string_characters(text, line_number, raw_line, errors, warnings):
    reported_abnt2 = {}
    for ch in text:
        code = ord(ch)
        if code < 32 or code > 126:
            errors.append(
                ParseIssue(
                    line_number,
                    "error",
                    "NON_ASCII_CHAR",
                    "Caractere %r (U+%04X) não é suportado por KeyboardLayoutUS; use apenas ASCII imprimível."
                    % (ch, code),
                    raw_line,
                )
            )
            continue

        if ch in US_TO_ABNT2_DIFF and ch not in reported_abnt2:
            reported_abnt2[ch] = True
            warnings.append(
                ParseIssue(
                    line_number,
                    "warning",
                    "ABNT2_MISMATCH",
                    "Caractere %r difere entre KeyboardLayoutUS e ABNT2 (no ABNT2 será digitado como %s)."
                    % (ch, US_TO_ABNT2_DIFF[ch]),
                    raw_line,
                )
            )


def parse_payload(content):
    """Analisa o conteúdo textual de um payload.dd e retorna um ParseResult."""
    instructions = []
    errors = []
    warnings = []
    default_delay_ms = 0
    last_repeatable = None

    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")

    for index, raw_line in enumerate(lines):
        line_number = index + 1
        stripped = raw_line.strip()

        if not stripped:
            continue

        cmd_raw, arg_raw = _split_command_and_arg(raw_line)
        cmd = cmd_raw.upper()

        if cmd == "REM":
            continue

        if cmd in ("DEFAULT_DELAY", "DEFAULTDELAY"):
            delay_val = _parse_non_negative_int(arg_raw)
            if delay_val is None:
                errors.append(
                    ParseIssue(
                        line_number,
                        "error",
                        "INVALID_DEFAULT_DELAY",
                        "DEFAULT_DELAY requer um inteiro não negativo em milissegundos.",
                        raw_line,
                    )
                )
                continue
            if delay_val > MAX_RECOMMENDED_DELAY_MS:
                warnings.append(
                    ParseIssue(
                        line_number,
                        "warning",
                        "LARGE_DELAY",
                        "DEFAULT_DELAY de %d ms é muito alto para uma demonstração." % delay_val,
                        raw_line,
                    )
                )
            default_delay_ms = delay_val
            instructions.append(Instruction(line_number, "DEFAULT_DELAY", delay_val, raw_line))
            continue

        if cmd == "DELAY":
            delay_val = _parse_non_negative_int(arg_raw)
            if delay_val is None:
                errors.append(
                    ParseIssue(
                        line_number,
                        "error",
                        "INVALID_DELAY",
                        "DELAY requer um inteiro não negativo em milissegundos.",
                        raw_line,
                    )
                )
                continue
            if delay_val > MAX_RECOMMENDED_DELAY_MS:
                warnings.append(
                    ParseIssue(
                        line_number,
                        "warning",
                        "LARGE_DELAY",
                        "DELAY de %d ms excede o limite recomendado (%d ms)."
                        % (delay_val, MAX_RECOMMENDED_DELAY_MS),
                        raw_line,
                    )
                )
            inst = Instruction(line_number, "DELAY", delay_val, raw_line)
            instructions.append(inst)
            last_repeatable = inst
            continue

        if cmd in ("STRING", "STRINGLN"):
            if not arg_raw:
                errors.append(
                    ParseIssue(
                        line_number,
                        "error",
                        "EMPTY_STRING",
                        "%s requer texto após o comando." % cmd,
                        raw_line,
                    )
                )
                continue
            _check_string_characters(arg_raw, line_number, raw_line, errors, warnings)
            inst = Instruction(line_number, cmd, arg_raw, raw_line)
            instructions.append(inst)
            last_repeatable = inst
            continue

        if cmd == "REPEAT":
            count = _parse_non_negative_int(arg_raw)
            if count is None or count < 1:
                errors.append(
                    ParseIssue(
                        line_number,
                        "error",
                        "INVALID_REPEAT",
                        "REPEAT requer um inteiro positivo (>= 1).",
                        raw_line,
                    )
                )
                continue
            if last_repeatable is None:
                errors.append(
                    ParseIssue(
                        line_number,
                        "error",
                        "REPEAT_WITHOUT_TARGET",
                        "REPEAT não possui uma instrução anterior executável para repetir.",
                        raw_line,
                    )
                )
                continue
            instructions.append(Instruction(line_number, "REPEAT", count, raw_line))
            continue

        # Comandos de tecla simples ou combinações com modificadores (ex.: ENTER, GUI r, CTRL SHIFT ESC)
        if cmd in MODIFIER_ALIASES or cmd in SPECIAL_KEY_ALIASES:
            tokens = stripped.split()
            if cmd in SPECIAL_KEY_ALIASES and len(tokens) > 1:
                errors.append(
                    ParseIssue(
                        line_number,
                        "error",
                        "INVALID_KEY_COMBO",
                        "Tecla especial %r não aceita argumentos extras (%r)."
                        % (SPECIAL_KEY_ALIASES[cmd], " ".join(tokens[1:])),
                        raw_line,
                    )
                )
                continue

            if len(tokens) > MAX_SIMULTANEOUS_KEYS:
                errors.append(
                    ParseIssue(
                        line_number,
                        "error",
                        "TOO_MANY_KEYS",
                        "Combinação excede o limite de %d teclas simultâneas do USB HID."
                        % MAX_SIMULTANEOUS_KEYS,
                        raw_line,
                    )
                )
                continue

            resolved_keys = []
            invalid_token = None
            for token in tokens:
                canonical = _resolve_key_token(token)
                if canonical is None:
                    invalid_token = token
                    break
                resolved_keys.append(canonical)

            if invalid_token is not None:
                errors.append(
                    ParseIssue(
                        line_number,
                        "error",
                        "UNKNOWN_KEY",
                        "Tecla desconhecida na combinação: %r." % invalid_token,
                        raw_line,
                    )
                )
                continue

            inst = Instruction(line_number, "KEY", tuple(resolved_keys), raw_line)
            instructions.append(inst)
            last_repeatable = inst
            continue

        errors.append(
            ParseIssue(
                line_number,
                "error",
                "UNKNOWN_COMMAND",
                "Comando desconhecido: %r." % cmd_raw,
                raw_line,
            )
        )

    if not instructions and not errors:
        warnings.append(
            ParseIssue(
                0,
                "warning",
                "EMPTY_PAYLOAD",
                "O arquivo de payload não contém instruções executáveis.",
                "",
            )
        )

    return ParseResult(instructions, errors, warnings, default_delay_ms)
