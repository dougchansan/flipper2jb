"""Shared connection selection for general commands and optional targets."""
import os


def add_options(parser):
    parser.add_argument('--transport', choices=['wifi', 'ble'], default=os.environ.get('FLIPPER_TRANSPORT', 'wifi'))
    parser.add_argument('--host', default=os.environ.get('FLIPPER_WIFI_HOST', '192.168.4.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('FLIPPER_WIFI_PORT', '8080')))
    parser.add_argument('--ble-device', default=os.environ.get('FLIPPER_BLE_DEVICE'), help='exact name or scan identifier (UUID on macOS)')


def with_connection(args, operation, tcp_factory):
    if args.transport == 'ble':
        from .ble import with_ble
        return with_ble(args.ble_device, operation)
    if args.transport != 'wifi': raise ValueError('unknown transport')
    rpc = tcp_factory(args.host, args.port)
    try: return operation(rpc)
    finally: rpc.close()
