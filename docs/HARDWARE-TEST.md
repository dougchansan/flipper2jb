# Supervised Bluetooth typing and auto-close — 2026-10-24

**Passed:** Bluetooth RPC, script upload/readback, USB keyboard text entry at
50 ms, and timed Bad KB closing on the user's physical setup.

## Procedure and evidence

- The Mac discovered and paired with the Flipper over BLE. An initial RPC check
  did not pass before pairing was completed; no keyboard input occurred then.
- After the user confirmed pairing, protobuf ping passed and the exact included
  en-UK layout and USB keyboard interface were verified.
- One generated text script was uploaded over BLE with exact byte readback.
  It entered two BASIC comment lines in an empty SmileBASIC editor:

  ```basic
  ' BLE 50ms OK
    ' AaZz 0123 "#$&():,+-*/
  ```

- The generated script contained 12.8 seconds of explicit delays at the default
  50 ms character timing. Auto-close used a planned 22.8-second wait including
  the minimum 10-second buffer, plus RPC/polling overhead.
- One Bad KB start sequence was acknowledged. After waiting and checking the
  screen header, the tool sent one Back sequence. Loader status then confirmed
  that the Flipper application had exited. A subsequent Flipper screen capture
  showed its ordinary settings UI rather than Bad KB.
- The user confirmed both lines matched, including indentation, case and
  punctuation, and that the app closed automatically without a manual Back press.
- The temporary remote script was removed after application exit. Source, expected
  text, diagnostic data and the post-close frame remain in ignored private runs.

No BASIC program was run or saved. No firmware was flashed, no target session
was started, and no one-shot target latch was consumed or reset.

## Scope

This establishes the short general text-entry/auto-close path on this setup.
It does not establish sustained reliability for a full bootstrap, the optional
post-bootstrap target sequence, other firmware versions or other target editors.
The remote script's removal is cleanup of this test, not a change to normal run
behavior: normal auto-close retains its remote file.

Auto-close remains timed. It checks for a changed screen header and verifies app
exit, but does not receive a script-completion acknowledgment. Pauses or stalls
that leave the header unchanged can still be interrupted. `--keep-open` is
available when timed closing is unsuitable.
