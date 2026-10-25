"""Optional BLE serial transport. Bleak is imported only for actual BLE use."""
import asyncio
import threading
from .rpc import RPC

# UUID byte order follows the firmware's little-endian serial_service_uuid.inc.
SERVICE = '8fe5b3d5-2e7f-4a98-2a48-7acc60fe0000'
ADVERTISED_SERVICE = '00003082-0000-1000-8000-00805f9b34fb'
RX = '19ed82ae-ed21-4c9d-4145-228e62fe0000'  # host → Flipper
TX = '19ed82ae-ed21-4c9d-4145-228e61fe0000'  # Flipper → host
FLOW = '19ed82ae-ed21-4c9d-4145-228e63fe0000'


class BluetoothError(RuntimeError):
    """Sanitized, actionable Bluetooth failure."""


def bleak_api():
    try:
        from bleak import BleakClient, BleakScanner
        return BleakClient, BleakScanner
    except ImportError:
        raise BluetoothError('Bluetooth requires: python3 -m pip install -r requirements-bluetooth.txt') from None


async def scan_devices(seconds=5):
    if not 1 <= seconds <= 60:
        raise ValueError('scan duration must be 1..60 seconds')
    _, scanner = bleak_api()
    found = await scanner.discover(timeout=seconds, return_adv=True)
    results = []
    for device, adv in found.values():
        name = adv.local_name or device.name or ''
        services = {s.lower() for s in adv.service_uuids}
        if name.lower().startswith('flipper ') or services & {SERVICE, ADVERTISED_SERVICE}:
            results.append((device, name))
    return results


class BleStream:
    """Async byte stream, exposed to the existing synchronous RPC worker."""
    def __init__(self, client, timeout=15):
        self.client = client
        self.timeout = timeout
        self.buffer = bytearray()
        self.available = asyncio.Event()
        self.writable = asyncio.Event()
        self.credits = 0
        self.error = None
        self.closed = False
        self.chunk_limit = 20

    def fail(self, error):
        if self.error is None: self.error = error
        self.available.set(); self.writable.set()

    def disconnected(self):
        self.closed = True
        self.fail(ConnectionError('Bluetooth disconnected; no reconnect attempted'))

    def on_data(self, _, data):
        if len(self.buffer) + len(data) > 2 * 1024 * 1024:
            self.fail(RuntimeError('Bluetooth receive buffer limit exceeded'))
            return
        self.buffer.extend(data)
        self.available.set()

    def on_flow(self, _, data):
        if len(data) != 4:
            self.fail(ValueError('invalid Bluetooth credit record'))
            return
        # Firmware reverses its uint32 before advertising a new receive window.
        self.credits = int.from_bytes(data, 'big')
        if self.credits > 1024 * 1024:
            self.fail(ValueError('invalid Bluetooth receive window'))
        elif self.credits: self.writable.set()
        else: self.writable.clear()

    def check(self):
        if self.error: raise self.error
        if self.closed or not self.client.is_connected:
            raise ConnectionError('Bluetooth disconnected')

    async def initialize(self):
        # Authenticated characteristics trigger the operating system's pairing UI.
        await asyncio.wait_for(self.client.start_notify(TX, self.on_data), 90)
        await asyncio.wait_for(self.client.start_notify(FLOW, self.on_flow), 90)
        initial = await asyncio.wait_for(self.client.read_gatt_char(FLOW), 90)
        self.on_flow(None, initial)
        self.check()
        mtu = self.client.mtu_size
        if mtu < 23: raise ValueError('invalid Bluetooth MTU')
        self.chunk_limit = min(243, mtu - 3)

    async def send(self, data):
        offset = 0
        while offset < len(data):
            self.check()
            await asyncio.wait_for(self.writable.wait(), self.timeout)
            self.check()
            count = min(len(data)-offset, self.chunk_limit, self.credits)
            if count <= 0: continue
            # Reserve before awaiting: a flow notification may arrive during the write.
            self.credits -= count
            if not self.credits: self.writable.clear()
            await asyncio.wait_for(self.client.write_gatt_char(RX, data[offset:offset+count], response=True), self.timeout)
            offset += count

    async def receive(self, count):
        while True:
            self.check()
            if self.buffer:
                data = bytes(self.buffer[:count]); del self.buffer[:count]
                if not self.buffer: self.available.clear()
                return data
            self.available.clear()
            await asyncio.wait_for(self.available.wait(), self.timeout)


class SyncStream:
    """Blocking socket-like methods called only by the worker thread."""
    def __init__(self, stream, loop):
        self.stream, self.loop = stream, loop
        self.loop_thread = threading.get_ident()

    def call(self, coroutine):
        if threading.get_ident() == self.loop_thread:
            coroutine.close()
            raise RuntimeError('blocking BLE operation on its event-loop thread')
        future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        try: return future.result()
        except BaseException:
            future.cancel()
            raise

    def sendall(self, data): return self.call(self.stream.send(bytes(data)))
    def recv(self, count): return self.call(self.stream.receive(count))
    def close(self): pass  # The async owner always disconnects in finally.


async def with_ble_async(identifier, operation):
    if not identifier:
        raise BluetoothError('choose --ble-device from ble-scan; no device is selected automatically')
    client_class, _ = bleak_api()
    devices = await scan_devices()
    matches = [d for d, name in devices if identifier.casefold() in (d.address.casefold(), name.casefold())]
    if len(matches) != 1:
        raise BluetoothError('Bluetooth device not found or name ambiguous; use its scan identifier')
    stream = None

    def disconnected(_):
        if stream is not None: stream.disconnected()

    client = client_class(matches[0], disconnected_callback=disconnected, timeout=60, pair=True)
    try:
        await asyncio.wait_for(client.connect(), 90)
        stream = BleStream(client)
        await stream.initialize()
        rpc = RPC.from_stream(SyncStream(stream, asyncio.get_running_loop()))
        # Keep CoreBluetooth and all GATT work on the main async loop.
        return await asyncio.to_thread(operation, rpc)
    finally:
        if stream is not None: stream.disconnected()
        if client.is_connected:
            await asyncio.wait_for(client.disconnect(), 10)


def with_ble(identifier, operation):
    try:
        return asyncio.run(with_ble_async(identifier, operation))
    except BluetoothError:
        raise
    except Exception:
        # Backend exception text can contain device or payload details.
        raise BluetoothError('Bluetooth operation failed; check pairing and Bluetooth permissions; no retry attempted') from None


def print_scan(seconds=5):
    try:
        devices = asyncio.run(scan_devices(seconds))
    except BluetoothError:
        raise
    except Exception:
        raise BluetoothError('Bluetooth scan failed; enable Bluetooth and allow this terminal Bluetooth access') from None
    for device, name in devices:
        print(f'{device.address}\t{name}')
    if not devices: print('No advertising Flippers found. Enable Bluetooth and disconnect the mobile app.')
