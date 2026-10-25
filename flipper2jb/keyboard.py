"""Generate and independently replay the tested en-UK physical-key sequence."""
import struct
from pathlib import Path

LAYOUT = Path(__file__).resolve().parents[1] / 'assets/en-UK.kl'


def compile_bas(source, ms=50):
    if type(ms) is not int or not 20 <= ms <= 250:
        raise ValueError('key timing must be 20..250 ms')
    source = source.replace('\r\n', '\n')
    if '\r' in source or not source or any(c != '\n' and not 32 <= ord(c) <= 126 for c in source):
        raise ValueError('source must be nonempty printable ASCII with LF or CRLF newlines')
    # Retain blank lines and normalize the final newline for text entry.
    expected = source if source.endswith('\n') else source + '\n'
    layout = LAYOUT.read_bytes()
    commands = ['REM Editor text entry only; no RUN or SAVE.',
                'REM en-UK USB; Caps Lock OFF; empty editor at first line.', 'DELAY 5000']

    def key(k, shift=False, delay=ms):
        if shift:
            commands.extend(['HOLD SHIFT', f'DELAY {delay}'])
        commands.extend(['HOLD ' + k, f'DELAY {delay}', 'RELEASE ' + k, f'DELAY {delay}'])
        if shift:
            commands.extend(['RELEASE SHIFT', f'DELAY {delay}'])

    for line in expected.splitlines():
        for ch in line:
            code = struct.unpack_from('<H', layout, ord(ch) * 2)[0]
            if not code or code >> 8 not in (0, 2):
                raise ValueError('character not supported by tested keymap')
            key('SPACE' if ch == ' ' else ch, bool(code >> 8))
        # Clear inherited indentation, including the empty final editor line.
        key('ENTER', delay=100)
        key('HOME', delay=100)
        key('END', True, 100)
        key('SPACE', delay=100)
        key('BACKSPACE', delay=100)
    data = ('\n'.join(commands) + '\n').encode('ascii')
    if replay(data) != expected:
        raise ValueError('physical-key replay did not reproduce source')
    seconds = sum(int(c.split()[1]) for c in commands if c.startswith('DELAY ')) / 1000
    return data, seconds, expected


def replay(data):
    layout = LAYOUT.read_bytes()
    lookup = {struct.unpack_from('<H', layout, c*2)[0]: chr(c) for c in range(32, 127)}
    rows, cursor, selection, shift, held = [''], 0, None, False, set()
    for command in data.decode('ascii').splitlines():
        if command.startswith(('REM ', 'DELAY ')):
            continue
        action, key = command.split(' ', 1)
        if action == 'RELEASE':
            held.remove(key)
            if key == 'SHIFT':
                shift = False
            continue
        if action != 'HOLD' or key in held:
            raise ValueError('invalid key transition')
        held.add(key)
        if key == 'SHIFT':
            shift = True
        elif key == 'ENTER':
            if cursor != len(rows[-1]) or selection is not None:
                raise ValueError('unexpected editor cursor')
            indent = len(rows[-1]) - len(rows[-1].lstrip(' '))
            rows.append(' ' * indent)
            cursor = indent
        elif key == 'HOME':
            cursor, selection = 0, None
        elif key == 'END':
            selection = (cursor, len(rows[-1])) if shift else None
            cursor = len(rows[-1])
        elif key == 'BACKSPACE':
            if cursor == 0 or selection is not None:
                raise ValueError('unexpected backspace')
            rows[-1] = rows[-1][:cursor-1] + rows[-1][cursor:]
            cursor -= 1
        else:
            ch = ' ' if key == 'SPACE' else key
            code = struct.unpack_from('<H', layout, ord(ch)*2)[0] & 255
            text = lookup[code | (512 if shift else 0)]
            start, end = selection if selection is not None else (cursor, cursor)
            rows[-1] = rows[-1][:start] + text + rows[-1][end:]
            cursor, selection = start + 1, None
    if held:
        raise ValueError('keys left held')
    return '\n'.join(rows)
