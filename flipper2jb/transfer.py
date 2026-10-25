"""Verified Flipper storage uploads over the protobuf bridge."""
from .rpc import vi, integer, blob, first


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
