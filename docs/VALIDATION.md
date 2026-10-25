# Validation

On 2026-10-24, all **39 tests** passed locally with Python 3.14.

The generic toolkit is checked with synthetic RPC responses, a fragmented
loopback TCP server, and physical-key replay against an editor model. These tests
exercise storage transfer, exact readback, launch failures without automatic
retry, text indentation, blank lines, punctuation, timing bounds, generated file
permissions, malformed protobuf, and remote path containment.

The documented fresh-checkout workflow uses caller-supplied printable-ASCII BASIC
with a default character timing of 50 ms. It requires Python 3.10+ and no third-party
Python packages for Wi-Fi/offline use. Bluetooth adds optional Bleak. CI is configured for Python 3.10 and 3.14 on Linux and macOS;
configured jobs are not evidence that every platform has passed remotely.

The retained ESP32-S2 firmware previously built with ESP-IDF v5.4.2 using isolated
output and dummy build credentials. Application size was 0xcd830 bytes, with 20%
free in the 1 MiB partition. Firmware compilation does not establish a physical
bridge handshake.

The release preparation performs no real AP connection, USB serial
operation, keyboard input or firmware flash. Remote-start and USB-serial commands
still need validation on the intended hardware/editor. The target editor must
support the documented auto-indent clearing shortcuts. A replay result or RPC
acknowledgment does not prove successful USB text delivery.

Generated scripts and firmware configuration stay in ignored paths. Fresh-checkout
checks also verify that those files leave the Git working tree clean.

## Optional ns2jb target

The target's tests cover physical-key reconstruction of the full command order
and LOAD confirmation; strict START parameter validation; live PID checks; private
review scripts; rejection of marked session scripts by general run; one-shot latch
consumption; no retry after a lost launch acknowledgment; blocking a host record
change during upload; and refusal to reset while a recorded host is live.

Both bootstrap variants in the pinned mac2jb checkout pass the general compiler's
physical-key/editor replay. The new target adapter has not been validated on
hardware. Bootstrap preparation does not include a runtime or establish that a
console can execute the supplied source.

## Bluetooth LE transport

Nine additional BLE tests cover credit-window exhaustion/refill, MTU fragmentation,
fragmented protobuf replies, explicit/ambiguous device selection, dependency errors,
connection cleanup, bounded buffering, no retry after a lost start acknowledgment,
and target-latch retention on a BLE failure. All 39 tests pass on Python 3.14 and
in an isolated Python 3.12 environment with Bleak 3.0.2 installed. The Bleak client
and scanner imports succeed on macOS. No scan, pairing or hardware access occurred.
Physical Bluetooth transfer and USB keyboard operation remain unverified.

## Timed auto-close

Eight lifecycle tests cover generated-script timing and command restrictions;
waiting for the full duration plus buffer; sending Back only once; cancelling on
a changed screen, early app exit, transport failure or Ctrl+C; default auto-close
and keep-open behavior; retaining the consumed target latch; and a complete BLE
start/wait/close/verify cycle. The existing TCP loopback test also covers automatic
closing for generated text scripts. All tests use synthetic device responses.

The firmware's Bad KB worker does not publish a script-completion event through
its ordinary RPC launch interface. Auto-close uses explicit DELAY totals plus
25% (minimum 10 seconds), then one Back press and a loader-lock status check.
It cannot detect a pause/stall that leaves the screen header unchanged. A timer
expiring is not proof of successful text delivery. No physical auto-close was
attempted. Source review used Momentum revision
`d3f89dfe2ef6b01839201598e9be1590cba80322` (Bad KB view/worker and GUI navigation).
