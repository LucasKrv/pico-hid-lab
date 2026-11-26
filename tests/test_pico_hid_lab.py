"""Testes automatizados para o projeto educacional Pico HID Lab."""

import io
import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import ducky_parser
import simulate

REPO_ROOT = Path(__file__).resolve().parent.parent


class DuckyParserTests(unittest.TestCase):
    def test_parses_valid_script_with_all_core_commands(self):
        script = "\n".join(
            [
                "REM Script de teste",
                "DEFAULT_DELAY 50",
                "DELAY 1000",
                "GUI r",
                "STRING notepad",
                "ENTER",
                "STRINGLN Hello World 123",
                "REPEAT 2",
                "CTRL SHIFT ESC",
                "F5",
            ]
        )
        result = ducky_parser.parse_payload(script)
        self.assertTrue(result.is_valid, msg=result.errors)
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.default_delay_ms, 50)
        self.assertEqual(
            [inst.kind for inst in result.instructions],
            ["DEFAULT_DELAY", "DELAY", "KEY", "STRING", "KEY", "STRINGLN", "REPEAT", "KEY", "KEY"],
        )
        self.assertEqual(result.instructions[2].value, ("GUI", "R"))
        self.assertEqual(result.instructions[7].value, ("CTRL", "SHIFT", "ESCAPE"))

    def test_detects_syntax_errors(self):
        script = "\n".join(
            [
                "REPEAT 2",
                "DELAY abc",
                "STRING",
                "FOOBAR 123",
                "ENTER EXTRA",
                "GUI F99",
                "CTRL ALT SHIFT GUI A B C",
            ]
        )
        result = ducky_parser.parse_payload(script)
        self.assertFalse(result.is_valid)
        codes = [err.code for err in result.errors]
        self.assertIn("REPEAT_WITHOUT_TARGET", codes)
        self.assertIn("INVALID_DELAY", codes)
        self.assertIn("EMPTY_STRING", codes)
        self.assertIn("UNKNOWN_COMMAND", codes)
        self.assertIn("INVALID_KEY_COMBO", codes)
        self.assertIn("UNKNOWN_KEY", codes)
        self.assertIn("TOO_MANY_KEYS", codes)

    def test_rejects_non_ascii_and_warns_on_abnt2_mismatches(self):
        non_ascii = ducky_parser.parse_payload("STRING Olá")
        self.assertFalse(non_ascii.is_valid)
        self.assertEqual(non_ascii.errors[0].code, "NON_ASCII_CHAR")

        abnt2_sensitive = ducky_parser.parse_payload("STRING C:\\teste/path:1;2?")
        self.assertTrue(abnt2_sensitive.is_valid)
        warning_codes = [w.code for w in abnt2_sensitive.warnings]
        self.assertEqual(warning_codes.count("ABNT2_MISMATCH"), 5)

    def test_repository_payload_is_valid_and_abnt2_safe(self):
        payload_file = REPO_ROOT / "payload.dd"
        content = payload_file.read_text(encoding="utf-8")
        result = ducky_parser.parse_payload(content)
        self.assertTrue(result.is_valid, msg=result.errors)
        self.assertEqual(result.warnings, [], msg=result.warnings)
        self.assertGreater(len(result.instructions), 5)


