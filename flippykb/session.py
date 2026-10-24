"""Existing TCP protobuf transport; no connection occurs on import or --self-test."""
import json, sys, time, struct, re, os
from pathlib import Path
from .rpc import RPC, vi, integer, blob, decode, first

def program(command, name="NS2", ms=50):
    import re
    if not re.fullmatch(r"V=START\([0-9,]+\)", command): raise ValueError("invalid session command")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,15}", name): raise ValueError("invalid bootstrap name")
    if not isinstance(ms, int) or not 20 <= ms <= 250: raise ValueError("timing must be 20..250 ms")
    layout=(Path(__file__).parent.parent/'assets/en-UK.kl').read_bytes()
    lines=['REM Fresh HBLauncher session; never replay', 'DELAY 5000']
    def key(k, shift=False, delay=ms):
        if shift: lines.extend(['HOLD SHIFT',f'DELAY {delay}'])
        lines.extend(['HOLD '+k,f'DELAY {delay}','RELEASE '+k,f'DELAY {delay}'])
        if shift: lines.extend(['RELEASE SHIFT',f'DELAY {delay}'])
    for line,pause in [(f'LOAD "TXT:{name}"',3000),('',3000),('RUN',3000),('REMOVE NSR,&H60000000,&H3FFFFFFF',6000),(command,0)]:
        for ch in line:
            code=struct.unpack_from('<H',layout,ord(ch)*2)[0]
            if not code or code>>8 not in (0,2): raise ValueError('unsupported key')
            key('SPACE' if ch==' ' else ch,bool(code>>8))
        key('ENTER',delay=100)
        if pause: lines.append(f'DELAY {pause}')
    duration=sum(int(x.split()[1]) for x in lines if x.startswith('DELAY '))/1000
    return ('\n'.join(lines)+'\n').encode(),duration

def upload(rpc, remote, data):
    if not data: raise ValueError('empty upload')
    # StorageWriteRequest is one command split into <=512 byte File.data records.
    rpc.ident+=1
    for offset in range(0,len(data),512):
        more=offset+512<len(data)
        payload=blob(1,remote)+blob(2,blob(4,data[offset:offset+512]))
        msg=integer(1,rpc.ident)+integer(3,int(more))+blob(11,payload)
        rpc.s.sendall(vi(len(msg))+msg)
    while True:
        d=rpc.receive()
        if first(d,1)!=rpc.ident: continue
        if first(d,2): raise RuntimeError('storage write rejected')
        if not first(d,3): break
    if rpc.read(remote)!=data: raise RuntimeError('upload readback mismatch')

def deliver(rpc, data, duration, remote, sleep=time.sleep):
    settings=rpc.read('/ext/badusb/.badkb.settings').decode()
    # Do not silently change the tested keyboard layout or USB/BLE interface.
    layout=re.search(r'^layout: (.+)$',settings,re.M)
    if not layout or not layout[1].strip().endswith('/en-UK.kl'): raise RuntimeError('Flipper en-UK layout required')
    if rpc.read(layout[1].strip())!=(Path(__file__).parent.parent/'assets/en-UK.kl').read_bytes(): raise RuntimeError('Keyboard layout differs from tested bytes')
    if not re.search(r'^interface: 0\s*$',settings,re.M): raise RuntimeError('Flipper USB interface required')
    print('Flipper RPC ready; existing keyboard layout verified',flush=True)
    upload(rpc,remote,data)
    print('Fresh command upload verified; starting Bad KB',flush=True)
    rpc.request(16,blob(1,'Bad KB')+blob(2,remote))
    sleep(2)
    for typ in (0,2,1): rpc.request(23,integer(1,4)+integer(2,typ))
    print('Flipper acknowledged start input; awaiting console authentication',flush=True)
    sleep(duration+2)
    # Elapsed script time is NOT an acknowledgement of HID delivery.
    try:
        rpc.request(12,blob(1,remote))
    except RuntimeError as error:
        if str(error)!='RPC status 13': raise
        print('Estimated typing interval elapsed; close Bad KB before temporary-script cleanup (file still open)',flush=True)
    else:
        print('Estimated typing interval elapsed; temporary script removed',flush=True)
