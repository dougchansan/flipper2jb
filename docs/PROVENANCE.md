# Source provenance and attribution

Flipper2JB combines local Flipper keyboard and storage utilities with a third-party
ESP32-S2 TCP/UART bridge. The Python tools provide physical-key script generation,
editor-model replay, verified storage transfer, Bad KB launch and display capture.
The bundled en-UK layout is retained byte-for-byte from the local typing setup.

## Firmware

The upstream bridge is [busse/flipperzero-mcp](https://github.com/busse/flipperzero-mcp)
at `36948b7ffb03e46fb352394363e327d953706a9d`. Its MIT notice is preserved in
[firmware/LICENSE](../firmware/LICENSE).

Local modifications include an AP-only private WPA2/PMF configuration, one AP/TCP
client, atomic UART writes, DATA acknowledgments, heartbeat handling, presence
signaling without deleting the UART driver, deferred LED startup, partial TCP
sends and double-close handling. Compile-time checks validate AP credential lengths;
the fallback AP password was removed from Kconfig. Imported trailing whitespace
was normalized. Configuration defaults retain the tested UART rate of 115200.

[firmware-source-sha256.json](firmware-source-sha256.json) records included firmware
source hashes. Original generated sdkconfig, AP credentials, flash backups and
NVS images are not included.

## Host tools

The Python transport and upload routines are adapted from local Flipper RPC
utilities. This version provides configurable TCP host/port, truncation-aware
protobuf decoding, a command-line interface, a printable-ASCII BASIC text
converter, independent editor replay, and private generated files. It does not
bundle any caller-supplied `bootstrap.bas` or other application source.

Reference SHA-256 values:

```text
original local rpc_client.py, before parameterization and decoder checks:
f913b76251ed31db54bfb7b946f044097db905ff89f59bfe9469ba8af0b9316b
en-UK.kl, unchanged:
2fbb1e7f3e144050339157d989e03f12e734e2defdedded28dfd7f9a2b6c903c
```

Imports and offline compilation do not connect to hardware. Credentials, private
serial transcripts, captured displays and generated scripts are not distributed.

## Optional target adapter

The SmileBASIC/ns2jb target follows the command order and active-host record format
in [cpypwn/mac2jb](https://github.com/cpypwn/mac2jb), inspected at
`68eb95f0bacc2d4940a2ea44c6a6153b040d5401`. The MIT notice is retained in
[third_party/mac2jb/LICENSE](../third_party/mac2jb/LICENSE). The target uses this
project's en-UK Flipper transport rather than the reference project's US-layout
Mac USB gadget sender. No native driver, GUI, bootstrap source or runtime is copied.
