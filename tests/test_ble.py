import asyncio
import contextlib
import io
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from flipper2jb import ble
from flipper2jb.__main__ import main
from flipper2jb.keyboard import LAYOUT
from flipper2jb.rpc import blob, decode, first, integer, vi
from flipper2jb.targets import ns2jb

DEVICE = SimpleNamespace(address='FAKE-FLIPPER-UUID', name='Flipper Test')
ADVERTISEMENT = SimpleNamespace(local_name='Flipper Test', service_uuids=[ble.SERVICE])
COMMAND = 'V=START(39380,127,0,0,1,11,22,33,44)'


class FakeBackend:
    def __init__(self):
        self.files, self.tags, self.clients = {}, [], []
        self.failure = None
        self.connect_failure = False
        self.devices = {'one': (DEVICE, ADVERTISEMENT)}

    async def discover(self, **kwargs): return self.devices

    def client(self, device, **kwargs):
        client = FakeClient(self, device, kwargs['disconnected_callback'])
        self.clients.append(client)
        return client

    def api(self): return self.client, SimpleNamespace(discover=self.discover)


class FakeClient:
    def __init__(self, backend, device, disconnected):
        self.backend, self.device, self.callback = backend, device, disconnected
        self.is_connected = False
        self.mtu_size = 23
        self.notifications, self.input, self.credit, self.writes = {}, bytearray(), 64, []
        self.disconnect_calls = 0

    async def connect(self):
        if self.backend.connect_failure: raise RuntimeError('backend details must stay private')
        self.is_connected = True

    async def disconnect(self):
        self.disconnect_calls += 1; self.is_connected = False; self.callback(self)

    async def start_notify(self, characteristic, callback): self.notifications[characteristic] = callback

    async def read_gatt_char(self, characteristic):
        assert characteristic == ble.FLOW
        return self.credit.to_bytes(4, 'big')

    def emit(self, data):
        for i in range(0, len(data), 7): self.notifications[ble.TX](None, data[i:i+7])

    def respond(self, ident, body):
        message = integer(1, ident)+body
        self.emit(vi(len(message))+message)

    async def write_gatt_char(self, characteristic, data, response):
        assert characteristic == ble.RX and response is True
        assert 0 < len(data) <= 20 and len(data) <= self.credit
        self.writes.append(bytes(data)); self.credit -= len(data)
        if not self.credit:
            self.credit = 64
            asyncio.get_running_loop().call_soon(self.notifications[ble.FLOW], None, self.credit.to_bytes(4, 'big'))
        self.input.extend(data)
        while self.input:
            size = shift = offset = 0
            for byte in self.input:
                size |= (byte & 127) << shift; shift += 7; offset += 1
                if byte < 128: break
            else: return
            if len(self.input) < offset+size: return
            request = decode(self.input[offset:offset+size]); del self.input[:offset+size]
            tag = next(k for k in request if k not in (1,2,3)); self.backend.tags.append(tag)
            ident = first(request,1); query = decode(first(request,tag))
            if tag == self.backend.failure:
                self.is_connected = False; self.callback(self)
                raise ConnectionError('simulated uncertain acknowledgment')
            if tag == 5: body = blob(6,blob(1,first(query,1)))
            elif tag == 11:
                path = first(query,1).decode()
                self.backend.files[path] = self.backend.files.get(path,b'')+first(decode(first(query,2)),4)
                if first(request,3): continue
                body = blob(4,b'')
            elif tag == 9:
                path = first(query,1).decode()
                if path.endswith('.settings'): data = b'layout: /ext/en-UK.kl\ninterface: 0\n'
                elif path.endswith('.kl'): data = LAYOUT.read_bytes()
                else: data = self.backend.files[path]
                body = blob(10,blob(1,blob(4,data)))
            elif tag == 12:
                del self.backend.files[first(query,1).decode()]; body = blob(4,b'')
            else: body = blob(4,b'')
            self.respond(ident,body)


