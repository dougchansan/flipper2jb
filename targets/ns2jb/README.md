# Optional SmileBASIC / ns2jb target

This adapter provides the bootstrap-text and post-bootstrap keyboard workflow
seen in [cpypwn/mac2jb](https://github.com/cpypwn/mac2jb), using a Flipper over
Bluetooth LE or its Wi-Fi dev board instead of Mac USB gadget drivers. It does not install a Mac
kernel extension or require a change to macOS security settings.

The general tools remain under `python3 -m flipper2jb`. Target commands are under
`python3 -m flipper2jb.targets.ns2jb`. Importing either module performs no device
I/O. Target operations are optional and not run by the test/setup instructions.

## Connection

Use `FLIPPER_TRANSPORT=ble` and `FLIPPER_BLE_DEVICE` from the
[Bluetooth guide](../../docs/BLUETOOTH.md) to operate without a Wi-Fi board.
The target accepts the same `--transport ble --ble-device IDENTIFIER` global
options as the general CLI, placed before `start`. Wi-Fi remains the default.
Transport selection does not change the 50 ms typing default or target latch.

## Prepare bootstrap text

Supply the bootstrap from an existing ns2jb checkout, or from mac2jb's `assets/`:

```sh
python3 -m flipper2jb.targets.ns2jb bootstrap /path/to/mac2jb/assets/bootstrap.bas -o dist/ns2jb/bootstrap.txt
python3 -m flipper2jb upload dist/ns2jb/bootstrap.txt
```

This compiles text only and records the source hash. The text-entry script neither
runs nor saves the BASIC program. Start it in an empty SmileBASIC editor with:

```sh
python3 -m flipper2jb run dist/ns2jb/bootstrap.txt --ready
```

Observe the result and save the reviewed source as `NS2` in slot 0 yourself.

**Keyboard difference:** mac2jb's native USB sender uses a US layout; this adapter
retains the tested **en-UK** Flipper layout and USB interface. Configure the target
keyboard language consistently. Character hold/release and Shift settling default
to **50 ms**, with **100 ms** navigation. No timing option is needed. Do not copy
mac2jb's layout instructions blindly onto this Flipper path.

The reference mac2jb revision is
`68eb95f0bacc2d4940a2ea44c6a6153b040d5401`. Its `assets/bootstrap.bas` hash is
`fe9f7541ce1f2a82db1eb769eaefd11e823baf3a50a6cd0c17c71e81b466da72`;
its vendored upstream bootstrap is a different byte sequence with hash
`2261f65fb9ec0ed708ce0f0b6da5057168f706e541d956f658a3c2655e9e8c36`.
The adapter accepts either caller-supplied source and records its exact hash; it
does not fetch updates, bundle the runtime, or silently substitute one for another.

## Fresh post-bootstrap sequence

Start a host through mac2jb's existing `scripts/host.sh` in its own checkout,
following that project's network and host instructions. That wrapper publishes
`vendor/ns2jb/runs/mac2jb-active-connect.txt` with a live host PID and its current
`V=START(...)` command. Flipper2JB reads this format directly. The host must be
running and ready before sending keyboard input.

For an offline review of the generated keys while the host record is live:

```sh
python3 -m flipper2jb.targets.ns2jb session --active-file /path/to/mac2jb/vendor/ns2jb/runs/mac2jb-active-connect.txt -o dist/ns2jb/session.txt
```

The file contains the current pairing values and is written with mode 0600. Keep
it private. It is a review artifact; general `run` refuses these marked session
scripts so that guarded target delivery is used instead.

Before a live attempt, freshly restart the console, open SmileBASIC in **Direct
mode**, confirm `NS2` is saved, Caps Lock is off, Bad KB is closed to the Flipper
desktop, and no other sender owns the target. Then explicitly run:

```sh
python3 -m flipper2jb.targets.ns2jb start --active-file /path/to/mac2jb/vendor/ns2jb/runs/mac2jb-active-connect.txt --ready
```

This generates the sequence afresh:

```text
LOAD "TXT:NS2"
<Enter to accept the load prompt>
RUN
REMOVE NSR,&H60000000,&H3FFFFFFF
V=START(<current host parameters>)
```

The adapter validates all nine numeric START parameters, checks the recorded host
PID, verifies that the active record has not changed before upload, checks the
Flipper layout, and consumes a durable one-shot latch before sending. It verifies
exact storage readback, starts Bad KB once, and never retries automatically.

`start` now keeps the connection open and auto-closes Bad KB after the generated
sequence's duration plus a 25% buffer (minimum 10 seconds), verifying application
exit afterward. Use `--keep-open` to disable this. Closing is timed, not proof of
script completion, authentication or runtime acquisition; paused or stalled scripts
can be interrupted. Do not interact with Bad KB during the wait. A changed screen
header or connection failure cancels closing without additional Back input.
It does not print the pairing values. Only the host's authenticated connection
and subsequent results establish that the sequence worked; RPC acknowledgments
and elapsed time do not establish console execution or runtime acquisition.

Never repeat the REMOVE transition in the same application process. After any
failed or uncertain attempt, stop Bad KB and all hosts and restart the console.
The latch is shared with the previously used local host adapter. Its default path
is `~/.local/state/hblauncher/console-session.json`; `HB_SESSION_LATCH` overrides it.
Only after that restart, rearm with:

```sh
python3 -m flipper2jb.targets.ns2jb reset --confirm-console-restarted
```

Reset refuses while the recorded sender or host PID is live. The latch cannot
prevent manually replaying a remote file or other software ignoring the latch.
After auto-close verifies exit, delete the unique remote script printed by `start`
using the general `remove` command. With `--keep-open`, close Bad KB yourself first. Do not replay a remaining session script.

## Attribution and validation

The command order and active-file format follow the pinned mac2jb source. Its
MIT notice is retained at [third_party/mac2jb/LICENSE](../../third_party/mac2jb/LICENSE).
The adapter is Python code for the existing Flipper transport, not a copy of
mac2jb's C sender, driver, GUI or vendored runtime. Bootstrap source remains
caller-supplied. See [validation](../../docs/VALIDATION.md) for offline coverage;
this new adapter has not been tested on physical hardware.
