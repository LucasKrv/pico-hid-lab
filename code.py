"""Pico HID Lab - Firmware educacional em CircuitPython + adafruit_hid.

Destinado exclusivamente a laboratórios controlados e estudos de segurança
ofensiva/defensiva sobre emulação de teclado USB HID (Raspberry Pi Pico).

Comportamento do Modo Seguro (GP0-GND):
- Com jumper ligando GP0 (pino físico 1) ao GND (pino físico 3):
  o script entra em Modo Seguro, pisca o LED lentamente e NÃO executa `payload.dd`.
- Sem jumper (GP0 aberto, mantido em HIGH pelo pull-up interno):
  aguarda breve aviso visual no LED, valida `payload.dd` e executa as teclas.
- Caso o jumper GP0-GND seja conectado durante a execução, o envio de teclas
  é interrompido imediatamente e todas as teclas pressionadas são liberadas.
"""

import time
import board
import digitalio

from ducky_parser import parse_payload

PAYLOAD_PATH = "payload.dd"
SAFE_POLL_INTERVAL_SEC = 0.05
STARTUP_BLINK_COUNT = 3
STARTUP_BLINK_SEC = 0.2


def _create_safe_mode_pin():
    pin = digitalio.DigitalInOut(board.GP0)
    pin.direction = digitalio.Direction.INPUT
    pin.pull = digitalio.Pull.UP
    time.sleep(0.01)
    return pin


def _create_led():
    if not hasattr(board, "LED"):
        return None
    led = digitalio.DigitalInOut(board.LED)
    led.direction = digitalio.Direction.OUTPUT
    led.value = False
    return led


def _set_led(led, state):
    if led is not None:
        led.value = bool(state)


def _blink_led(led, count, interval_sec):
    for _ in range(count):
        _set_led(led, True)
        time.sleep(interval_sec)
        _set_led(led, False)
        time.sleep(interval_sec)


def is_safe_mode_active(safe_pin):
    """Retorna True quando GP0 está conectado ao GND (nível lógico LOW)."""
    return not safe_pin.value


def _sleep_with_safe_check(duration_sec, safe_pin):
    """Dorme em pequenos intervalos, retornando False se GP0-GND for acionado."""
    remaining = duration_sec
    while remaining > 0:
        if is_safe_mode_active(safe_pin):
            return False
        step = SAFE_POLL_INTERVAL_SEC if remaining > SAFE_POLL_INTERVAL_SEC else remaining
        time.sleep(step)
        remaining -= step
    return not is_safe_mode_active(safe_pin)


def _build_keycode_map(keycode_cls):
    """Mapeia nomes canônicos do ducky_parser para constantes adafruit_hid.Keycode."""
    mapping = {
        "GUI": keycode_cls.GUI,
        "CTRL": keycode_cls.CONTROL,
        "ALT": keycode_cls.ALT,
        "SHIFT": keycode_cls.SHIFT,
        "ENTER": keycode_cls.ENTER,
        "TAB": keycode_cls.TAB,
        "ESCAPE": keycode_cls.ESCAPE,
        "SPACE": keycode_cls.SPACE,
        "BACKSPACE": keycode_cls.BACKSPACE,
        "DELETE": keycode_cls.DELETE,
        "UP": keycode_cls.UP_ARROW,
        "DOWN": keycode_cls.DOWN_ARROW,
        "LEFT": keycode_cls.LEFT_ARROW,
        "RIGHT": keycode_cls.RIGHT_ARROW,
        "HOME": keycode_cls.HOME,
        "END": keycode_cls.END,
        "PAGEUP": keycode_cls.PAGE_UP,
        "PAGEDOWN": keycode_cls.PAGE_DOWN,
        "CAPSLOCK": keycode_cls.CAPS_LOCK,
        "INSERT": keycode_cls.INSERT,
        "PRINTSCREEN": keycode_cls.PRINT_SCREEN,
        "0": keycode_cls.ZERO,
        "1": keycode_cls.ONE,
        "2": keycode_cls.TWO,
        "3": keycode_cls.THREE,
        "4": keycode_cls.FOUR,
        "5": keycode_cls.FIVE,
        "6": keycode_cls.SIX,
        "7": keycode_cls.SEVEN,
        "8": keycode_cls.EIGHT,
        "9": keycode_cls.NINE,
    }

    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        mapping[letter] = getattr(keycode_cls, letter)

    for num in range(1, 13):
        fn_name = "F%d" % num
        mapping[fn_name] = getattr(keycode_cls, fn_name)

    return mapping


def _load_payload_text(path):
    with open(path, "r") as handle:
        return handle.read()


def _execute_instruction(inst, keyboard, layout, keycode_map, safe_pin):
    if is_safe_mode_active(safe_pin):
        return False

    if inst.kind == "DELAY":
        return _sleep_with_safe_check(inst.value / 1000.0, safe_pin)

    if inst.kind == "STRING":
        layout.write(inst.value)
        return True

    if inst.kind == "STRINGLN":
        layout.write(inst.value)
        keyboard.send(keycode_map["ENTER"])
        return True

    if inst.kind == "KEY":
        codes = [keycode_map[name] for name in inst.value]
        keyboard.send(*codes)
        return True

    return True


