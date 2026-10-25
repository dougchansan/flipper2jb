# Existing AP-only ESP32-S2 bridge

Source is the locally modified `busse/flipperzero-mcp` TCP/UART bridge used in
our preparation. It uses Flipper Expansion negotiation, atomic UART frame writes,
DATA acknowledgements and heartbeat handling. TCP allows one client; the private
AP allows one Wi-Fi client, uses WPA2 with PMF required, and has no STA uplink or
captive portal. HTTP `/api/health` and `/api/debug/counters` are diagnostic;
HTTP file endpoints are placeholders. Script transfers use protobuf on TCP 8080.

This is third-party **dev board firmware**, separate from the Flipper main
firmware. A working board needs no changes to use the Python client.

## Wiring

| ESP32-S2 | Flipper | Direction |
| --- | --- | --- |
| GPIO 43 TX | pin 14 RX | board → Flipper |
| GPIO 44 RX | pin 13 TX | Flipper → board |
| GND | ground | common ground |
| 3.3 V | pin 9 | power |

Enable the existing Flipper USART/Expansion setting and seat the dev board.
The default UART negotiation target here is **115200**, matching the deployed
local configuration. Expansion's initial baud negotiation is in the source.

## Build

Use **ESP-IDF v5.4.2** with its ESP32-S2 toolchain, the version used locally.
After installing that environment and sourcing its `export.sh`, from repo root:

```sh
python3 tools/configure_bridge.py --ssid Flipper2JB
cd firmware/tcp_uart_bridge
idf.py -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.local' set-target esp32s2
idf.py -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.local' build
```

The generator creates a private, ignored `sdkconfig.defaults.local` with a fresh
random password; it refuses overwrites. Read that file locally to join the AP.
An empty/default password is deliberately a compile error. Do not reuse anyone's
old generated sdkconfig, NVS or firmware binary. Build output contains your new AP
password and stays ignored. If a prior sdkconfig exists, ESP-IDF may retain its
settings; edit it through `idf.py menuconfig` rather than assuming defaults replace
existing values.

Optional hardware flash, only when you intend to replace the board firmware:

```sh
idf.py -p /dev/cu.usbmodemYOURBOARD flash
idf.py -p /dev/cu.usbmodemYOURBOARD monitor
```

Use the board's USB port for flashing, not the Flipper's. Keep your original board
flash backup privately before replacing firmware. This repository contains no
backup or NVS image. No flashing is part of normal script compilation/upload.

Join the new AP from the Mac; its default gateway is 192.168.4.1. From repo root:

```sh
python3 -m flipper2jb ping
python3 -m flipper2jb inspect
```

Only trusted devices should join this AP: protobuf TCP has no additional
application authentication. The client does not change keyboard settings. If
inspection fails, select en-UK and USB in the Flipper's existing Bad KB settings
and use the included keymap bytes. Stop other RPC clients if TCP is busy.

The inherited source comments sometimes describe upstream captive portal/STA
behavior; this local `wifi_manager.c` is AP-only. The new compile-time checks
validate AP credential lengths. Aside from trailing whitespace normalization, other C source is retained from the deployed
local preparation. See [provenance](../../docs/PROVENANCE.md) for the
upstream revision and retained MIT notice in `firmware/LICENSE`.
