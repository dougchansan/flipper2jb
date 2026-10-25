import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flipper2jb import autoclose, ble
from flipper2jb.__main__ import main
from flipper2jb.keyboard import compile_bas
from flipper2jb.rpc import blob, decode, first, integer
from flipper2jb.targets import ns2jb
from test_ble import FakeBackend, DEVICE, COMMAND
from test_transport import FakeRPC

FRAME = b'A'*128+b'\0'*896


class LifecycleRPC(FakeRPC):
    def __init__(self):
        super().__init__()
        self.locked = True
        self.frames = [FRAME]
        self.inputs = []
        self.refuse_close = False

    def screen_frame(self):
        return self.frames.pop(0) if len(self.frames)>1 else self.frames[0]

    def request(self,tag,payload):
        self.calls.append(tag)
        if tag==self.fail: raise RuntimeError('lost acknowledgment')
        if tag==17: return [{18:[integer(1,int(self.locked))]}]
        if tag==23:
            data = decode(payload); key,event = first(data,1),first(data,2)
            self.inputs.append((key,event))
            if key==5 and event==2 and not self.refuse_close: self.locked=False
        return []


class AutoCloseTests(unittest.TestCase):
    def test_only_bounded_generated_scripts_are_automatically_timed(self):
        data,seconds,_=compile_bas('PRINT "OK"\nEND\n')
        self.assertEqual(autoclose.enabled_duration(data),seconds)
        self.assertIsNone(autoclose.enabled_duration(data,False))
        self.assertIsNone(autoclose.enabled_duration(b'REM Custom\nWAIT_FOR_BUTTON_PRESS\n'))
        with self.assertRaises(ValueError): autoclose.enabled_duration(b'REM Custom\n',True)
        for extra in [b'WAIT_FOR_BUTTON_PRESS\n',b'REPEAT 2\n',b'DEFAULT_DELAY 1000\n',b'HOLD SHIFT\n']:
            with self.assertRaises(ValueError): autoclose.duration(data+extra)

    def test_waits_for_duration_and_buffer_then_sends_back_once(self):
        rpc=LifecycleRPC(); delays=[]
        with patch.object(autoclose.time,'sleep',side_effect=delays.append),contextlib.redirect_stdout(io.StringIO()):
            autoclose.wait_and_close(rpc,100,autoclose.prepare(rpc))
        self.assertAlmostEqual(sum(delays),125)
        self.assertTrue(all(d<=5 for d in delays))
        self.assertEqual(rpc.inputs,[(5,0),(5,2),(5,1)])
        self.assertFalse(rpc.locked)

    def test_changed_screen_or_early_exit_never_sends_back(self):
        for changed in [True,False]:
            rpc=LifecycleRPC(); identity=autoclose.prepare(rpc)
            if changed: rpc.frames=[b'B'*1024]
            else: rpc.locked=False
            with patch.object(autoclose.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
                if changed:
                    with self.assertRaises(RuntimeError): autoclose.wait_and_close(rpc,1,identity)
                else: autoclose.wait_and_close(rpc,1,identity)
            self.assertFalse(rpc.inputs)

    def test_disconnect_or_cancellation_never_sends_exit_input(self):
        rpc=LifecycleRPC(); identity=autoclose.prepare(rpc)
        for error in [ConnectionError(),KeyboardInterrupt()]:
            with patch.object(autoclose.time,'sleep',side_effect=error),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(type(error)): autoclose.wait_and_close(rpc,1,identity)
            self.assertFalse(rpc.inputs)

    def test_unconfirmed_exit_is_not_retried(self):
        rpc=LifecycleRPC();rpc.refuse_close=True
        with patch.object(autoclose.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError): autoclose.wait_and_close(rpc,1,autoclose.prepare(rpc))
        self.assertEqual(rpc.inputs,[(5,0),(5,2),(5,1)])

    def test_general_generated_run_auto_closes_and_keep_open_skips_it(self):
        with tempfile.TemporaryDirectory() as directory:
            script=Path(directory)/'script.txt';script.write_bytes(compile_bas('END\n')[0])
            for extra in [[],['--keep-open']]:
                rpc=LifecycleRPC()
                with patch('flipper2jb.__main__.RPC',return_value=rpc),patch.object(autoclose.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
                    main(['run',str(script),'--ready']+extra)
                self.assertEqual(any(k==5 for k,_ in rpc.inputs),not bool(extra))
                self.assertEqual(sum(k==4 for k,_ in rpc.inputs),3)
                self.assertNotIn(12,rpc.calls)

    def test_target_auto_close_retains_consumed_session_latch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);active=root/'active';latch=root/'latch'
            active.write_text(f'{os.getpid()}\n{COMMAND}\n');rpc=LifecycleRPC()
            with patch.dict(os.environ,{'HB_SESSION_LATCH':str(latch)}),patch.object(ns2jb,'RPC',return_value=rpc),patch.object(autoclose.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
                ns2jb.main(['start','--active-file',str(active),'--ready'])
            self.assertTrue(latch.exists());self.assertFalse(rpc.locked)
            self.assertEqual(rpc.inputs,[(4,0),(4,2),(4,1),(5,0),(5,2),(5,1)])

    def test_ble_generated_run_stays_connected_through_exit_verification(self):
        backend=FakeBackend()
        with tempfile.TemporaryDirectory() as directory:
            script=Path(directory)/'script.txt';script.write_bytes(compile_bas('END\n')[0])
            with patch.object(ble,'bleak_api',side_effect=backend.api),patch.object(autoclose.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
                main(['--transport','ble','--ble-device',DEVICE.address,'run',str(script),'--ready'])
        self.assertEqual(backend.tags.count(16),1)
        self.assertEqual(backend.tags.count(23),6)
        self.assertFalse(backend.locked)
        self.assertEqual(backend.clients[0].disconnect_calls,1)


if __name__=='__main__': unittest.main()
