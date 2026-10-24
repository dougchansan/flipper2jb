# Validation — 2026-10-23

## This repository

- 18 Python tests pass on this Mac (Python 3.14), using synthetic RPC and a
  fragmented loopback TCP server. Coverage includes physical key decoding,
  indentation, empty lines, punctuation, timing bounds, corrupt upload readback,
  lost launch acknowledgements without retry, shared session latch, private
  output permissions, malformed protobuf and remote path containment.
- Full existing bootstrap: 8,108 source characters; exact editor-model replay;
  539,604-byte generated script; estimated 1,522.3 seconds at 50 ms. The generated
  script stayed outside Git and was not uploaded.
- ESP32-S2 bridge built successfully using ESP-IDF v5.4.2 and isolated output
  with dummy build-only AP credentials. Application size 0xcd830 bytes; 20%
  free in the 1 MiB app partition. No flashing occurred.
- Git whitespace check and Python module/help checks pass.
- CI is configured for Python 3.10 and 3.14 on Linux and macOS. The initial
  configuration is not itself proof that remote jobs have passed.

No Flipper/AP connection, serial device access, keyboard input, console host
launch or firmware flash was performed while assembling this repository.
The parameterized USB uploader and the simplified reusable saved-source checker
need a future physical validation; their prior equivalents were used locally.
The firmware build confirms compilation, not a new hardware handshake.

## Historical observations carried forward

Local preparation records report successful en-UK text trials at
100/75/50/35/20 ms and a full-file 50 ms workflow. The user's confirmed
passing default is 50 ms. HBLauncher milestones included an authenticated native
session, graphical menu, Hello World launch/return and Diagnostics controller
input. Those observations belong to the earlier checkout and hardware sessions;
they do not establish that every current CLI command has been tested on hardware.

Use offline compilation and upload/readback checks before a new typing attempt,
and observe the console for final text delivery. RPC acceptance is distinct from
USB delivery or a successful authenticated host connection.