class SimulateCliTests(unittest.TestCase):
    def test_cli_succeeds_in_strict_mode_on_repo_payload(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = simulate.main([str(REPO_ROOT / "payload.dd"), "--strict"])
        self.assertEqual(exit_code, 0)
        output = buf.getvalue()
        self.assertIn("Status           : VALIDO", output)
        self.assertIn("notepad", output)

    def test_cli_json_output_and_strict_warning_exit_code(self):
        with tempfile.NamedTemporaryFile("w", suffix=".dd", encoding="utf-8", delete=False) as tmp:
            tmp.write("STRING http://example.com\n")
            tmp_path = Path(tmp.name)

        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = simulate.main([str(tmp_path), "--strict", "--json"])
            self.assertEqual(exit_code, 2)
            data = json.loads(buf.getvalue())
            self.assertTrue(data["valid"])
            self.assertEqual(len(data["warnings"]), 2)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_cli_returns_1_for_missing_file(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = simulate.main([str(REPO_ROOT / "nao_existe.dd"), "--json"])
        self.assertEqual(exit_code, 1)


class FirmwareCodeTests(unittest.TestCase):
    """Testa code.py usando mocks dos módulos de hardware do CircuitPython."""

    def _build_fake_circuitpython_modules(self, gp0_value):
        recorded = {
            "sent_keys": [],
            "written_text": [],
            "released_all": 0,
            "pin_deinit": 0,
            "led_deinit": 0,
        }

        board_mod = types.ModuleType("board")
        board_mod.GP0 = "GP0"
        board_mod.LED = "LED"

        digitalio_mod = types.ModuleType("digitalio")

        class Direction:
            INPUT = "INPUT"
            OUTPUT = "OUTPUT"

        class Pull:
            UP = "UP"

        class FakeDigitalInOut:
            def __init__(self, pin):
                self.pin = pin
                self.direction = None
                self.pull = None
                self.value = gp0_value if pin == "GP0" else False

            def deinit(self):
                if self.pin == "GP0":
                    recorded["pin_deinit"] += 1
                else:
                    recorded["led_deinit"] += 1

        digitalio_mod.Direction = Direction
        digitalio_mod.Pull = Pull
        digitalio_mod.DigitalInOut = FakeDigitalInOut

        usb_hid_mod = types.ModuleType("usb_hid")
        usb_hid_mod.devices = ["FAKE_KEYBOARD_DEVICE"]

        adafruit_hid_pkg = types.ModuleType("adafruit_hid")
        keyboard_mod = types.ModuleType("adafruit_hid.keyboard")
        layout_mod = types.ModuleType("adafruit_hid.keyboard_layout_us")
        keycode_mod = types.ModuleType("adafruit_hid.keycode")

        class FakeKeycode:
            GUI = "KC_GUI"
            CONTROL = "KC_CTRL"
            ALT = "KC_ALT"
            SHIFT = "KC_SHIFT"
            ENTER = "KC_ENTER"
            TAB = "KC_TAB"
            ESCAPE = "KC_ESC"
            SPACE = "KC_SPACE"
            BACKSPACE = "KC_BS"
            DELETE = "KC_DEL"
            UP_ARROW = "KC_UP"
            DOWN_ARROW = "KC_DOWN"
            LEFT_ARROW = "KC_LEFT"
            RIGHT_ARROW = "KC_RIGHT"
            HOME = "KC_HOME"
            END = "KC_END"
            PAGE_UP = "KC_PGUP"
            PAGE_DOWN = "KC_PGDN"
            CAPS_LOCK = "KC_CAPS"
            INSERT = "KC_INS"
            PRINT_SCREEN = "KC_PRTSC"
            ZERO = "KC_0"
            ONE = "KC_1"
            TWO = "KC_2"
            THREE = "KC_3"
            FOUR = "KC_4"
            FIVE = "KC_5"
            SIX = "KC_6"
            SEVEN = "KC_7"
            EIGHT = "KC_8"
            NINE = "KC_9"

        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            setattr(FakeKeycode, letter, "KC_%s" % letter)
        for num in range(1, 13):
            setattr(FakeKeycode, "F%d" % num, "KC_F%d" % num)

        class FakeKeyboard:
            def __init__(self, devices):
                self.devices = devices

            def send(self, *codes):
                recorded["sent_keys"].append(codes)

            def release_all(self):
                recorded["released_all"] += 1

        class FakeKeyboardLayoutUS:
            def __init__(self, keyboard):
                self.keyboard = keyboard

            def write(self, text):
                recorded["written_text"].append(text)

        keyboard_mod.Keyboard = FakeKeyboard
        layout_mod.KeyboardLayoutUS = FakeKeyboardLayoutUS
        keycode_mod.Keycode = FakeKeycode

        modules = {
            "board": board_mod,
            "digitalio": digitalio_mod,
            "usb_hid": usb_hid_mod,
            "adafruit_hid": adafruit_hid_pkg,
            "adafruit_hid.keyboard": keyboard_mod,
            "adafruit_hid.keyboard_layout_us": layout_mod,
            "adafruit_hid.keycode": keycode_mod,
        }
        return modules, recorded

    def test_safe_mode_gp0_low_blocks_payload_execution(self):
        fake_modules, recorded = self._build_fake_circuitpython_modules(gp0_value=False)
        with mock.patch.dict(sys.modules, fake_modules):
            sys.modules.pop("code", None)
            import code as pico_code

            with mock.patch.object(pico_code.time, "sleep", return_value=None):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    status = pico_code.run_payload(
                        payload_path=str(REPO_ROOT / "payload.dd"),
                        loop_in_safe_mode=False,
                    )
        self.assertEqual(status, "SAFE_MODE")
        self.assertEqual(recorded["sent_keys"], [])
        self.assertEqual(recorded["written_text"], [])
        self.assertEqual(recorded["pin_deinit"], 1)

    def test_lab_mode_gp0_high_executes_payload_and_releases_keys(self):
        fake_modules, recorded = self._build_fake_circuitpython_modules(gp0_value=True)
        with mock.patch.dict(sys.modules, fake_modules):
            sys.modules.pop("code", None)
            import code as pico_code

            with mock.patch.object(pico_code.time, "sleep", return_value=None):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    status = pico_code.run_payload(
                        payload_path=str(REPO_ROOT / "payload.dd"),
                        loop_in_safe_mode=False,
                    )
        self.assertEqual(status, "COMPLETED")
        self.assertIn(("KC_GUI", "KC_R"), recorded["sent_keys"])
        self.assertIn("notepad", recorded["written_text"])
        self.assertGreaterEqual(recorded["released_all"], 1)
        self.assertEqual(recorded["pin_deinit"], 1)


if __name__ == "__main__":
    unittest.main()
