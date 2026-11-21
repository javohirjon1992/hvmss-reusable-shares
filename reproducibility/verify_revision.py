"""Run from the package directory. Writes separate revision evidence."""
from pathlib import Path
import csv, sys, math, statistics, collections, platform, multiprocessing as mp, time
sys.path.insert(0,'code')
import hvmss as h
def rows(name):
    return list(csv.DictReader(open('results/'+name+'.csv')))
def save(name, fields, vals):
    with open(name+'.csv','w',newline='') as f:
        w=csv.writer(f);w.writerow(fields);w.writerows(vals)
def validate():
    raw=collections.defaultdict(list)
    for v in rows('timings_raw'):
        raw[v['operation'],v['n']].append(float(v['ms']))
    count=0
    for v in rows('timings')+rows('baselines'):
        if v['reps']=='21':
            vals=raw[v['operation'],v['n']][:21]  # protocol block precedes batching
            assert len(vals)==21
            quartiles=statistics.quantiles(vals,n=4,method='inclusive')
            assert all(math.isclose(a,float(v[key])) for a,key in zip(quartiles,['q1_ms','median_ms','q3_ms']))
            count+=1
    for x in rows('soundness_exhaustive'):
        assert math.isclose(int(x['accepted'])/int(x['total']),float(x['theory']))
    assert all(int(x['measured_bytes'])==int(x['formula_bytes']) for x in rows('payloads'))
    print(count,'timing summaries verified')
def budgets():
    q=h.Q; delta=1444*(q-1444)/(q*2**512)
    vals=[]
    for label,bits,salt in [('A',256,128),('B',256,256),('C',384,128),('D',384,256)]:
        for u in [32,48,64,80]:
            Q=2**u
            terms={'affine':(Q+1)/q,'birthday':Q*(Q-1)/2**(bits+1),'late':Q/2**bits,'salt':2*Q/(2**salt-Q),'seed':2*Q/(2**256-Q),'field':Q*delta}
            for key,v in terms.items(): vals.append((label,u,key,v,math.log2(v)))
    save('budget',['profile','log2_queries','event','bound','log2_bound'],vals)
def worker(conn):
    while True:
        msg=conn.recv()
        if msg is None: return
        tag,args=msg
        if tag=='HBV': ok=h.hbv_verify(*args)
        elif tag=='RMSS': ok=h.rmss_verify_public(args[0],args[1]) and h.rmss_verify_participant(*args)
        else: ok=h.dfr_check_exact(*args)
        conn.send(ok)
def bench():
    out=[]
    c,d=mp.Pipe();p=mp.Process(target=worker,args=(d,));p.start()
    try:
        for n in (32,64,128,256,512):
            t=n//2
            for k in (1,4):
                sec=list(range(k));pub,ops=h.hbv_deal(sec,n,t,'audit')
                setup,seeds,_=h.rmss_setup(n,t)
                rp=h.rmss_add(sec,'audit',setup,seeds)
                for tag,args in [('HBV',(pub,ops[-1])),('RMSS',(setup,rp,n,seeds[-1]))]:
                    for j in range(6):
                        start=time.perf_counter_ns();c.send((tag,args));assert c.recv()
                        elapsed=(time.perf_counter_ns()-start)/1e6
                        if j: out.append((tag,n,k,j,elapsed))
        n=8;t=4; C=list(range(1,n+1));old=[[3+i] for i in C]
        shares,_,syn=h.dfr_run(C,old,[],[[]],t,n,t)
        assert sum(a*v[0] for a,v in zip(h.lagrange_at_zero(C[:t]),shares))%h.Q==3
        for j in range(6):
            start=time.perf_counter_ns();c.send(('DFR-syndrome',(n,t,syn)));assert c.recv()
            if j:out.append(('DFR-syndrome',n,1,j,(time.perf_counter_ns()-start)/1e6))
    finally:
        c.send(None);p.join()
    save('ipc_observations',['operation','n','k','run','round_trip_ms'],out)
    print(platform.platform(),sys.version)
if __name__=='__main__':
    validate();budgets();bench()
