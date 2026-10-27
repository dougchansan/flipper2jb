# Flipper2JB

Flipper Zero tools for preparing keyboard scripts, transferring files over
Bluetooth LE or an optional Wi-Fi dev board, and entering BASIC source into a
USB-connected text editor.

```text
Computer ── Bluetooth LE ── Flipper Zero ── USB keyboard ── Target editor
```

Bluetooth needs no Wi-Fi board. The existing ESP32-S2 Wi-Fi/Expansion UART bridge
is also supported.

The toolkit includes a BASIC-to-Bad-KB converter, verified Wi-Fi uploads, remote
script start, a USB serial upload fallback, and Flipper display capture. An
optional [SmileBASIC/ns2jb target](targets/ns2jb/README.md) adds bootstrap text
preparation and fresh host-command delivery, following the mac2jb workflow. Python
**3.10+** is required. Wi-Fi and offline compilation use the standard library;
Bluetooth adds the optional Bleak dependency.

## Start with a fresh checkout

```sh
git clone --branch flipper2jb --single-branch https://github.com/dougchansan/flipper2jb.git
cd flipper2jb
python3 -m flipper2jb compile /path/to/bootstrap.bas -o dist/bootstrap.txt
```

Compilation runs offline and creates a keyboard script and a JSON manifest with
hashes, estimated duration, and an editor replay check. Generated files are private
to the local user and `dist/` is ignored by Git. Output files are never silently
overwritten; choose a new output filename when compiling another version.

The source must contain printable ASCII with LF or CRLF line endings. The converter
preserves blank lines and indentation and adds a final newline when needed. It
enters text without automatically executing or saving the BASIC program.

## Keyboard and editor setup

The remote-start workflow uses Momentum **Bad KB**, **USB** keyboard mode, the
included **en-UK** layout, and **Caps Lock off**. Stock firmware's Bad USB app is
not currently supported by the launch command. The Flipper's USB connects to
the target device; the Wi-Fi board is only needed for Wi-Fi transport.

**Not on Momentum?** The launch command here drives Momentum's Bad KB. If you're
on stock (or other) firmware, [ns2-flipper-typer](https://github.com/wowilookgood/ns2-flipper-typer)
does the same job from the Flipper's **JavaScript Bad USB** module (needs the JS
SDK 0.1+ / Scripts app, so Shift is held reliably): it types the ns2jb
`bootstrap.bas` and the per-run Direct-mode commands into SmileBASIC. Use the same
console setup — USB keyboard **English (US)**, SmileBASIC **CapsLock off**, and
restart SmileBASIC. It's tested on Unleashed; recent official and Momentum are
expected to work.

The generated sequence assumes an empty editor with the cursor at the beginning.
After each Enter, it uses Home, Shift+End, Space and Backspace to clear inherited
auto-indentation. The target must support these shortcuts as expected.
An offline replay check verifies the sequence's editor model; it does not establish
compatibility with every editor or prove physical key delivery.

Default character hold/release and Shift settling are **50 ms**; navigation uses
**100 ms**. No timing option is needed. The manifest reports the estimated typing
duration.

## Bluetooth connection (no Wi-Fi board)

