"""Pico HID Lab - Configuração de inicialização do CircuitPython (boot.py).

Executado automaticamente na energização do Raspberry Pi Pico antes de `code.py`.

Modo Seguro (GP0 conectado ao GND):
- Pino físico 1 (GP0) + Pino físico 3 (GND) com jumper instalado -> GP0 em nível LOW.
- A interface USB HID é desabilitada já no boot, garantindo que o dispositivo
  não se apresente como teclado enquanto você edita `code.py` ou `payload.dd`.
- A unidade `CIRCUITPY` e o console serial (`usb_cdc`) permanecem SEMPRE ativos
  neste laboratório educacional para transparência e facilidade de depuração.
"""

import time
import board
import digitalio
import storage
import usb_cdc
import usb_hid


def _is_safe_mode_pin_low():
    pin = digitalio.DigitalInOut(board.GP0)
    pin.direction = digitalio.Direction.INPUT
    pin.pull = digitalio.Pull.UP
    try:
        time.sleep(0.01)
        return not pin.value
    finally:
        pin.deinit()


# Mantém a unidade CIRCUITPY e o console serial sempre acessíveis no laboratório.
storage.enable_usb_drive()
usb_cdc.enable(console=True, data=False)

if _is_safe_mode_pin_low():
    # Modo Seguro: impede até a enumeração do dispositivo USB HID no host.
    usb_hid.disable()
    print("[boot.py] MODO SEGURO ATIVO (GP0-GND): USB HID desabilitado; CIRCUITPY livre para edicao.")
else:
    # Modo Laboratório: habilita apenas o perfil de teclado HID (sem mouse/consumer).
    usb_hid.enable((usb_hid.Device.KEYBOARD,))
    print("[boot.py] MODO LAB (GP0 aberto): USB HID Keyboard habilitado.")
