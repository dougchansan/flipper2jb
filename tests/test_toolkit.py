import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flippykb.__main__ import main, remote_path
from flippykb.keyboard import compile_bas, replay
from flippykb.rpc import decode, vi
from test_transport import FakeRPC


class CompilerTests(unittest.TestCase):
    def test_editor_roundtrip_autoindent_blank_lines_punctuation(self):
        source = "  ' AaZz 001122\r\n\r\n    PRINT \"#$&():,<>=+-*/[]{}!?\"\r\nEND"
        for ms in [20, 35, 50, 75, 100, 250]:
            data, seconds, expected = compile_bas(source, ms)
            self.assertEqual(replay(data), source.replace('\r\n', '\n') + '\n')
            self.assertEqual(expected, replay(data))
            self.assertGreater(seconds, 5)
            self.assertEqual(data.count(b'HOLD HOME'), 4)

    def test_reject_untypable_or_invalid_input(self):
        for source in ['', '\tPRINT 1', 'PRINT "é"', 'X\rY', '\0']:
            with self.assertRaises(ValueError): compile_bas(source)
        for ms in [True, 19, 251, 50.0]:
            with self.assertRaises(ValueError): compile_bas('END', ms)

    def test_offline_compile_private_outputs_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); src = root/'source.bas'; src.write_text('END\n')
            out = root/'out.txt'
            with patch('flippykb.__main__.RPC', side_effect=AssertionError('offline')):
                with contextlib.redirect_stdout(io.StringIO()): main(['compile', str(src), '-o', str(out)])
            manifest = json.loads(Path(str(out)+'.json').read_text())
            self.assertTrue(manifest['physical_key_roundtrip'])
            self.assertEqual(out.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError): main(['compile', str(src), '-o', str(out)])



class TransportTests(unittest.TestCase):
    def test_malformed_protobuf_rejected(self):
        for data in [b'\x80', b'\x0a\x03x', b'\x00\x01', b'\x0b']:
            with self.assertRaises(ValueError): decode(data)
        for value in [-1, 2**64, True]:
            with self.assertRaises(ValueError): vi(value)

    def test_paths_cannot_escape_badusb(self):
        for name in ['/ext/badusb/../settings.txt', '/int/x.txt', '/ext/badusb/x.bin']:
            with self.assertRaises(ValueError): remote_path(name)
        self.assertEqual(remote_path('/ext/badusb/a.txt'), '/ext/badusb/a.txt')

    def test_cli_upload_verifies_without_starting(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory)/'script.txt'; script.write_bytes(b'REM test\n' * 100)
            rpc = FakeRPC(); rpc.close = lambda: None
            with patch('flippykb.__main__.RPC', return_value=rpc):
                with contextlib.redirect_stdout(io.StringIO()): main(['upload', str(script)])
            self.assertEqual(rpc.calls, [])
            self.assertEqual(rpc.data, script.read_bytes())

    def test_cli_corrupt_readback_and_lost_start_never_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory)/'script.txt'; script.write_bytes(b'REM test\n')
            for rpc in [FakeRPC(corrupt=True), FakeRPC(fail=16)]:
                rpc.close = lambda: None
                with patch('flippykb.__main__.RPC', return_value=rpc):
                    with contextlib.redirect_stdout(io.StringIO()):
                        with self.assertRaises(RuntimeError): main(['run', str(script), '--ready'])
                self.assertLessEqual(rpc.calls.count(16), 1)
                self.assertNotIn(23, rpc.calls)



if __name__ == '__main__': unittest.main()
