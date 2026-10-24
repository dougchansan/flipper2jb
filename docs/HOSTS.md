# Existing host integration

The bootstrap source in the local ns2jb distribution and HBLauncher bridge is
byte-identical (SHA-256 recorded in PROVENANCE.md). Reuse an already verified,
saved NS2; do not type it again for each host connection.

The existing macOS HBLauncher checkout has its own Flipper adapter. From that
checkout, the established invocation is:

```sh
HB_KEYBOARD=flipper HB_LIVE_APPROVED=1 ./start.sh <MAC_ADDRESS_REACHABLE_FROM_SWITCH>
```

This is a user-invoked live operation. Confirm fresh console state and stop other
hosts before running it. HBLauncher binds its listener, generates a fresh pairing
command, claims the shared session latch, sends the keyboard script, authenticates
the console and qualifies the native session. FlippyKB's `session` subcommand is
an adapter for a command supplied by a host; it does not establish a listener or
replace those runtime checks. It accepts the same numeric V=START syntax and
saved bootstrap filename restrictions as the existing adapter.

For ns2jb, follow that distribution's README for its host invocation and generated
connection command. Never copy a V=START from historical logs: it belongs to the
old listener/session. Avoid putting pairing data into command arguments, Git,
terminal transcripts or reusable examples.

Topology has two separate links: the Mac reaches the Flipper AP over Wi-Fi;
the console reaches the host over its console network, which may be Ethernet.
The dev board IP is not automatically the right host address for the console.
The Flipper USB keyboard link only enters text; it does not provide a console
network stack or a direct Switch filesystem upload API.

FlippyKB's original HBLauncher-compatible delivery helper remains available as
`flippykb.session` for protocol tests. Its `deliver()` function assumes the caller
owns the listener and lifecycle; use the CLI/shared guard for one-use launches.
