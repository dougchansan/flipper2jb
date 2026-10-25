import socket,time,random,pathlib

def vi(n):
 if type(n) is not int or not 0 <= n < 2**64: raise ValueError('unsigned 64-bit integer required')
 b=bytearray()
 while n>127:b.append((n&127)|128);n>>=7
 b.append(n);return bytes(b)
def integer(k,n):return vi(k*8)+vi(n)
def blob(k,b):
 if isinstance(b,str):b=b.encode()
 return vi(k*8+2)+vi(len(b))+b
def decode(b):
 i=0;out={}
 def var():
  nonlocal i
  n=0;s=0
  while True:

   if i>=len(b):raise ValueError('truncated varint')
   v=b[i];i+=1;n|=(v&127)<<s
   if v<128:return n
   s+=7
   if s>63:raise ValueError('bad varint')
 while i<len(b):
  key=var();typ=key&7;k=key>>3
  if not k:raise ValueError('invalid field number')
  if typ==0:v=var()
  elif typ==2:
   n=var()
   if n>len(b)-i:raise ValueError('truncated field')
   v=b[i:i+n];i+=n
  else:raise ValueError('wire type '+str(typ))
  out.setdefault(k,[]).append(v)
 return out
def first(d,k,default=0):return d.get(k,[default])[0]
class RPC:
 def __init__(self, host='192.168.4.1', port=8080):
  self.s=socket.create_connection((host,port),5);self.s.settimeout(8);self.ident=random.randint(1000,1000000);self.screen=None
 @classmethod
 def from_stream(cls,stream):
  rpc=cls.__new__(cls);rpc.s=stream;rpc.ident=random.randint(1000,1000000);rpc.screen=None
  return rpc
 def exact(self,n):
  b=b''
  while len(b)<n:
   d=self.s.recv(n-len(b))
   if not d:raise EOFError()
   b+=d
  return b
 def receive(self):
  n=0;shift=0
  while True:
   v=self.exact(1)[0];n|=(v&127)<<shift
   if v<128:break
   shift+=7
   if shift>28:raise ValueError('length')
  if n>65536:raise ValueError('oversize')
  d=decode(self.exact(n))
  if 22 in d:self.screen=first(decode(first(d,22)),1,b'')
  return d
 def request(self,tag,payload=b''):
  self.ident+=1;msg=integer(1,self.ident)+blob(tag,payload);self.s.sendall(vi(len(msg))+msg);out=[]
  while True:
   d=self.receive()
   if first(d,1)!=self.ident:continue
   if first(d,2):raise RuntimeError('RPC status '+str(first(d,2)))
   out.append(d)
   if not first(d,3):return out
 def read(self,path):
  return b''.join(first(decode(first(decode(first(d,10)),1)),4,b'') for d in self.request(9,blob(1,path)))
 def capture(self,path):
  self.screen=None;self.request(20)
  end=time.monotonic()+4
  while self.screen is None and time.monotonic()<end:self.receive()
  self.request(21)
  b=self.screen
  if b is None or len(b)!=1024:raise ValueError('screen bytes '+str(None if b is None else len(b)))
  pixels=bytearray(1024)
  for y in range(64):
   for x in range(128):
    if b[(y//8)*128+x]&(1<<(y%8)):pixels[y*16+x//8]|=1<<(7-x%8)
  pathlib.Path(path).write_bytes(b'P4\n128 64\n'+pixels)
 def close(self):self.s.close()
