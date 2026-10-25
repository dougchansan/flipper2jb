"""Optional SmileBASIC bootstrap and active-host keyboard adapter."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import time
import uuid
from ..__main__ import private_write, verify_layout
from ..keyboard import compile_bas, LAYOUT
from ..rpc import RPC, blob, integer
from ..transfer import upload

MARKER = b'REM FLIPPER2JB TARGET NS2JB; fresh session only\n'


def validate_command(command):
    if not re.fullmatch(r'V=START\([0-9]+(?:,[0-9]+){8}\)', command):
        raise ValueError('invalid host command')
    values = [int(v) for v in command[8:-1].split(',')]
    if values[0] != 39380 or any(v > 255 for v in values[1:5]) or any(v >= 2**64 for v in values[5:]):
        raise ValueError('invalid host parameters')
    return command


def active_command(path):
    path = Path(path)
    if path.stat().st_size > 4096:
        raise ValueError('active file too large')
    lines = path.read_text().splitlines()
    if len(lines) != 2 or not re.fullmatch(r'[0-9]{1,10}', lines[0]):
        raise ValueError('invalid active host record')
    pid = int(lines[0])
    if not 1 < pid <= 2147483647:
        raise ValueError('invalid host process')
    os.kill(pid, 0)
    return pid, validate_command(lines[1])


def session_script(command, name='NS2', ms=50):
    validate_command(command)
    if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,15}', name):
        raise ValueError('invalid saved program name')
    if type(ms) is not int or not 20 <= ms <= 250:
        raise ValueError('key timing must be 20..250 ms')
    layout = LAYOUT.read_bytes()
    commands = [MARKER.decode().rstrip(), 'DELAY 5000']

    def key(k, shift=False, delay=ms):
        if shift: commands.extend(['HOLD SHIFT', f'DELAY {delay}'])
        commands.extend(['HOLD '+k, f'DELAY {delay}', 'RELEASE '+k, f'DELAY {delay}'])
        if shift: commands.extend(['RELEASE SHIFT', f'DELAY {delay}'])

    steps = [(f'LOAD "TXT:{name}"', 3000), ('', 3000), ('RUN', 3000),
             ('REMOVE NSR,&H60000000,&H3FFFFFFF', 6000), (command, 0)]
    for line, pause in steps:
        for char in line:
            usage = struct.unpack_from('<H', layout, ord(char)*2)[0]
            if not usage or usage >> 8 not in (0, 2):
                raise ValueError('unsupported physical key')
            key('SPACE' if char == ' ' else char, bool(usage >> 8))
        key('ENTER', delay=100)
        if pause: commands.append(f'DELAY {pause}')
    seconds = sum(int(c.split()[1]) for c in commands if c.startswith('DELAY '))/1000
    return ('\n'.join(commands)+'\n').encode(), seconds


def latch_path():
    # Interoperate with the existing local host adapter's consumed-session latch.
    return Path(os.environ.get('HB_SESSION_LATCH', Path.home()/'.local/state/hblauncher/console-session.json'))


def claim(host_pid):
    path = latch_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump({'pid': os.getpid(), 'hostPid': host_pid, 'restartRequired': True}, stream)
        stream.flush(); os.fsync(stream.fileno())


def reset():
    path = latch_path()
    state = json.loads(path.read_text())
    for pid in {state['pid'], state.get('hostPid', state['pid'])}:
        if type(pid) is not int or pid <= 1:
            raise ValueError('invalid latch process')
        try: os.kill(pid, 0)
        except ProcessLookupError: continue
        raise ValueError('recorded sender or host still running')
    path.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default=os.environ.get('FLIPPER_WIFI_HOST', '192.168.4.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('FLIPPER_WIFI_PORT', '8080')))
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('bootstrap', help='compile caller-supplied bootstrap.bas; offline')
    p.add_argument('source', type=Path); p.add_argument('-o', '--output', type=Path, required=True)
    p.add_argument('--key-ms', type=int, default=50)
    for action, help_text in [('session', 'prepare a private one-use script from a live host record'),
                              ('start', 'generate and send a fresh session sequence once')]:
        p = sub.add_parser(action, help=help_text)
        p.add_argument('--active-file', type=Path, required=True)
        p.add_argument('--name', default='NS2'); p.add_argument('--key-ms', type=int, default=50)
        if action == 'session': p.add_argument('-o', '--output', type=Path, required=True)
        else: p.add_argument('--ready', action='store_true', required=True,
                            help='confirm fresh console process, Direct mode, saved NS2, Caps Lock off, Flipper desktop')
    p = sub.add_parser('reset', help='rearm only after stopping hosts/Bad KB and restarting console')
    p.add_argument('--confirm-console-restarted', action='store_true', required=True)
    args = parser.parse_args(argv)
    if args.action == 'reset':
        reset(); print('Latch reset after confirmed console restart'); return
    if args.action == 'bootstrap':
        source = args.source.read_bytes()
        data, seconds, expected = compile_bas(source.decode('ascii'), args.key_ms)
        private_write(args.output, data)
        private_write(str(args.output)+'.json', (json.dumps({
            'target': 'ns2jb', 'source_sha256': hashlib.sha256(source).hexdigest(),
            'script_sha256': hashlib.sha256(data).hexdigest(), 'seconds': seconds,
            'typed_sha256': hashlib.sha256(expected.encode()).hexdigest(),
            'physical_key_roundtrip': True, 'key_ms': args.key_ms}, indent=2)+'\n').encode())
        print(f'Bootstrap text script created; estimated {seconds/60:.1f} minutes'); return
    pid, command = active_command(args.active_file)
    data, seconds = session_script(command, args.name, args.key_ms)
    if args.action == 'session':
        private_write(args.output, data)
        print('Private one-use script created for review. Use target start for guarded delivery.'); return
    rpc = RPC(args.host, args.port)
    try:
        verify_layout(rpc)
        if active_command(args.active_file) != (pid, command):
            raise ValueError('active host changed')
        # Consume before upload/start; a failed or uncertain attempt is never rearmed here.
        claim(pid)
        remote = '/ext/badusb/Flipper2JB-NS2-'+uuid.uuid4().hex+'.txt'
        upload(rpc, remote, data)
        print('Fresh script exact readback verified:', remote)
        if active_command(args.active_file) != (pid, command):
            raise ValueError('active host changed during upload')
        rpc.request(16, blob(1, 'Bad KB')+blob(2, remote))
        time.sleep(2)
        for typ in (0, 2, 1): rpc.request(23, integer(1, 4)+integer(2, typ))
        print('Fresh script readback and start input acknowledged:', remote)
        print(f'Estimated typing interval: {seconds:.1f} seconds. Only the host can confirm authentication.')
        print('Close Bad KB before deleting the script. Never replay it. No automatic retry.')
    finally: rpc.close()


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, RuntimeError, EOFError, KeyError, IndexError):
        print('Target operation failed; no automatic retry. If delivery was attempted, stop Bad KB and restart the console before another session.', file=sys.stderr)
        sys.exit(1)
