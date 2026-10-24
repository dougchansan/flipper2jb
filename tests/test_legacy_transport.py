import unittest, struct
from unittest.mock import patch
from flippykb.session import program, deliver, upload
from flippykb.rpc import decode, first

class FakeSocket:
    def __init__(self,r):self.r=r
    def sendall(self,b):
        n=0;s=0;i=0
        while True:
            v=b[i];i+=1;n|=(v&127)<<s;s+=7
            if v<128:break
        d=decode(b[i:]);assert len(b[i:])==n
        q=decode(first(d,11));file=decode(first(q,2))
        chunk=first(file,4);assert len(chunk)<=512
        self.r.data+=chunk;self.r.more.append(first(d,3))
class FakeRPC:
    def __init__(self,corrupt=False,fail=None):self.ident=1;self.data=b'';self.more=[];self.calls=[];self.corrupt=corrupt;self.fail=fail;self.s=FakeSocket(self)
    def receive(self):return {1:[self.ident]}
    def read(self,p):
        if p.endswith('.settings'):return b'layout: /ext/badusb/assets/layouts/en-UK.kl\ninterface: 0\n'
        if p.endswith('.kl'):return (__import__('pathlib').Path(__file__).resolve().parents[1] / 'assets/en-UK.kl').read_bytes()
        return b'bad' if self.corrupt else self.data
    def request(self,tag,payload):
        self.calls.append(tag)
        if tag==self.fail:raise RuntimeError('simulated lost acknowledgement')
        return []
class Tests(unittest.TestCase):
    def test_roundtrip_physical_keys(self):
        command='V=START(39380,192,168,50,34,1,2,3,4)';data,duration=program(command)
        layout=(__import__('pathlib').Path(__file__).resolve().parents[1] / 'assets/en-UK.kl').read_bytes()
        lookup={struct.unpack_from('<H',layout,c*2)[0]:chr(c) for c in range(32,127)}
        shift=False;out='';held=set()
        for line in data.decode().splitlines():
            if line.startswith('HOLD '):
                k=line[5:];self.assertNotIn(k,held);held.add(k)
                if k=='SHIFT':shift=True
                elif k=='ENTER':out+='\n'
                else:
                    ch=' ' if k=='SPACE' else k
                    usage=struct.unpack_from('<H',layout,ord(ch)*2)[0]&255
                    out+=lookup[usage|(512 if shift else 0)]
            elif line.startswith('RELEASE '):
                k=line[8:];held.remove(k)
                if k=='SHIFT':shift=False
        self.assertFalse(held)
        self.assertEqual(out,'LOAD "TXT:NS2"\n\nRUN\nREMOVE NSR,&H60000000,&H3FFFFFFF\n'+command+'\n')
        self.assertIn(b'DELAY 50',data);self.assertGreater(duration,20)
    def test_invalid(self):
        for value in ['RUN','V=START(1)\nREMOVE','V=START(foo)']:
            with self.assertRaises(ValueError):program(value)
        with self.assertRaises(ValueError):program('V=START(1)',ms=0)
    def test_upload_and_no_secret_output(self):
        data,t=program('V=START(1)');r=FakeRPC()
        with patch('builtins.print') as log:deliver(r,data,t,'/ext/badusb/test.txt',lambda _:None)
        self.assertEqual(r.data,data);self.assertEqual(r.more[-1],0);self.assertTrue(all(r.more[:-1]));self.assertEqual(r.calls,[16,23,23,23,12])
        self.assertNotIn('V=START',str(log.call_args_list))
    def test_bad_readback_never_launches(self):
        r=FakeRPC(corrupt=True)
        with self.assertRaises(RuntimeError):deliver(r,b'test',0,'test',lambda _:None)
        self.assertEqual(r.calls,[])
    def test_lost_start_ack_not_retried(self):
        r=FakeRPC(fail=16)
        with self.assertRaises(RuntimeError):deliver(r,b'test',0,'test',lambda _:None)
        self.assertEqual(r.calls,[16])
    def test_open_script_cleanup_is_deferred_without_replaying_input(self):
        r=FakeRPC();request=r.request
        def guarded(tag,payload):
            result=request(tag,payload)
            if tag==12: raise RuntimeError('RPC status 13')
            return result
        r.request=guarded
        with patch('builtins.print') as log:deliver(r,b'test',0,'test',lambda _:None)
        self.assertEqual(r.calls,[16,23,23,23,12])
        self.assertIn('file still open',str(log.call_args_list))
    def test_unexpected_cleanup_error_is_reported(self):
        r=FakeRPC(fail=12)
        with self.assertRaises(RuntimeError):deliver(r,b'test',0,'test',lambda _:None)
        self.assertEqual(r.calls.count(16),1)
class SocketIntegration(unittest.TestCase):
    def test_existing_rpc_over_fragmented_loopback(self):
        import socket, threading
        from flippykb.rpc import RPC, vi, blob, integer
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen()
        address=listener.getsockname();saved=socket.create_connection;seen=[];errors=[]
        def serve():
            conn,_=listener.accept();reader=object.__new__(RPC);reader.s=conn
            content=b''
            try:
                while True:
                    request=reader.receive();ident=first(request,1)
                    tag=next(k for k in request if k not in (1,2,3));seen.append(tag)
                    q=decode(first(request,tag))
                    if tag==11:
                        content+=first(decode(first(q,2)),4)
                        if first(request,3):continue
                        body=blob(4,b'')
                    elif tag==9:
                        name=first(q,1).decode()
                        if name.endswith('.settings'):data=b'layout: /ext/layouts/en-UK.kl\ninterface: 0\n'
                        elif name.endswith('.kl'):data=(__import__('pathlib').Path(__file__).resolve().parents[1] / 'assets/en-UK.kl').read_bytes()
                        else:data=content
                        body=blob(10,blob(1,blob(4,data)))
                    else:body=blob(4,b'')
                    reply=integer(1,ident)+body;frame=vi(len(reply))+reply
                    # Exercise the original exact-read framing with split records.
                    conn.sendall(frame[:1]);conn.sendall(frame[1:])
                    if tag==12:break
            except Exception as e:errors.append(e)
            finally:conn.close();listener.close()
        thread=threading.Thread(target=serve);thread.start()
        try:
            with patch('socket.create_connection',lambda *args,**kwargs:saved(address,5)):
                client=RPC()
            try:
                data,duration=program('V=START(39380,127,0,0,1,1,2,3,4)')
                deliver(client,data,duration,'/ext/badusb/test.txt',lambda _:None)
            finally:client.close()
        finally:thread.join(5)
        self.assertFalse(thread.is_alive());self.assertFalse(errors)
        self.assertEqual(seen.count(16),1);self.assertEqual(seen.count(23),3);self.assertEqual(seen[-1],12)
if __name__=='__main__':unittest.main()
