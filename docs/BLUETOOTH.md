# Bluetooth LE connection — no Wi-Fi board

Bluetooth replaces the computer-to-Flipper control link. The Flipper still acts
as a **USB** keyboard connected to the target. Keep Bad KB in USB mode and use the
included en-UK layout; do not select its Bluetooth HID keyboard interface.

```text
Computer ── Bluetooth LE / RPC ── Flipper Zero ── USB keyboard ── Target editor
```

No Wi-Fi dev board or new Flipper firmware is required for the BLE transport.
The existing remote launch commands still require Momentum's Bad KB app; adding
BLE does not add support for stock Bad USB launch names.

## Install the optional dependency

From the checkout, using a working Python 3.10+ installation:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-bluetooth.txt
```

Wi-Fi and offline compilation remain usable without Bleak installed.

## Select and pair your Flipper

1. Enable Bluetooth in the Flipper settings and leave it at its desktop.
2. Disconnect the Flipper mobile app and other Bluetooth clients so the serial
   service is available. Allow the terminal/Python application Bluetooth access
   if the operating system requests it.
3. Scan:

   ```sh
   python -m flipper2jb ble-scan
   ```

4. Copy the exact device identifier printed next to your Flipper. On macOS this
   is an OS-assigned UUID, rather than the Flipper's Bluetooth MAC address.
5. Choose it and verify a read-only connection first:

   ```sh
   export FLIPPER_TRANSPORT=ble
   export FLIPPER_BLE_DEVICE="PASTE-SCAN-IDENTIFIER"
   python -m flipper2jb ping
   python -m flipper2jb inspect
   ```

The first access to authenticated serial characteristics can open an OS pairing
prompt. Confirm the code shown on your Flipper. Pairing is handled by the OS;
this tool does not record the PIN. Connection/pairing setup allows up to 90 seconds
per setup operation. Scan results do not automatically select a nearby device.
An exact unique advertised name also works, but an identifier avoids ambiguity.

The equivalent explicit flags go **before** the subcommand:

```sh
python -m flipper2jb --transport ble --ble-device "PASTE-SCAN-IDENTIFIER" ping
```

## Transfer and type

With those environment variables set, normal commands use Bluetooth:

```sh
python -m flipper2jb compile /path/to/bootstrap.bas -o dist/bootstrap.txt
python -m flipper2jb upload dist/bootstrap.txt
python -m flipper2jb run dist/bootstrap.txt --ready
```

Prepare the empty intended target editor before `run`; it sends keyboard input.
Character timing remains **50 ms**, with **100 ms** navigation. Bluetooth changes
transfer time, not the script's key delays. Upload still requires exact readback
before launch. The `/ext/badusb/` directory must already exist on the Flipper.

Capture and removal work through the same selected connection:

```sh
python -m flipper2jb capture dist/flipper.pbm
python -m flipper2jb remove /ext/badusb/Flipper2JB-REPLACE-WITH-PRINTED-ID.txt
```

Close Bad KB before removing its file. An acknowledgment confirms request
acceptance, not physical text delivery. Observe the target to verify completion.
There is no automatic reconnect or launch retry after an uncertain BLE failure.

## Optional target adapter

The [ns2jb adapter](../targets/ns2jb/README.md) accepts the same environment
variables or explicit transport flags:

```sh
python -m flipper2jb.targets.ns2jb --transport ble --ble-device "PASTE-SCAN-IDENTIFIER" start --active-file /path/to/mac2jb/vendor/ns2jb/runs/mac2jb-active-connect.txt --ready
```

Its live-host checks and consumed-session latch remain in force. After a failed
or uncertain target attempt, follow its stop/restart instructions before retrying.

## Switch back to Wi-Fi

```sh
export FLIPPER_TRANSPORT=wifi
python -m flipper2jb --host 192.168.4.1 ping
```

An explicit `--transport wifi` overrides the environment for an individual command.
BLE never silently falls back to Wi-Fi.

## Protocol and verification

The adapter uses the Flipper's encrypted BLE serial GATT service. It fragments
writes within the negotiated MTU and firmware's 243-byte characteristic update
limit, honors the big-endian receive-window credits, and reassembles the unchanged
protobuf byte stream from TX indications. CoreBluetooth operations remain on the
main async event loop; the existing synchronous RPC runs in a worker thread.
Receive buffers and waits are bounded. Disconnects wake blocked readers/writers.

Implementation references:

- [Flipper serial UUIDs](https://github.com/flipperdevices/flipperzero-firmware/blob/dev/targets/f7/ble_glue/services/serial_service_uuid.inc)
- [Flipper serial service and flow control](https://github.com/flipperdevices/flipperzero-firmware/blob/dev/targets/f7/ble_glue/services/serial_service.c)
- [Bleak client and pairing API](https://bleak.readthedocs.io/en/latest/api/client.html)

The transport is tested against simulated GATT peers and dependency imports.
Physical pairing, file transfer and concurrent BLE control/USB Bad KB operation
still require a hardware test. No such device operation was performed during
implementation.
