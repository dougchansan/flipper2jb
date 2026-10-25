"""Generic storage/keyboard tests; all connections stay on loopback."""
import contextlib
import io
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch
from flippykb.__main__ import main
from flippykb.keyboard import compile_bas, LAYOUT
from flippykb.rpc import RPC, blob, decode, first, integer, vi
from flippykb.transfer import upload


class FakeSocket:
    def __init__(self, rpc): self.rpc = rpc

    def sendall(self, frame):
        length = shift = offset = 0
        while True:
            value = frame[offset]; offset += 1
            length |= (value & 127) << shift; shift += 7
            if value < 128: break
        if len(frame[offset:]) != length: raise AssertionError('frame size')
        fields = decode(frame[offset:])
        query = decode(first(fields, 11))
        chunk = first(decode(first(query, 2)), 4)
        if len(chunk) > 512: raise AssertionError('chunk size')
        self.rpc.data += chunk
        self.rpc.more.append(first(fields, 3))
        self.rpc.ids.append(first(fields, 1))


class FakeRPC:
    def __init__(self, corrupt=False, fail=None):
        self.ident, self.data = 1, b''
        self.more, self.calls, self.ids = [], [], []
        self.corrupt, self.fail = corrupt, fail
        self.s = FakeSocket(self)

    def receive(self): return {1: [self.ident]}

    def read(self, path):
        if path.endswith('.settings'):
            return b'layout: /ext/badusb/assets/layouts/en-UK.kl\ninterface: 0\n'
        if path.endswith('.kl'): return LAYOUT.read_bytes()
        return b'bad' if self.corrupt else self.data

    def request(self, tag, payload):
        self.calls.append(tag)
        if tag == self.fail: raise RuntimeError('simulated lost acknowledgment')
        return []

    def close(self): pass


class StorageTests(unittest.TestCase):
    def test_chunking_and_exact_readback_use_one_command_id(self):
        rpc = FakeRPC()
        data = b'REM transport test\n' * 100
        upload(rpc, '/ext/badusb/test.txt', data)
        self.assertEqual(rpc.data, data)
        self.assertEqual(set(rpc.ids), {rpc.ident})
        self.assertTrue(all(rpc.more[:-1]))
        self.assertEqual(rpc.more[-1], 0)

    def test_empty_upload_never_sends(self):
        rpc = FakeRPC()
        with self.assertRaises(ValueError): upload(rpc, '/ext/badusb/test.txt', b'')
        self.assertEqual(rpc.more, [])

    def test_storage_error_is_reported(self):
        rpc = FakeRPC()
        rpc.receive = lambda: {1: [rpc.ident], 2: [9]}
        with self.assertRaises(RuntimeError): upload(rpc, '/ext/badusb/test.txt', b'REM test\n')

    def test_readback_mismatch_is_reported(self):
        with self.assertRaises(RuntimeError):
            upload(FakeRPC(corrupt=True), '/ext/badusb/test.txt', b'REM test\n')

    def test_bad_layout_never_uploads_or_starts(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory)/'test.txt'; script.write_bytes(b'REM test\n')
            for settings in [b'layout: /ext/en-US.kl\ninterface: 0\n',
                             b'layout: /ext/en-UK.kl\ninterface: 1\n']:
                rpc = FakeRPC()
                rpc.read = lambda path: settings if path.endswith('.settings') else LAYOUT.read_bytes()
                with patch('flippykb.__main__.RPC', return_value=rpc):
                    with self.assertRaises(ValueError): main(['run', str(script), '--ready'])
                self.assertFalse(rpc.more)
                self.assertFalse(rpc.calls)


class SocketIntegration(unittest.TestCase):
    def test_all_network_commands_over_fragmented_loopback(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0)); listener.listen(); listener.settimeout(5)
        address = listener.getsockname()
        files, seen, errors = {}, [], []
        image = bytes([0xff]) * 1024

        def serve():
            try:
                # ping, inspect, upload, run, capture, remove use separate connections.
                for _ in range(6):
                    conn, _ = listener.accept(); conn.settimeout(5)
                    reader = object.__new__(RPC); reader.s = conn
                    try:
                        while True:
                            try: request = reader.receive()
                            except EOFError: break
                            ident = first(request, 1)
                            tag = next(k for k in request if k not in (1, 2, 3)); seen.append(tag)
                            query = decode(first(request, tag))
                            bodies = [blob(4, b'')]
                            if tag == 5:
                                bodies = [blob(6, blob(1, first(query, 1)))]
                            elif tag == 11:
                                path = first(query, 1).decode()
                                files[path] = files.get(path, b'') + first(decode(first(query, 2)), 4)
                                if first(request, 3): continue
                            elif tag == 9:
                                path = first(query, 1).decode()
                                if path.endswith('.settings'):
                                    data = b'layout: /ext/en-UK.kl\ninterface: 0\n'
                                elif path.endswith('.kl'): data = LAYOUT.read_bytes()
                                else: data = files[path]
                                bodies = [blob(10, blob(1, blob(4, data[i:i+1024])))
                                          for i in range(0, len(data), 1024)]
                            elif tag == 12:
                                del files[first(query, 1).decode()]
                            for i, body in enumerate(bodies):
                                reply = integer(1, ident) + integer(3, int(i+1 < len(bodies))) + body
                                frame = vi(len(reply)) + reply
                                conn.sendall(frame[:1]); conn.sendall(frame[1:])
                            if tag == 20:
                                event = integer(1, 0) + blob(22, blob(1, image))
                                conn.sendall(vi(len(event)) + event)
                    finally: conn.close()
            except Exception as error: errors.append(error)
            finally: listener.close()

        thread = threading.Thread(target=serve, daemon=True); thread.start()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); script = root/'test.txt'
            data, _, _ = compile_bas('PRINT "FlippyKB"\nEND\n')
            script.write_bytes(data)
            args = ['--host', address[0], '--port', str(address[1])]
            with contextlib.redirect_stdout(io.StringIO()), patch('flippykb.__main__.time.sleep'):
                main(args + ['ping'])
                main(args + ['inspect'])
                main(args + ['upload', str(script), '--remote', '/ext/badusb/upload.txt'])
                self.assertEqual(files['/ext/badusb/upload.txt'], data)
                self.assertNotIn(16, seen)
                main(args + ['run', str(script), '--remote', '/ext/badusb/run.txt', '--ready'])
                main(args + ['capture', str(root/'flipper.pbm')])
                main(args + ['remove', '/ext/badusb/upload.txt'])
            self.assertEqual((root/'flipper.pbm').read_bytes(), b'P4\n128 64\n' + image)
            self.assertEqual((root/'flipper.pbm').stat().st_mode & 0o777, 0o600)
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors, errors)
        self.assertEqual(seen.count(16), 1)
        self.assertEqual(seen.count(23), 3)
        self.assertNotIn('/ext/badusb/upload.txt', files)


if __name__ == '__main__': unittest.main()