class BleCommandTests(unittest.TestCase):
    def test_general_commands_share_rpc_with_fragmentation_and_credit_refills(self):
        backend = FakeBackend()
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory)/'script.txt'; script.write_bytes(b'REM Bluetooth transfer\n'*100)
            base = ['--transport','ble','--ble-device',DEVICE.address]
            with patch.object(ble,'bleak_api',side_effect=backend.api), patch('flipper2jb.__main__.time.sleep'), contextlib.redirect_stdout(io.StringIO()):
                main(base+['ping']); main(base+['inspect'])
                main(base+['upload',str(script),'--remote','/ext/badusb/test.txt'])
                self.assertEqual(backend.files['/ext/badusb/test.txt'],script.read_bytes())
                self.assertNotIn(16,backend.tags)
                main(base+['run',str(script),'--ready'])
                main(base+['remove','/ext/badusb/test.txt'])
        self.assertEqual(backend.tags.count(16),1)
        self.assertEqual(backend.tags.count(23),3)
        self.assertTrue(all(c.disconnect_calls==1 for c in backend.clients))
        self.assertTrue(all(not c.is_connected for c in backend.clients))

    def test_ble_target_retains_latch_after_lost_start_ack(self):
        backend = FakeBackend(); backend.failure = 16
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); active = root/'active'; latch = root/'latch'
            active.write_text(f'{os.getpid()}\n{COMMAND}\n')
            with patch.dict(os.environ,{'HB_SESSION_LATCH':str(latch)}), patch.object(ble,'bleak_api',side_effect=backend.api), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ble.BluetoothError):
                    ns2jb.main(['--transport','ble','--ble-device',DEVICE.address,'start','--active-file',str(active),'--ready'])
            self.assertTrue(latch.exists())
            self.assertEqual(backend.tags.count(16),1)
            self.assertNotIn(23,backend.tags)
            self.assertFalse(backend.clients[0].is_connected)

    def test_device_selection_is_explicit_and_ambiguous_names_fail(self):
        backend = FakeBackend()
        backend.devices['two'] = (SimpleNamespace(address='OTHER',name=DEVICE.name),ADVERTISEMENT)
        with patch.object(ble,'bleak_api',side_effect=backend.api):
            for identifier in [None, DEVICE.name, 'missing']:
                with self.assertRaises(ble.BluetoothError): ble.with_ble(identifier,lambda rpc: None)
        self.assertFalse(backend.clients)

    def test_connect_failure_is_redacted_and_no_retry(self):
        backend = FakeBackend(); backend.connect_failure = True
        with patch.object(ble,'bleak_api',side_effect=backend.api):
            with self.assertRaises(ble.BluetoothError) as error: ble.with_ble(DEVICE.address,lambda rpc: None)
        self.assertNotIn('backend details',str(error.exception))
        self.assertEqual(len(backend.clients),1)

    def test_scan_lists_only_candidates_without_connecting(self):
        backend = FakeBackend()
        backend.devices['unrelated'] = (SimpleNamespace(address='OTHER',name='Speaker'),SimpleNamespace(local_name='Speaker',service_uuids=[]))
        with patch.object(ble,'bleak_api',side_effect=backend.api), contextlib.redirect_stdout(io.StringIO()) as output:
            main(['ble-scan','--seconds','1'])
        self.assertIn(DEVICE.address,output.getvalue()); self.assertNotIn('Speaker',output.getvalue())
        self.assertFalse(backend.clients)

    def test_missing_optional_dependency_is_actionable(self):
        import sys
        with patch.dict(sys.modules,{'bleak':None}):
            with self.assertRaises(ble.BluetoothError) as error: ble.bleak_api()
        self.assertIn('requirements-bluetooth.txt',str(error.exception))


class BleStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_waiting_sender_and_reader_fail_on_disconnect(self):
        client = SimpleNamespace(is_connected=True)
        stream = ble.BleStream(client,timeout=.1)
        sender = asyncio.create_task(stream.send(b'123'))
        reader = asyncio.create_task(stream.receive(1))
        await asyncio.sleep(0)
        stream.disconnected()
        for task in [sender,reader]:
            with self.assertRaises(ConnectionError): await task

    async def test_zero_credit_times_out_without_write(self):
        stream = ble.BleStream(SimpleNamespace(is_connected=True),timeout=.01)
        with self.assertRaises(asyncio.TimeoutError): await stream.send(b'test')

    async def test_malformed_credit_and_bounded_receive_buffer(self):
        for data in [b'',b'\x01',b'\xff'*4]:
            stream = ble.BleStream(SimpleNamespace(is_connected=True))
            stream.on_flow(None,data)
            with self.assertRaises(ValueError): stream.check()
        stream = ble.BleStream(SimpleNamespace(is_connected=True))
        stream.on_data(None,b'X'*(2*1024*1024+1))
        with self.assertRaises(RuntimeError): stream.check()


if __name__=='__main__': unittest.main()
