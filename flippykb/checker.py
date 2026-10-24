"""Generate the source checksum checker used in a separate SmileBASIC slot."""

def normalize(text):
    return ''.join(line + '\n' for line in text.replace('\r', '').split('\n') if line)


def hashes(text):
    a = b = 0
    for char in text:
        a = (a * 257 + ord(char)) % 2147483647
        b = (b * 65599 + ord(char)) % 2147483629
    return a, b


def checker(source, name='NS2'):
    import re
    if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,15}', name):
        raise ValueError('invalid saved source name')
    normalized = normalize(source)
    a, b = hashes(normalized)
    return f'''\
' Source checker: run in a separate slot, never in the bootstrap slot.
VAR CK$,CL$="",CT$="",CI,CC,CN=0
VAR CA#=0,CH#=0
CK$=LOADV("TXT:{name}")
IF LEN(CK$)==0 THEN PRINT "EMPTY OR LOAD FAILED":END
CK$=CK$+CHR$(10)
FOR CI=0 TO LEN(CK$)-1
 CC=ASC(MID$(CK$,CI,1))
 IF CC!=13 THEN
  IF CC==10 THEN
   IF LEN(CL$)>0 THEN CT$=CT$+CL$+CHR$(10)
   CL$=""
  ELSE
   CL$=CL$+CHR$(CC)
  ENDIF
 ENDIF
NEXT
FOR CI=0 TO LEN(CT$)-1
 CC=ASC(MID$(CT$,CI,1))
 CA#=CA#*257+CC
 CA#=CA#-FLOOR(CA#/2147483647)*2147483647
 CH#=CH#*65599+CC
 CH#=CH#-FLOOR(CH#/2147483629)*2147483629
 IF CC==10 THEN CN=CN+1
NEXT
PRINT "LINES / CHARS",CN,LEN(CT$)
PRINT "HASH A / HASH B",CA#,CH#
IF CN=={normalized.count(chr(10))} && LEN(CT$)=={len(normalized)} && CA#=={a} && CH#=={b} THEN
 PRINT "SOURCE CHECK MATCH"
ELSE
 PRINT "SOURCE CHECK MISMATCH"
ENDIF
END
'''