def run_payload(payload_path=PAYLOAD_PATH, loop_in_safe_mode=True):
    """Fluxo principal do Pico HID Lab."""
    safe_pin = _create_safe_mode_pin()
    led = _create_led()
    keyboard = None

    try:
        if is_safe_mode_active(safe_pin):
            print("[Pico HID Lab] MODO SEGURO ATIVO (GP0 conectado ao GND).")
            print("[Pico HID Lab] payload.dd NAO sera executado. Edite os arquivos em CIRCUITPY com seguranca.")
            if loop_in_safe_mode:
                while is_safe_mode_active(safe_pin):
                    _set_led(led, True)
                    time.sleep(0.25)
                    _set_led(led, False)
                    time.sleep(1.25)
            return "SAFE_MODE"

        try:
            payload_text = _load_payload_text(payload_path)
        except OSError as exc:
            print("[Pico HID Lab] Erro ao abrir %s: %s" % (payload_path, exc))
            _blink_led(led, 5, 0.1)
            return "FILE_ERROR"

        parsed = parse_payload(payload_text)
        for warning in parsed.warnings:
            print("[AVISO L%d] %s" % (warning.line_number, warning.message))

        if not parsed.is_valid:
            print("[Pico HID Lab] Erros de sintaxe em %s; execucao cancelada:" % payload_path)
            for err in parsed.errors:
                print("  [ERRO L%d] %s" % (err.line_number, err.message))
            _blink_led(led, 5, 0.1)
            return "PARSE_ERROR"

        # Importa módulos HID somente após confirmar que não estamos em Modo Seguro.
        import usb_hid
        from adafruit_hid.keyboard import Keyboard
        from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
        from adafruit_hid.keycode import Keycode

        if not usb_hid.devices:
            print("[Pico HID Lab] Nenhum dispositivo USB HID disponivel (verifique boot.py / GP0).")
            _blink_led(led, 4, 0.15)
            return "NO_HID"

        keyboard = Keyboard(usb_hid.devices)
        layout = KeyboardLayoutUS(keyboard)
        keycode_map = _build_keycode_map(Keycode)

        print("[Pico HID Lab] Aviso visual antes da execucao de %s..." % payload_path)
        for _ in range(STARTUP_BLINK_COUNT):
            _set_led(led, True)
            if not _sleep_with_safe_check(STARTUP_BLINK_SEC, safe_pin):
                print("[Pico HID Lab] Execucao abortada pelo jumper GP0-GND.")
                return "ABORTED"
            _set_led(led, False)
            if not _sleep_with_safe_check(STARTUP_BLINK_SEC, safe_pin):
                print("[Pico HID Lab] Execucao abortada pelo jumper GP0-GND.")
                return "ABORTED"

        print("[Pico HID Lab] Executando %d instrucoes..." % len(parsed.instructions))
        _set_led(led, True)

        default_delay_sec = 0.0
        last_executable = None

        for inst in parsed.instructions:
            if is_safe_mode_active(safe_pin):
                print("[Pico HID Lab] Execucao abortada pelo jumper GP0-GND.")
                return "ABORTED"

            if inst.kind == "DEFAULT_DELAY":
                default_delay_sec = inst.value / 1000.0
                continue

            if inst.kind == "REPEAT":
                if last_executable is None:
                    continue
                for _ in range(inst.value):
                    ok = _execute_instruction(
                        last_executable, keyboard, layout, keycode_map, safe_pin
                    )
                    if not ok:
                        print("[Pico HID Lab] Execucao abortada pelo jumper GP0-GND.")
                        return "ABORTED"
                    if default_delay_sec > 0 and last_executable.kind != "DELAY":
                        if not _sleep_with_safe_check(default_delay_sec, safe_pin):
                            print("[Pico HID Lab] Execucao abortada pelo jumper GP0-GND.")
                            return "ABORTED"
                continue

            ok = _execute_instruction(inst, keyboard, layout, keycode_map, safe_pin)
            if not ok:
                print("[Pico HID Lab] Execucao abortada pelo jumper GP0-GND.")
                return "ABORTED"

            last_executable = inst
            if default_delay_sec > 0 and inst.kind != "DELAY":
                if not _sleep_with_safe_check(default_delay_sec, safe_pin):
                    print("[Pico HID Lab] Execucao abortada pelo jumper GP0-GND.")
                    return "ABORTED"

        _set_led(led, False)
        _blink_led(led, 2, 0.15)
        print("[Pico HID Lab] Execucao concluida com sucesso.")
        return "COMPLETED"
    finally:
        if keyboard is not None:
            try:
                keyboard.release_all()
            except Exception:
                pass
        _set_led(led, False)
        if led is not None:
            led.deinit()
        safe_pin.deinit()


if __name__ == "__main__":
    run_payload()
