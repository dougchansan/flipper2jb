import contextlib
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from flipper2jb.__main__ import main as general_main
from flipper2jb.keyboard import LAYOUT
from flipper2jb.targets import ns2jb
from test_transport import FakeRPC

COMMAND = 'V=START(39380,127,0,0,1,11,22,33,44)'


def typed_text(script):
    layout = LAYOUT.read_bytes()
    lookup = {struct.unpack_from('<H', layout, c*2)[0]: chr(c) for c in range(32,127)}
    held, shift, text = set(), False, ''
    for line in script.decode().splitlines():
        if line.startswith('HOLD '):
            key = line[5:]
            if key in held: raise AssertionError('duplicate key hold')
            held.add(key)
            if key == 'SHIFT': shift = True
            elif key == 'ENTER': text += '\n'
            else:
                char = ' ' if key == 'SPACE' else key
                code = struct.unpack_from('<H', layout, ord(char)*2)[0] & 255
                text += lookup[code | (512 if shift else 0)]
        elif line.startswith('RELEASE '):
            key = line[8:]; held.remove(key)
            if key == 'SHIFT': shift = False
    if held: raise AssertionError('held keys remain')
    return text


class TargetTests(unittest.TestCase):
    def test_physical_keys_reproduce_order_and_load_confirmation(self):
        script, seconds = ns2jb.session_script(COMMAND)
        self.assertTrue(script.startswith(ns2jb.MARKER))
        self.assertEqual(typed_text(script), 'LOAD "TXT:NS2"\n\nRUN\nREMOVE NSR,&H60000000,&H3FFFFFFF\n'+COMMAND+'\n')
        self.assertGreater(seconds, 20)

    def test_start_parameters_are_strictly_validated(self):
        for command in ['RUN', COMMAND+'\n', COMMAND.replace('39380','80'),
                        COMMAND.replace('127','256'), 'V=START(1)',
                        COMMAND.replace('44', str(2**64))]:
            with self.assertRaises(ValueError): ns2jb.validate_command(command)
        with self.assertRaises(ValueError): ns2jb.session_script(COMMAND, name='BAD"\nRUN')
        with self.assertRaises(ValueError): ns2jb.session_script(COMMAND, ms=0)

    def test_active_file_requires_matching_live_pid_and_two_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'active.txt'
            path.write_text(f'{os.getpid()}\n{COMMAND}\n')
            self.assertEqual(ns2jb.active_command(path), (os.getpid(), COMMAND))
            path.write_text('2147483647\n'+COMMAND+'\n')
            with self.assertRaises(ProcessLookupError): ns2jb.active_command(path)
            path.write_text(f'{os.getpid()}\n{COMMAND}\nextra\n')
            with self.assertRaises(ValueError): ns2jb.active_command(path)

    def test_review_script_is_private_and_general_run_refuses_before_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); active = root/'active.txt'; out = root/'review.txt'
            active.write_text(f'{os.getpid()}\n{COMMAND}\n')
            with contextlib.redirect_stdout(io.StringIO()) as log:
                ns2jb.main(['session','--active-file',str(active),'-o',str(out)])
            self.assertEqual(out.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(COMMAND, log.getvalue())
            with patch('flipper2jb.__main__.RPC', side_effect=AssertionError('should not connect')):
                with self.assertRaises(ValueError): general_main(['run',str(out),'--ready'])

    def test_bootstrap_preparation_uses_caller_source_without_device_io(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'bootstrap.bas'; out = root/'script.txt'
            source.write_text('PRINT "READY"\nEND\n')
            with patch.object(ns2jb,'RPC',side_effect=AssertionError('offline')), contextlib.redirect_stdout(io.StringIO()):
                ns2jb.main(['bootstrap',str(source),'-o',str(out)])
            manifest = json.loads(Path(str(out)+'.json').read_text())
            self.assertTrue(manifest['physical_key_roundtrip'])
            self.assertEqual(manifest['target'],'ns2jb')

    def test_start_consumes_latch_and_never_retries_lost_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); active = root/'active.txt'; latch = root/'latch.json'
            active.write_text(f'{os.getpid()}\n{COMMAND}\n')
            rpc = FakeRPC(fail=16)
            args = ['start','--active-file',str(active),'--ready']
            with patch.dict(os.environ,{'HB_SESSION_LATCH':str(latch)}), patch.object(ns2jb,'RPC',return_value=rpc), contextlib.redirect_stdout(io.StringIO()) as log:
                with self.assertRaises(RuntimeError): ns2jb.main(args)
                self.assertTrue(latch.exists())
                self.assertEqual(rpc.calls,[16])
                rpc.calls.clear()
                with self.assertRaises(FileExistsError): ns2jb.main(args)
                self.assertEqual(rpc.calls,[])
                self.assertNotIn(COMMAND,log.getvalue())

    def test_host_change_during_upload_blocks_start_and_retains_latch(self):
        with tempfile.TemporaryDirectory() as directory:
            latch = Path(directory)/'latch.json'; rpc = FakeRPC()
            states = [(os.getpid(),COMMAND),(os.getpid(),COMMAND),(os.getpid(),COMMAND.replace('44','45'))]
            with patch.dict(os.environ,{'HB_SESSION_LATCH':str(latch)}), patch.object(ns2jb,'RPC',return_value=rpc), patch.object(ns2jb,'active_command',side_effect=states), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ValueError): ns2jb.main(['start','--active-file','synthetic','--ready'])
            self.assertTrue(latch.exists()); self.assertEqual(rpc.calls,[])

    def test_successful_start_sends_one_start_and_input_sequence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); active = root/'active.txt'; latch = root/'latch.json'
            active.write_text(f'{os.getpid()}\n{COMMAND}\n'); rpc = FakeRPC()
            with patch.dict(os.environ,{'HB_SESSION_LATCH':str(latch)}), patch.object(ns2jb,'RPC',return_value=rpc), patch.object(ns2jb.time,'sleep'), contextlib.redirect_stdout(io.StringIO()):
                ns2jb.main(['start','--active-file',str(active),'--ready'])
            self.assertEqual(rpc.calls,[16,23,23,23]); self.assertTrue(latch.exists())

    def test_reset_requires_sender_and_host_stopped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'latch.json'
            with patch.dict(os.environ,{'HB_SESSION_LATCH':str(path)}):
                path.write_text(json.dumps({'pid':2147483647,'hostPid':os.getpid()}))
                with self.assertRaises(ValueError): ns2jb.reset()
                self.assertTrue(path.exists())
                path.write_text(json.dumps({'pid':2147483647,'hostPid':2147483647}))
                ns2jb.reset(); self.assertFalse(path.exists())


if __name__ == '__main__': unittest.main()
