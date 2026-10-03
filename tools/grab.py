import sys,re,base64
# usage: python3 grab.py OUT SRC1 [SRC2 ...]  (old order "SRC OUT" also accepted). Parts are concatenated in order.
a=sys.argv[1:]
if len(a)==2 and not a[1].endswith('.txt') and a[0].endswith('.txt'): a=[a[1],a[0]]
out,srcs=a[0],a[1:]; b64=''
for src in srcs:
    t=open(src).read()
    m=re.search(r'B64START([A-Za-z0-9+/=\\n]+?)B64END',t)
    b64+=m.group(1).replace('\\n','')
d=base64.b64decode(b64)
open(out,'wb').write(d); print(out,len(d))
