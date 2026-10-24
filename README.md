# FlippyKB

Our Flipper Zero / Wi-Fi dev board toolkit for typing SmileBASIC source into a
Switch, uploading Bad KB scripts, checking saved source, and delivering a fresh
host connection command.

```text
Mac ── Wi-Fi / TCP protobuf ── ESP32-S2 board ── Expansion UART ── Flipper Zero
                                                                    │
                                                               USB keyboard
                                                                    │
                                                         Switch / SmileBASIC
```

Python **3.10+**, standard library only. Run commands from this checkout; no pip
installation needed. The Wi-Fi board stays attached to the Flipper, and the
Flipper's USB connects to the Switch/dock. The keyboard transport was used with
Momentum **Bad KB**, USB mode, the included **en-UK** layout, and Caps Lock off.
Stock firmware's Bad USB app is not currently supported by the launch command.
The bootstrap workflow was used with SmileBASIC **4.4.9** on Switch 2 **23.0.1**;
this does not establish compatibility with other versions.

## Convert bootstrap.bas and send it

Use the existing `bootstrap.bas` from your ns2jb or HBLauncher checkout:

```sh
git clone https://github.com/dougchansan/flippykb.git
cd flippykb
python3 -m flippykb compile ../ns2jb-main/bootstrap.bas -o dist/bootstrap.txt
```

This creates a private Bad KB script and adjacent JSON manifest containing hashes,
timing and physical-key replay verification. It preserves blank lines and leading
spaces, clearing SmileBASIC's auto-indent after every Enter. Default character
hold/release and Shift settling are **50 ms**; navigation is **100 ms**. The full
8,108-character reference bootstrap takes about **25.4 minutes**. `--key-ms` accepts
20..250; short trials at 20 ms do not establish long-file reliability.

Connect the Mac to the board's existing private Wi-Fi AP. Keep its current password;
there is no need to flash or reconfigure a working board. Default endpoint is
`192.168.4.1:8080`:

```sh
python3 -m flippykb ping
python3 -m flippykb inspect
python3 -m flippykb upload dist/bootstrap.txt --remote /ext/badusb/Bootstrap.txt
```

`upload` verifies exact readback and leaves the script ready on the Flipper. The
remote directory must already exist. An explicit existing filename may be replaced;
omit `--remote` to use a unique name printed by the command. Neither command types
into the Switch. Select the uploaded file in Bad KB when ready, or start it remotely:

1. Open SmileBASIC's **empty intended editor slot**, at the first line. Check that
   this is the editor rather than Direct mode, Caps Lock is off, and the Flipper is
   at its desktop. Leave existing saved programs untouched.
2. Start once:

   ```sh
   python3 -m flippykb run dist/bootstrap.txt --ready
   ```

3. Observe typing after the five-second delay. The script **does not RUN or SAVE**
   the BASIC source. Review the editor and save it yourself as `NS2` in slot 0.
4. After Bad KB is stopped and closed, remove the unique remote path printed above:

   ```sh
   python3 -m flippykb remove /ext/badusb/FlippyKB-REPLACE-WITH-PRINTED-ID.txt
   ```

Wi-Fi uploads use the Flipper's protobuf storage protocol with 512-byte records.
Starting Bad KB verifies the exact UK keymap bytes and USB interface first. A
transport acknowledgment establishes request acceptance; observe the Switch to
verify text delivery. There are no automatic launch retries. The script remains
on the Flipper until removed; the command does not infer completion from time.

## Verify saved source

Generate the separate SmileBASIC checker, then convert and type it into a different
empty editor slot:

```sh
python3 -m flippykb checker ../ns2jb-main/bootstrap.bas --name NS2 -o dist/checker.bas
python3 -m flippykb compile dist/checker.bas -o dist/checker.txt
python3 -m flippykb run dist/checker.txt --ready
```

Run the checker manually in that separate slot. It loads `TXT:NS2`, compares line
and character counts and two rolling hashes, and prints `SOURCE CHECK MATCH` or
`SOURCE CHECK MISMATCH`. It ignores CR characters and empty lines, matching the
previous saved-source check; nonempty-line spacing and characters affect the
hashes. These checksums detect typing mistakes and are not cryptographic signatures.
The command does not execute the bootstrap.

## Timing trial

```sh
python3 -m flippykb compile examples/typing-test.bas --key-ms 100 -o dist/test100.txt
python3 -m flippykb run dist/test100.txt --ready
```

Use a disposable empty editor slot. Compare all four lines with the example,
including indentation, punctuation and case. Repeat with new output files for
75, 50, 35 and 20 ms only as needed. The historical long-file default is 50 ms.

## Fresh host session command

The existing HBLauncher integration already generates and delivers a fresh
`V=START(...)` command. Continue to use that launcher for a coordinated listener,
authentication and native qualification. See [host integration](docs/HOSTS.md).
For another host that already owns a fresh listener, generate its one-use script
without putting a pairing command in shell history or process arguments:

```sh
# Paste the host's fresh V=START(...) command, then Ctrl-D.
python3 -m flippykb session --name NS2 -o dist/session.txt
python3 -m flippykb run dist/session.txt --ready
```

This sequence requires **Direct mode with NS2 already saved**, a fresh application
process, Caps Lock off, and the Flipper desktop. It types LOAD, confirmation, RUN,
the one-shot REMOVE transition and the supplied connection command. The host must
already be listening. Session output is private and must never be replayed.

Session launches share HBLauncher's durable consumed-session latch. Stop all hosts
and Bad KB, restart the console, then explicitly rearm if a previous session
consumed the latch:

```sh
python3 -m flippykb reset-session --confirm-console-restarted
```

The latch survives failures and refuses reset while its recorded process is live.
It cannot detect manual typing or an unrelated host that doesn't use the latch.
Do not reset it just to retry in the same console process. Never launch this and
HBLauncher concurrently.

## Other tools

| Command | Purpose |
| --- | --- |
| `python3 -m flippykb capture dist/flipper.pbm` | Flipper display screenshot, **not** a Switch screen capture |
| `python3 tools/upload_usb.py dist/bootstrap.txt --device /dev/cu.usbmodemYOURFLIPPER --remote /ext/badusb/BootstrapUSB.txt` | macOS/Linux USB serial fallback; exact readback, refuses existing target, never launches |
| `python3 tools/configure_bridge.py` | Generate fresh private AP build configuration, offline |
| `python3 -m unittest discover -s tests -v` | Offline and loopback tests; no hardware |

Global connection options go before the command:

```sh
python3 -m flippykb --host 192.168.4.1 --port 8080 inspect
```

`FLIPPER_WIFI_HOST` and `FLIPPER_WIFI_PORT` also work. USB upload requires the
Flipper connected to the Mac, so reconnect its USB to the Switch before typing.
The serial uploader is adapted from the previous USB CLI workflow; it has not
been retested on hardware in this repository.

## Firmware and provenance

[Wi-Fi board build/setup](firmware/tcp_uart_bridge/README.md) documents the existing
AP-only ESP32-S2 firmware, wiring, diagnostics and optional flashing.
[Provenance](docs/PROVENANCE.md) records sources and reference hashes.
[Validation](docs/VALIDATION.md) distinguishes offline results from prior hardware
observations. Runtime captures, Wi-Fi credentials, NVS, flash backups, SDK dumps,
generated session scripts and tokens are excluded from the repository.

This is the keyboard/transport toolkit. ns2jb and HBLauncher continue to own their
console runtime, native checks, SDK, applications and exports.
