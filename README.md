# Pico HID Lab

Laboratório educacional para **Raspberry Pi Pico** com **CircuitPython** e **`adafruit_hid`**, criado para demonstrar de forma controlada como funciona a emulação de teclado USB HID (Human Interface Device), as diferenças de mapeamento entre layouts **US** e **ABNT2 (PT-BR)**, e quais controles defensivos protegem estações de trabalho contra dispositivos HID não autorizados.

> **Uso responsável:** utilize este projeto apenas em computadores e ambientes próprios ou expressamente autorizados para fins de estudo, testes de automação e educação em segurança defensiva.

---

## Estrutura do Projeto

| Arquivo | Função |
| --- | --- |
| [`boot.py`](boot.py) | Executado na inicialização do CircuitPython. Verifica o jumper **GP0–GND** e desabilita a interface `usb_hid` no Modo Seguro, mantendo `CIRCUITPY` sempre acessível para edição. |
| [`code.py`](code.py) | Firmware principal do Raspberry Pi Pico (`adafruit_hid`). Valida `GP0–GND`, lê `payload.dd`, executa os comandos de teclado com feedback no LED onboard e oferece parada imediata via jumper. |
| [`ducky_parser.py`](ducky_parser.py) | Parser puro em Python, compartilhado entre o CircuitPython no Pico e o Python 3 no desktop. |
| [`payload.dd`](payload.dd) | Script benigno de demonstração que abre o **Bloco de Notas (Notepad)** no Windows e digita uma mensagem educativa compatível com ABNT2. |
| [`simulate.py`](simulate.py) | Validador de sintaxe, verificador de compatibilidade ABNT2 e simulador passo a passo para testar scripts `.dd` no computador antes de copiá-los para o Pico. |
| [`tests/test_pico_hid_lab.py`](tests/test_pico_hid_lab.py) | Suíte de testes automatizados (`unittest`) cobrindo o parser, `simulate.py`, `payload.dd` e o fluxo do Modo Seguro em `code.py`. |

---

## Requisitos

### Hardware
- **Raspberry Pi Pico** (RP2040) ou **Pico W**
- Cabo micro-USB com suporte a **dados** (cabos apenas de energia não montam `CIRCUITPY`)
- 1 jumper fêmea-fêmea (ou fio Dupont) para o **Modo Seguro (`GP0`–`GND`)**

### Software (no Raspberry Pi Pico)
- **CircuitPython 8.x ou 9.x** para Raspberry Pi Pico (`circuitpython.org`)
- Pasta `adafruit_hid/` extraída do **Adafruit CircuitPython Library Bundle** (na mesma versão major do CircuitPython instalado)

### Software (no computador para validação local)
- **Python 3.8+** (usa apenas a biblioteca padrão, sem dependências extras)

---

## Pinagem e Modo Seguro (`GP0`–`GND`)

O pino `GP0` é configurado com resistor interno de *pull-up* (`Pull.UP`):

```text
          +--------- USB ---------+
   GP0  1 | o                   o | 40  VBUS
   GP1  2 | o                   o | 39  VSYS
   GND  3 | o                   o | 38  GND
          +-----------------------+

  Jumper entre Pino 1 (GP0) e Pino 3 (GND)  -->  MODO SEGURO ATIVO
  Pino 1 (GP0) desconectado (aberto)        -->  MODO LABORATÓRIO
```

| Estado do Jumper `GP0`–`GND` | Nível Lógico em `GP0` | Comportamento | LED Onboard |
| --- | --- | --- | --- |
| **Conectado** (Modo Seguro) | `LOW` (`False`) | `boot.py` desabilita `usb_hid`; `code.py` não envia teclas e mantém `CIRCUITPY` pronto para edição. | Pisca lento (0,25 s aceso / 1,25 s apagado) |
| **Desconectado** (Modo Lab) | `HIGH` (`True`) | Aviso visual inicial, leitura/validação de `payload.dd` e execução das instruções HID. | 3 piscadas de aviso -> aceso durante execução -> 2 piscadas ao concluir |
| **Conectado durante execução** | `HIGH` -> `LOW` | Interrupção imediata da execução e chamada de `keyboard.release_all()`. | Apaga imediatamente |
| **Erro de leitura/sintaxe** | `HIGH` (`True`) | Execução cancelada antes de enviar qualquer tecla; detalhes exibidos no console serial. | 5 piscadas rápidas |

---

