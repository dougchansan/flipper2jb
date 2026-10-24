import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import time
import uuid
from .keyboard import compile_bas, LAYOUT
from .checker import checker
from .rpc import RPC, blob, integer, decode, first
from .session import upload, program


def private_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)


def remote_path(value):
    p = PurePosixPath(value)
    if not value.startswith('/ext/badusb/') or '..' in p.parts or len(p.parts) < 4 or not value.endswith('.txt'):
        raise ValueError('script path must be /ext/badusb/<name>.txt without traversal')
    return value


def verify_layout(rpc):
    import re
    settings = rpc.read('/ext/badusb/.badkb.settings').decode()
    layout = re.search(r'^layout: (.+)$', settings, re.M)
    if not layout or not layout[1].strip().endswith('/en-UK.kl'):
        raise ValueError('Flipper must use the tested en-UK layout')
    if rpc.read(layout[1].strip()) != LAYOUT.read_bytes():
        raise ValueError('Flipper keyboard layout bytes differ')
    if not re.search(r'^interface: 0\s*$', settings, re.M):
        raise ValueError('Flipper must use USB keyboard mode')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Flipper Wi-Fi → USB keyboard tools for SmileBASIC')
    parser.add_argument('--host', default=os.environ.get('FLIPPER_WIFI_HOST', '192.168.4.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('FLIPPER_WIFI_PORT', '8080')))
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('compile', help='BAS → Bad KB script; offline')
    p.add_argument('source', type=Path); p.add_argument('-o', '--output', required=True, type=Path)
    p.add_argument('--key-ms', type=int, default=50)
    p = sub.add_parser('checker', help='generate a BAS saved-source checker; offline')
    p.add_argument('source', type=Path); p.add_argument('-o', '--output', required=True, type=Path)
    p.add_argument('--name', default='NS2')
    p = sub.add_parser('session', help='generate host-provided V=START sequence from stdin; offline')
    p.add_argument('-o', '--output', required=True, type=Path); p.add_argument('--name', default='NS2')
    p.add_argument('--key-ms', type=int, default=50)
    p = sub.add_parser('reset-session', help='rearm only after stopping hosts/Bad KB and restarting console')
    p.add_argument('--confirm-console-restarted', required=True, action='store_true')
    sub.add_parser('ping', help='check protobuf echo on the existing bridge')
    sub.add_parser('inspect', help='verify keyboard layout and USB interface')
    p = sub.add_parser('capture', help='capture Flipper display (not the Switch display)')
    p.add_argument('output', type=Path)
    p = sub.add_parser('upload', help='upload with exact readback; does not start typing')
    p.add_argument('script', type=Path); p.add_argument('--remote')
    p = sub.add_parser('run', help='upload, verify and start Bad KB once')
    p.add_argument('script', type=Path); p.add_argument('--remote')
    p.add_argument('--ready', required=True, action='store_true', help='confirm correct editor/Direct mode, Caps Lock off, Flipper desktop')
    p = sub.add_parser('remove', help='remove one generated script after closing Bad KB')
    p.add_argument('remote')
    args = parser.parse_args(argv)
    if args.action in ('compile', 'checker', 'session'):
        if args.action == 'compile':
            source = args.source.read_bytes().decode('ascii')
            data, seconds, expected = compile_bas(source, args.key_ms)
            manifest = {'source_sha256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
                        'typed_sha256': hashlib.sha256(expected.encode()).hexdigest(),
                        'script_sha256': hashlib.sha256(data).hexdigest(), 'key_ms': args.key_ms,
                        'navigation_ms': 100, 'seconds': seconds, 'physical_key_roundtrip': True}
        elif args.action == 'checker':
            data = checker(args.source.read_bytes().decode('ascii'), args.name).encode('ascii')
            manifest = None
        else:
            data, seconds = program(sys.stdin.read().strip(), args.name, args.key_ms)
            manifest = {'seconds': seconds, 'fresh_session_only': True}
        # Session scripts can contain pairing tokens; keep every generated file private.
        private_write(args.output, data)
        if manifest is not None:
            private_write(str(args.output) + '.json', (json.dumps(manifest, indent=2) + '\n').encode())
        print('Created', args.output)
        if manifest and 'seconds' in manifest:
            print(f"Estimated typing time: {manifest['seconds'] / 60:.1f} minutes")
        return
    if args.action == 'reset-session':
        from .guard import reset
        reset()
        print('Session latch reset after confirmed console restart')
        return
    # Validate inputs before opening any network connection.
    data = None
    if args.action in ('upload', 'run'):
        data = args.script.read_bytes()
        if not data:
            raise ValueError('empty script')
        remote = remote_path(args.remote or '/ext/badusb/FlippyKB-' + uuid.uuid4().hex + '.txt')
    elif args.action == 'remove':
        remote = remote_path(args.remote)
    elif args.action == 'capture' and args.output.exists():
        raise ValueError('capture destination already exists')
    rpc = RPC(args.host, args.port)
    try:
        if args.action == 'ping':
            token = os.urandom(16)
            replies = rpc.request(5, blob(1, token))
            if not any(first(decode(first(d, 6, b'')), 1, b'') == token for d in replies):
                raise RuntimeError('ping echo mismatch')
            print('Bridge protobuf echo verified')
        elif args.action == 'inspect':
            verify_layout(rpc)
            print('Tested en-UK layout and USB interface verified')
        elif args.action == 'capture':
            rpc.capture(args.output)
            os.chmod(args.output, 0o600)
            print('Saved Flipper display:', args.output)
        elif args.action == 'remove':
            rpc.request(12, blob(1, remote))
            print('Removed', remote)
        else:
            if args.action == 'run':
                verify_layout(rpc)
            if args.action == 'run' and data.startswith(b'REM Fresh HBLauncher session; never replay'):
                from .guard import claim
                claim()
            upload(rpc, remote, data)
            print('Exact upload readback verified:', remote, flush=True)
            if args.action == 'run':
                rpc.request(16, blob(1, 'Bad KB') + blob(2, remote))
                time.sleep(2)
                for typ in (0, 2, 1):
                    rpc.request(23, integer(1, 4) + integer(2, typ))
                print('Start input acknowledged. Observe the Switch; RPC does not prove typing completed.')
                print('Close Bad KB before removing the remote script. Never replay a consumed session command.')
    finally:
        rpc.close()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, EOFError, IndexError, KeyError):
        # Exceptions from transport can include payloads; keep pairing data out of logs.
        print('Operation failed. No automatic retry. Check inputs, bridge and layout. If launch was attempted, stop Bad KB; restart the console before retrying a session.', file=sys.stderr)
        sys.exit(1)
