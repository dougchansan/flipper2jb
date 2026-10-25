#!/usr/bin/env python3
"""Create ignored ESP-IDF defaults with a new private AP password. No device I/O."""
import argparse
import json
import os
from pathlib import Path
import secrets

parser = argparse.ArgumentParser()
parser.add_argument('--ssid', default='FlippyKB')
args = parser.parse_args()
if not 1 <= len(args.ssid.encode()) <= 32 or any(ord(c) < 32 for c in args.ssid):
    parser.error('SSID must be 1..32 bytes without control characters')
root = Path(__file__).resolve().parents[1]
password = secrets.token_urlsafe(24)
path = root / 'firmware/tcp_uart_bridge/sdkconfig.defaults.local'
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as stream:
    stream.write('CONFIG_BRIDGE_AP_SSID=' + json.dumps(args.ssid) + '\n')
    stream.write('CONFIG_BRIDGE_AP_PASSWORD=' + json.dumps(password) + '\n')
print('Created private sdkconfig.defaults.local. Read it locally for the AP password.')
