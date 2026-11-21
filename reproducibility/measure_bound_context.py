"""Measure one complete honest DFR transfer in a single local process."""
import csv
import hashlib
import json
import platform
import statistics
import time
from pathlib import Path
from variant_check import implementation

def main():
    module = implementation('protocol')
    root = Path(__file__).resolve().parent
    rows = []
    for n in (8, 16, 32):
        t = n // 2
        members = list(range(1, n + 1))
        values = [[(7 + 11*i) % module.Q] for i in members]
        weights = module.lagrange_at_zero(members[:t])
        for iteration in range(24):
            start = time.perf_counter_ns()
            shares, _, _ = module.dfr_run(members, values, [], [[]], t, n, t,
                                          epoch=('old-sharing-001',iteration))
            elapsed = (time.perf_counter_ns() - start) / 1e6
            assert sum(w * v[0] for w,v in zip(weights,shares)) % module.Q == 7
            if iteration >= 3:
                rows.append((n,t,iteration-2,elapsed))
        print(n,statistics.median(row[-1] for row in rows if row[0]==n))
    with (root/'context_transfer_times.csv').open('w',newline='') as f:
        w=csv.writer(f); w.writerow(('n','t','run','ms'));w.writerows(rows)
    metadata = {'python':platform.python_version(),'system':platform.platform(),
                'machine':platform.machine(),'module_sha256':hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
                'warmups':3,'repetitions':21,'scope':'single-process serial transfer including exact syndrome checks; interpolation cross-check outside timer'}
    (root/'context_transfer_host.json').write_text(json.dumps(metadata,indent=2))
if __name__=='__main__': main()