## Instalação no Raspberry Pi Pico

1. **Instale o CircuitPython:**
   - Segure o botão **BOOTSEL** no Pico enquanto conecta o cabo USB.
   - Copie o arquivo `.uf2` do CircuitPython para a unidade `RPI-RP2`.
   - O Pico reiniciará e aparecerá como uma unidade chamada **`CIRCUITPY`**.
2. **Ative o Modo Seguro antes de copiar os scripts:**
   - Conecte o jumper entre **GP0 (pino 1)** e **GND (pino 3)** para evitar qualquer envio de teclas enquanto prepara os arquivos.
3. **Instale a biblioteca `adafruit_hid`:**
   - Baixe o *Adafruit CircuitPython Bundle* correspondente à sua versão do CircuitPython.
   - Copie a pasta `lib/adafruit_hid` do pacote para `CIRCUITPY/lib/adafruit_hid`.
4. **Copie os arquivos do projeto para a raiz de `CIRCUITPY`:**
   - `boot.py`
   - `code.py`
   - `ducky_parser.py`
   - `payload.dd`
5. **Teste controlado:**
   - Valide `payload.dd` primeiro no computador com `python3 simulate.py --strict`.
   - Remova o Pico com segurança, retire o jumper `GP0`–`GND` e reconecte em uma máquina Windows de laboratório (com sessão desbloqueada) para observar a abertura do Bloco de Notas.

---

## Sintaxe Suportada no `payload.dd`

- `REM <comentario>` — comentário ignorado na execução.
- `DELAY <ms>` — aguarda o tempo especificado em milissegundos.
- `DEFAULT_DELAY <ms>` / `DEFAULTDELAY <ms>` — pausa padrão após cada comando executável.
- `STRING <texto>` — digita texto ASCII imprimível.
- `STRINGLN <texto>` — digita texto ASCII imprimível seguido de `ENTER`.
- `REPEAT <n>` — repete a instrução executável anterior `n` vezes.
- Teclas especiais: `ENTER`, `TAB`, `ESC`/`ESCAPE`, `SPACE`, `BACKSPACE`, `DEL`/`DELETE`, `UP`, `DOWN`, `LEFT`, `RIGHT`, `HOME`, `END`, `PAGEUP`, `PAGEDOWN`, `CAPSLOCK`, `INSERT`, `PRINTSCREEN`, `F1`–`F12`.
- Combinações com modificadores (até 6 teclas simultâneas): `GUI`/`WINDOWS`, `CTRL`/`CONTROL`, `ALT`, `SHIFT` combinados com letras, dígitos ou teclas especiais (ex.: `GUI r`, `CTRL s`, `ALT F4`).

---

## Validador e Simulador (`simulate.py`)

Use `simulate.py` para verificar sintaxe, duração estimada, prévia de texto e compatibilidade com ABNT2 sem precisar conectar o Pico:

```bash
# Validação + simulação passo a passo do payload.dd padrão
python3 simulate.py

# Modo estrito: falha (código de saída 2) se houver qualquer aviso, incluindo divergências ABNT2
python3 simulate.py payload.dd --strict

# Apenas validação, sem listar todos os eventos
python3 simulate.py payload.dd --validate-only

# Saída estruturada em JSON (útil para automação/CI)
python3 simulate.py payload.dd --json

# Simulação respeitando o tempo dos delays (2x mais rápido)
python3 simulate.py payload.dd --realtime --speed 2.0
```

Para executar a suíte de testes unitários do repositório:

```bash
python3 -m unittest discover -s tests -v
```

---

## Notas sobre Teclado ABNT2 (PT-BR) vs `KeyboardLayoutUS`

Um teclado USB HID **não envia caracteres Unicode**; ele envia **códigos de tecla física** (*HID Usage IDs / scancodes*). Quem traduz cada código para um caractere é o layout configurado no sistema operacional do computador host.

A classe padrão `KeyboardLayoutUS` da `adafruit_hid` converte texto ASCII em scancodes de um teclado **ANSI US**. Quando o host está configurado em **Português (Brasil ABNT2)**, diversos sinais de pontuação são mapeados para outros símbolos — e caracteres acentuados (`á`, `é`, `ç`, `ã`, etc.) sequer são aceitos por `KeyboardLayoutUS.write()` (gerando `ValueError`).

