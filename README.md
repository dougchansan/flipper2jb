# Flipper2JB

Flipper Zero and ESP32-S2 Wi-Fi dev board tools for preparing keyboard scripts,
transferring files, and entering BASIC source into a USB-connected text editor.

```text
Computer ── Wi-Fi / TCP ── ESP32-S2 board ── Expansion UART ── Flipper Zero
                                                                   │
                                                              USB keyboard
                                                                   │
                                                             Target editor
```

The toolkit includes a BASIC-to-Bad-KB converter, verified Wi-Fi uploads, remote
script start, a USB serial upload fallback, and Flipper display capture. An
optional [SmileBASIC/ns2jb target](targets/ns2jb/README.md) adds bootstrap text
preparation and fresh host-command delivery, following the mac2jb workflow. Python
**3.10+** and its standard library are sufficient for the host tools.

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
not currently supported by the launch command. The dev board stays attached to
the Flipper; the Flipper's USB connects to the target device.

The generated sequence assumes an empty editor with the cursor at the beginning.
After each Enter, it uses Home, Shift+End, Space and Backspace to clear inherited
auto-indentation. The target must support these shortcuts as expected.
An offline replay check verifies the sequence's editor model; it does not establish
compatibility with every editor or prove physical key delivery.

Default character hold/release and Shift settling are **50 ms**; navigation uses
**100 ms**. No timing option is needed. The manifest reports the estimated typing
duration.

## Connect and upload

Connect the computer to the board's existing private Wi-Fi AP. A working board
needs no firmware change. The default endpoint is `192.168.4.1:8080`:

```sh
python3 -m flipper2jb ping
python3 -m flipper2jb inspect
python3 -m flipper2jb upload dist/bootstrap.txt
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
get a unique filename. Wi-Fi uploads use 512-byte protobuf storage records.

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

The remote script stays on the Flipper until removed. After stopping and closing
Bad KB, remove the exact path printed by the upload/run command:

```sh
python3 -m flipper2jb remove /ext/badusb/Flipper2JB-REPLACE-WITH-PRINTED-ID.txt
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

`FLIPPER_WIFI_HOST` and `FLIPPER_WIFI_PORT` are also supported.

## Wi-Fi board firmware

The [firmware guide](firmware/tcp_uart_bridge/README.md) covers wiring, building,
diagnostics, and optional flashing. The bridge uses a private WPA2 AP with one
Wi-Fi client and one TCP client. There is no additional application authentication
on the protobuf endpoint, so keep AP access restricted to trusted devices.

Local Wi-Fi credentials, generated firmware builds, captures, and runtime files
are excluded from Git. [Source provenance and attribution](docs/PROVENANCE.md)
and [validation notes](docs/VALIDATION.md) describe the included components and
the limits of the recorded tests.