Install the optional Bluetooth dependency, enable Bluetooth on the Flipper, and
close the mobile app or other Bluetooth connections:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-bluetooth.txt
python -m flipper2jb ble-scan
export FLIPPER_TRANSPORT=ble
export FLIPPER_BLE_DEVICE="PASTE-SCAN-IDENTIFIER"
python -m flipper2jb ping
python -m flipper2jb inspect
python -m flipper2jb upload dist/bootstrap.txt
```

Use the identifier from the scan (an OS UUID on macOS). Confirm the Flipper's
pairing code when prompted and allow Bluetooth access for your terminal.
Subsequent commands use BLE with these environment variables set. The Flipper
remains a **USB** keyboard to the target. See the [Bluetooth guide](docs/BLUETOOTH.md)
for explicit flags, pairing, target scripts and verification limits. A supervised
[hardware test](docs/HARDWARE-TEST.md) passed short BLE transfer, 50 ms USB typing
and timed auto-close; full bootstrap and target-session runs remain unverified.

## Wi-Fi connection (optional board)

Connect the computer to the board's existing private Wi-Fi AP. A working board
needs no firmware change. The default endpoint is `192.168.4.1:8080`:

```sh
python3 -m flipper2jb --transport wifi ping
python3 -m flipper2jb --transport wifi inspect
python3 -m flipper2jb --transport wifi upload dist/bootstrap.txt
```

`ping` checks a protobuf echo. `inspect` verifies the exact included keymap bytes
and USB keyboard interface. `upload` transfers the script, verifies exact readback,
and prints its unique remote filename. Uploading does not start keyboard input.
The `/ext/badusb/` directory must already exist on the Flipper.

An explicit destination is also supported:

```sh
python3 -m flipper2jb upload dist/bootstrap.txt --remote /ext/badusb/Bootstrap.txt
```

An existing file at an explicit destination may be replaced. Omit `--remote` to
get a unique filename. Both transports use the same 512-byte protobuf storage
records; BLE additionally splits each frame into GATT-sized writes.

## Send the script

Open the intended empty editor buffer, check Caps Lock is off, and return the
Flipper to its desktop. Then:

```sh
python3 -m flipper2jb run dist/bootstrap.txt --ready
```

`run` uploads and verifies the script, checks the keyboard configuration, and
sends one Bad KB start input. Typing begins after the script's five-second delay.
Observe the target editor: a Flipper acknowledgment confirms request acceptance,
not completed USB delivery. There are no automatic launch retries.

**Auto-close is on by default for Flipper2JB-generated scripts.** Keep the command
running: it waits for the scripted duration plus a 25% buffer (at least 10 seconds),
then sends Back once and verifies that the Flipper application exited. It checks
the screen header during the wait and cancels closing if that header changes or
communication fails. This is a timer, not a completion signal: a paused or stalled
script can still be interrupted. Avoid interacting with Bad KB during the wait.

Use `--keep-open` to disable closing. Custom scripts keep manual closing; explicit
`--auto-close` only accepts this project's bounded generated key sequences. Pressing
Ctrl+C cancels the waiting command without sending Back. This feature works with
Wi-Fi and BLE; it does not reset the target session latch or delete the remote file.

After auto-close reports the app exited (or after manually closing Bad KB), remove
the exact path printed by the upload/run command:

```sh
python3 -m flipper2jb remove /ext/badusb/F2-REPLACE-WITH-PRINTED-ID.txt
```

## Optional target scripts

The [target guide](targets/ns2jb/README.md) documents bootstrap conversion,
one-use session scripts, the current-host command file, and restart/latch handling.
These commands are separate from general text entry and are never invoked by
compilation, dependency setup or the offline tests.

```sh
python3 -m flipper2jb.targets.ns2jb --help
```

## Other tools

| Command | Purpose |
| --- | --- |
| `python3 -m flipper2jb capture dist/flipper.pbm` | Capture the Flipper's display as a PBM image |
| `python3 tools/upload_usb.py dist/bootstrap.txt --device /dev/cu.usbmodemYOURFLIPPER --remote /ext/badusb/BootstrapUSB.txt` | macOS/Linux USB serial upload; exact readback, refuses existing destination, never starts typing |
| `python3 tools/configure_bridge.py` | Generate private AP build settings offline |

Use the Flipper's USB serial device for the fallback uploader, then reconnect its
USB to the target before typing. The ESP32 board's USB port is used for board
firmware flashing, not this serial upload command.

Global connection options go before the subcommand:

```sh
python3 -m flipper2jb --host 192.168.4.1 --port 8080 inspect
```

`FLIPPER_WIFI_HOST` and `FLIPPER_WIFI_PORT` configure Wi-Fi.
`FLIPPER_TRANSPORT` selects `wifi` (default) or `ble`; `FLIPPER_BLE_DEVICE` selects
the Bluetooth device. Explicit flags override these environment values.

## Wi-Fi board firmware

The [firmware guide](firmware/tcp_uart_bridge/README.md) covers wiring, building,
diagnostics, and optional flashing. The bridge uses a private WPA2 AP with one
Wi-Fi client and one TCP client. There is no additional application authentication
on the protobuf endpoint, so keep AP access restricted to trusted devices.

Local Wi-Fi credentials, generated firmware builds, captures, and runtime files
are excluded from Git. [Source provenance and attribution](docs/PROVENANCE.md)
and [validation notes](docs/VALIDATION.md) describe the included components and
the limits of the recorded tests.