### Caracteres seguros (iguais em US e ABNT2)
- Letras `A-Z` e `a-z`
- Dígitos `0-9`
- Espaço, `.`, `,`, `-`, `_`, `=`, `+`, `!`, `@`, `#`, `$`, `%`, `&`, `*`, `(`, `)`

### Tabela de divergências (`KeyboardLayoutUS` -> host ABNT2)

| Caractere no script (`STRING`) | Scancode enviado (US) | Resultado no host ABNT2 |
| --- | --- | --- |
| `;` | `0x33` | `ç` |
| `:` | `Shift + 0x33` | `Ç` |
| `/` | `0x38` | `;` |
| `?` | `Shift + 0x38` | `:` |
| `'` | `0x34` | `~` (tecla morta) |
| `"` | `Shift + 0x34` | `^` (tecla morta) |
| `` ` `` | `0x35` | `'` |
| `~` | `Shift + 0x35` | `"` |
| `[` | `0x2F` | `´` (acento agudo - tecla morta) |
| `{` | `Shift + 0x2F` | `` ` `` (acento grave - tecla morta) |
| `]` | `0x30` | `[` |
| `}` | `Shift + 0x30` | `{` |
| `\` | `0x31` | `]` |
| `|` | `Shift + 0x31` | `}` |
| `^` | `Shift + 6` (`0x23`) | `¨` (trema - tecla morta) |

### Recomendações práticas para ABNT2
1. **Para demonstrações portáveis (US + ABNT2):** mantenha o texto apenas no subconjunto ASCII seguro e rode `python3 simulate.py --strict` para garantir zero avisos `ABNT2_MISMATCH`.
2. **Para suporte completo a PT-BR:** utilize um layout customizado compatível com `adafruit_hid` (como módulos comunitários de `KeyboardLayout` para `br` / ABNT2) no lugar de `KeyboardLayoutUS`, lembrando que a tecla física `\`/`|` do ABNT2 corresponde ao código ISO `0x64` e `/`/?` ao código `0x87` (International 1).

---

## Controles Defensivos e Boas Práticas (Proteção contra HID Não Autorizado)

Este laboratório evidencia um ponto importante de arquitetura: sistemas operacionais confiam por padrão em novos teclados USB conectados a uma sessão já autenticada. As medidas abaixo formam uma defesa em camadas:

### 1. Segurança física e bloqueio de sessão
- **Bloqueio imediato ao se ausentar** (`Win+L` no Windows, `Ctrl+Cmd+Q` no macOS, `Super+L` no Linux) e políticas de bloqueio automático após poucos minutos de inatividade.
- Em estações críticas ou quiosques, uso de bloqueadores físicos de portas USB ou desativação de portas externas na BIOS/UEFI.

### 2. Controle de dispositivos USB no sistema operacional
- **Linux (`USBGuard`):** permite criar políticas de *allowlist* por `VID:PID`, classe USB e número de série, bloqueando automaticamente novas interfaces HID (`03:*:*`) enquanto a tela estiver bloqueada ou fora da lista aprovada.
- **Windows (GPO / Microsoft Intune / Defender Device Control):** restrição de instalação de novos dispositivos por ID de hardware/classe de dispositivo, além de auditoria de eventos de conexão USB.
- **macOS (MDM / Endpoint Security):** aprovação explícita de acessórios USB novos (recurso nativo *Allow accessories to connect* em Macs com Apple Silicon).

### 3. Princípio do menor privilégio e endurecimento de execução
- Uso diário com **conta padrão (sem privilégios administrativos)** e UAC configurado para exigir credenciais em desktop seguro.
- Políticas de controle de aplicativos (**WDAC / AppLocker** no Windows) e **PowerShell Constrained Language Mode** reduzem o impacto de comandos rápidos disparados por atalhos como `Win+R`.

### 4. Monitoramento e detecção (Blue Team)
- **Auditoria de novos dispositivos HID:** correlação de logs de enumeração USB (Windows Event Logs `DriverFrameworks-UserMode` / kernel PnP, `udev`/`journald` no Linux) com criação imediata de processos filhos de `explorer.exe`.
- **Telemetria de EDR/Sysmon:** alertas para sequências incomuns logo após a conexão de um dispositivo HID (por exemplo, abertura imediata de interpretadores de comando com cadência de digitação perfeitamente uniforme).
- **Conscientização:** política clara de nunca conectar cabos, pendrives ou adaptadores USB de origem desconhecida.

---

## Licença

Distribuído sob a licença [MIT](LICENSE).