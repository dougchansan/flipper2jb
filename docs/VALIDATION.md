# Validation

On 2026-10-24, all **13 tests** passed locally with Python 3.14.

The generic toolkit is checked with synthetic RPC responses, a fragmented
loopback TCP server, and physical-key replay against an editor model. These tests
exercise storage transfer, exact readback, launch failures without automatic
retry, text indentation, blank lines, punctuation, timing bounds, generated file
permissions, malformed protobuf, and remote path containment.

The documented fresh-checkout workflow uses only the bundled typing example and
caller-supplied printable-ASCII BASIC. It requires Python 3.10+ and no third-party
Python packages. CI is configured for Python 3.10 and 3.14 on Linux and macOS;
configured jobs are not evidence that every platform has passed remotely.

The retained ESP32-S2 firmware previously built with ESP-IDF v5.4.2 using isolated
output and dummy build credentials. Application size was 0xcd830 bytes, with 20%
free in the 1 MiB partition. Firmware compilation does not establish a physical
bridge handshake.

The generic release preparation performs no real AP connection, USB serial
operation, keyboard input or firmware flash. Remote-start and USB-serial commands
still need validation on the intended hardware/editor. The target editor must
support the documented auto-indent clearing shortcuts. A replay result or RPC
acknowledgment does not prove successful USB text delivery.

Generated scripts and firmware configuration stay in ignored paths. Fresh-checkout
checks also verify that those files leave the Git working tree clean.
