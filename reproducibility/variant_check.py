"""Honest functional and paired local timing checks; Python 3.11+ standard library.

Run from any directory. Use --output-dir PATH to preserve a delivered measurement.
The default writes to variant_observations/ next to this script.
"""
import argparse
import csv
import hashlib
import importlib.util
import itertools
import json
import platform
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WARMUPS, SAMPLES = 3, 21


def implementation(folder):
    path = ROOT / folder / 'hvmss.py'
    spec = importlib.util.spec_from_file_location(f'hvmss_{folder}', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_rows(path, rows):
    with path.open('w', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def require(value, context):
    if not value:
        raise RuntimeError(context)


def check_functional(name, m):
    rows = []
    for n in (1, 4, 7):
        for t in sorted({1, (n+1)//2, n}):
            for k in (1, 4):
                secrets = [j * 13 for j in range(k)]
                sid = f'functional/{n}/{t}/{k}'
                for mode in ('independent', 'powers'):
                    pub, openings = m.hbv_deal(secrets, n, t, sid, rng=m.SeededRNG(120), mode=mode)
                    require(all(m.hbv_verify(pub, op) for op in openings), sid)
                    count = 0
                    for subset in itertools.combinations(openings, t):
                        require(m.hbv_reconstruct(pub, subset) == secrets, sid)
                        count += 1
                    rows.append(dict(variant=name, component='HBV', mode=mode, n=n, t=t, k=k,
                                     checks=n, reconstruction_subsets=count, outcome='pass'))
                setup, seeds, salts = m.rmss_setup(n, t, rng=m.SeededRNG(121))
                require(all(tag == m.H(m.D_SET, m.Q, n, t, i, seed, salt)
                            for i, (tag, seed, salt) in enumerate(zip(setup['D'], seeds, salts), 1)), sid)
                pub = m.rmss_add(secrets, sid, setup, seeds, rng=m.SeededRNG(122))
                require(m.rmss_verify_public(setup, pub), sid)
                require(all(m.rmss_verify_participant(setup, pub, i, seed)
                            for i, seed in enumerate(seeds, 1)), sid)
                openings = [m.rmss_open(sid, i, seed, k) for i, seed in enumerate(seeds, 1)]
                count = 0
                for subset in itertools.combinations(openings, t):
                    require(m.rmss_reconstruct(setup, pub, subset) == secrets, sid)
                    count += 1
                rows.append(dict(variant=name, component='RMSS', mode='independent', n=n, t=t, k=k,
                                 checks=n+1, reconstruction_subsets=count, outcome='pass'))
                committee = list(range(1, n+1))
                public_points = list(range(n+1, n+1+len(pub['M'])))
                new, _, syn = m.dfr_run(committee, [op[1] for op in openings], public_points,
                                        pub['Y'], t, n, t, sid, rng=m.SeededRNG(123))
                require(m.dfr_check_exact(n, t, syn), sid)
                for ids in itertools.combinations(committee, t):
                    weights = m.lagrange_at_zero(ids)
                    got = [sum(w * new[i-1][j] for i, w in zip(ids, weights)) % m.Q for j in range(k)]
                    require(got == secrets, sid)
                rows.append(dict(variant=name, component='DFR-from-RMSS', mode='driver-default',
                                 n=n, t=t, k=k, checks=n*n, reconstruction_subsets=count, outcome='pass'))
    return rows


def prepare(m, n, t, k):
    sid = f'paired/{n}/{k}'
    secrets = list(range(k))
    verify = {}
    for mode in ('independent', 'powers'):
        pub, openings = m.hbv_deal(secrets, n, t, sid, rng=m.SeededRNG(82), mode=mode)
        verify['HBV.'+mode] = lambda pub=pub, opening=openings[-1]: m.hbv_verify(pub, opening)
    setup, seeds, _ = m.rmss_setup(n, t, rng=m.SeededRNG(83))
    pub = m.rmss_add(secrets, sid, setup, seeds, rng=m.SeededRNG(84))
    verify['RMSS.member'] = lambda: m.rmss_verify_participant(setup, pub, n, seeds[-1])
    verify['RMSS.public'] = lambda: m.rmss_verify_public(setup, pub)
    return verify


def measure(modules):
    raw, summary = [], []
    order_rng = random.Random(1701)
    for n, k in [(n,k) for n in (8,16,32,64,128,256,512) for k in (1,4)] + [(32,k) for k in (2,8,16,32,64)]:
        t = n//2
        suite = {name: prepare(m,n,t,k) for name,m in modules.items()}
        for op in suite['archived']:
            samples = {variant: [] for variant in modules}
            for iteration in range(WARMUPS+SAMPLES):
                variants = list(modules)
                order_rng.shuffle(variants)
                for variant in variants:
                    fn = suite[variant][op]
                    before = time.perf_counter_ns()
                    valid = fn()
                    elapsed = time.perf_counter_ns()-before
                    require(valid, (variant,op,n,k))
                    if iteration>=WARMUPS:
                        samples[variant].append(elapsed/1e6)
                        raw.append(dict(variant=variant, operation=op, n=n, t=t, k=k,
                                        iteration=iteration-WARMUPS+1, pair_order=variants.index(variant)+1, ns=elapsed))
            for variant, values in samples.items():
                q1, median, q3 = statistics.quantiles(values,n=4,method='inclusive')
                summary.append(dict(variant=variant, operation=op, n=n, t=t, k=k, reps=SAMPLES,
                                    median_ms=median, q1_ms=q1, q3_ms=q3))
    return raw, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'variant_observations')
    out = parser.parse_args().output_dir
    out.mkdir(parents=True,exist_ok=True)
    modules = {'archived':implementation('code'),'specified':implementation('specified')}
    functional = [row for name,m in modules.items() for row in check_functional(name,m)]
    write_rows(out/'functional.csv',functional)
    raw, summary = measure(modules)
    write_rows(out/'timings_raw.csv',raw)
    write_rows(out/'timings.csv',summary)
    build = {name:hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for name,m in modules.items()}
    metadata = dict(python=sys.version, platform=platform.platform(), clock='perf_counter_ns',
                    warmups=WARMUPS, repetitions=SAMPLES, data_generation='fixed identical test-only PRNG seeds',
                    hash_challenge_cache='none supplied', order='fixed-seed shuffled within each pair',
                    modules_sha256=build)
    (out/'environment.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(len(functional),'functional rows,',len(raw),'timing observations,',len(summary),'summaries')


if __name__ == '__main__':
    main()
