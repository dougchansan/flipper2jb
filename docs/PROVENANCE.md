# Provenance

Repository assembled on 2026-10-23 from the existing local Switch/Flipper workflow.

| Component | Source |
| --- | --- |
| TCP protobuf framing, storage reads, display capture | local validated `switch2/wifi-bridge-review-*/rpc_client.py` |
| Session key sequence and 512-byte upload/readback | local `HBLauncher-macos-flipper/smilebasic/keyboard/flipper.py` |
| en-UK physical layout | existing UK typing trial asset |
| BAS compiler editor navigation | existing `switch2/flipper-speed-tests-*` generator and full bootstrap 50 ms script |
| Saved-source checker | existing `switch2/source-checker-tools/build_checker.py`, adapted into reusable generator |
| USB CLI upload fallback | existing full bootstrap 50 ms `upload-usb.py`, parameterized device/path |
| ESP32-S2 firmware | local `switch2/wifi-bridge-review-*/build-source` |

The upstream bridge is [busse/flipperzero-mcp](https://github.com/busse/flipperzero-mcp)
at `36948b7ffb03e46fb352394363e327d953706a9d`. Its MIT notice is preserved in
[firmware/LICENSE](../firmware/LICENSE). Local C modifications predate this repo:
AP-only private WPA2/PMF, one AP/TCP client, atomic UART writes, DATA ACKs,
heartbeat handling, presence signaling without UART driver deletion, deferred LED
startup, partial TCP sends and double-close handling. This repo adds compile-time
AP credential length checks and removes the fallback AP password from Kconfig.
Trailing whitespace in imported files was normalized. Configuration defaults retain the deployed UART rate of 115200. Generated
sdkconfig and original firmware images are not copied.

The host runtime is [ravensclawx/HBLauncher](https://github.com/ravensclawx/HBLauncher),
upstream base `9d00834f3636639d9d9df54cb3e1fb10456b2467`; FlippyKB extracts the
locally added transport adapter rather than bundling the SDK/runtime.
The bootstrap comes from [pepsipu/ns2jb](https://gitlab.com/pepsipu/ns2jb), reference
`95f5525089273c5fce0b95047f3600f8442e96ae`. Supply that source from your existing
checkout; this repository does not redistribute bootstrap or native payloads.

Reference SHA-256 values:

```text
bootstrap.bas:
2261f65fb9ec0ed708ce0f0b6da5057168f706e541d956f658a3c2655e9e8c36
original rpc_client.py (before parameterization and decoder checks):
f913b76251ed31db54bfb7b946f044097db905ff89f59bfe9469ba8af0b9316b
en-UK.kl (copied unchanged):
2fbb1e7f3e144050339157d989e03f12e734e2defdedded28dfd7f9a2b6c903c
```

[firmware-source-sha256.json](firmware-source-sha256.json) records the included
firmware source hashes. Credentials, hardware identifiers, AP password, original
flash/NVS, private serial transcripts, captured screens, SDK/memory dumps and
previous host pairing commands are excluded.

New Python changes: configurable TCP host/port; bounded/truncation-aware decoding;
CLI; reusable compiler with independent editor replay; checker generator;
shared session latch; private generated outputs; input validation; offline tests.
Imports and offline commands do not open network connections.
