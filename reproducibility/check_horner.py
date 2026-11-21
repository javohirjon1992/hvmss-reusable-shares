import pathlib,random,subprocess,tempfile,sys
sys.path.insert(0,'code')
from hvmss import peval
rng=random.Random(20261121)
with tempfile.TemporaryDirectory() as td:
    exe=pathlib.Path(td)/'horner'
    subprocess.run(['cc','-O2','horner.c','-lgmp','-o',exe],check=True)
    for q in (127,2**127-1,2**255-19,2**521-1):
        for n in (1,16,128,256):
            for x in (0,1,q-1,rng.randrange(q)):
                c=[rng.randrange(q) for _ in range(n)]
                args=' '.join(map(str,[q,x,n,*reversed(c)]))
                result=subprocess.check_output([exe],input=args,text=True)
                assert int(result)==peval(c,x,q)
print('64 polynomial evaluations agree.')
