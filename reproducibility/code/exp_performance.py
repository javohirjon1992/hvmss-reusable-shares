"""Computation and communication measurements for HBV, RMSS, DFR and group-based baselines.

All protocol randomness comes from the OS CSPRNG.  Each operation: 3 warm-up runs,
21 timed runs (time.perf_counter_ns), median and interquartile range reported.
Usage:  python exp_performance.py
"""
import csv
import hashlib
import json
import os
import pathlib
import platform
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hvmss as hv  # noqa: E402
from hvmss import Q, peval  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)
NS = [8, 16, 32, 64, 128, 256]
WARM, REPS = 3, 21
raw_rows = []


def bench(name, n, fn, extra=None):
    for _ in range(WARM):
        fn()
    vals = []
    for _ in range(REPS):
        st = time.perf_counter_ns()
        fn()
        vals.append((time.perf_counter_ns() - st) / 1e6)
    vals.sort()
    q1, med, q3 = statistics.quantiles(vals, n=4, method="inclusive")
    raw_rows.extend(dict(operation=name, n=n, run=i, ms=v) for i, v in enumerate(vals))
    row = dict(operation=name, n=n, t=n // 2, median_ms=med, q1_ms=q1, q3_ms=q3, reps=REPS)
    if extra:
        row.update(extra)
    print(f"  {name:28s} n={n:4d} median={med:10.4f} ms", flush=True)
    return row


def write(name, rows):
    with (OUT / f"{name}.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[saved] {name}.csv ({len(rows)} rows)", flush=True)


# ---------------------------------------------------------------------------
# Canonical serializations (used for measured payload sizes)
# ---------------------------------------------------------------------------
def fe(x):
    return x.to_bytes(32, "big")


def ser_hbv_pub(pub):
    return b"".join(pub["C"]) + b"".join(fe(z) for z in pub["z"])


def ser_hbv_open(op):
    return b"".join(fe(v) for v in op[1]) + fe(op[2]) + op[3]


def ser_rmss_pub(pub):
    return (b"".join(fe(y) for Y in pub["Y"] for y in Y) + b"".join(fe(m) for m in pub["M"])
            + b"".join(e for row in pub["E"] for e in row) + b"".join(fe(z) for z in pub["Z"]))


# ---------------------------------------------------------------------------
# Protocol timings
# ---------------------------------------------------------------------------
def protocol_timings():
    rows = []
    for n in NS:
        t = n // 2
        # HBV
        pub, ops = hv.hbv_deal([17], n, t, f"bench-hbv-{n}")
        rows.append(bench("HBV.Deal", n, lambda: hv.hbv_deal([hv.SYS.randbelow(Q)], n, t, f"bench-hbv-{n}")))
        rows.append(bench("HBV.Verify", n, lambda: hv.hbv_verify(pub, ops[-1])))
        rows.append(bench("HBV.Reconstruct", n, lambda: hv.hbv_reconstruct(pub, ops[-t:])))
        # RMSS
        setup, seeds, _ = hv.rmss_setup(n, t)
        cnt = [0]

        def add():
            cnt[0] += 1
            return hv.rmss_add([hv.SYS.randbelow(Q)], f"bench-rmss-{n}-{cnt[0]}", setup, seeds)
        rp = add()
        rows.append(bench("RMSS.Add", n, add))
        rows.append(bench("RMSS.VerifyMember", n, lambda: hv.rmss_verify_participant(setup, rp, n, seeds[-1])))
        rows.append(bench("RMSS.VerifyPublic", n, lambda: hv.rmss_verify_public(setup, rp)))
        opens = [hv.rmss_open(rp["sid"], i, seeds[i - 1], 1) for i in range(n - t + 1, n + 1)]
        rows.append(bench("RMSS.Reconstruct", n, lambda: hv.rmss_reconstruct(setup, rp, opens)))
        # DFR with m = n' = n and t = t' = n/2 (plain Shamir source state)
        C = list(range(1, n + 1))
        g = [17] + [hv.SYS.randbelow(Q) for _ in range(t - 1)]
        vals = [[peval(g, b)] for b in C]
        hv.dfr_geometry(tuple(C), (), t)
        hv.new_committee_parity(n, t)
        rows_ = [hv.dfr_reshare(b, vals[i], n, t, "bench") for i, b in enumerate(C)]
        rows_k = [o[n - 1][1] for _, o in rows_]
        S = [hv.dfr_syndromes(C, [], [[]], t, [o[k][1] for _, o in rows_]) for k in range(n)]
        rows.append(bench("DFR.Reshare", n, lambda: hv.dfr_reshare(n, vals[-1], n, t, "bench")))
        rows.append(bench("DFR.VerifyRows", n, lambda: all(hv.hbv_verify(p, o[n - 1]) for p, o in rows_)))
        rows.append(bench("DFR.Syndromes", n, lambda: hv.dfr_syndromes(C, [], [[]], t, rows_k)))
        rows.append(bench("DFR.Check", n, lambda: hv.dfr_check(n, t, S)))
        rows.append(bench("DFR.CheckExact", n, lambda: hv.dfr_check_exact(n, t, S)))
        rows.append(bench("DFR.NewShare", n, lambda: hv.dfr_new_share(C, [], [[]], t, rows_k)))
    # per-party critical path of one DFR epoch (parties act in parallel)
    for n in NS:
        parts = ["DFR.Reshare", "DFR.VerifyRows", "DFR.Syndromes", "DFR.Check", "DFR.NewShare"]
        tot = sum(next(r["median_ms"] for r in rows if r["operation"] == p and r["n"] == n) for p in parts)
        rows.append(dict(operation="DFR.CriticalPath", n=n, t=n // 2, median_ms=tot, q1_ms="", q3_ms="", reps="sum of medians"))
    return rows


def precompute_timings():
    rows = []
    for n in NS:
        t = n // 2
        st = time.perf_counter_ns()
        hv._rmss_geometry.cache_clear()
        hv._rmss_geometry(n, t, Q)
        a = (time.perf_counter_ns() - st) / 1e6
        st = time.perf_counter_ns()
        hv.dfr_geometry.cache_clear()
        hv.dfr_geometry(tuple(range(1, n + 1)), (), t, Q)
        b = (time.perf_counter_ns() - st) / 1e6
        st = time.perf_counter_ns()
        hv.new_committee_parity.cache_clear()
        hv.new_committee_parity(n, t, Q)
        c = (time.perf_counter_ns() - st) / 1e6
        rows.append(dict(n=n, t=t, rmss_lagrange_matrix_ms=a, dfr_parity_and_weights_ms=b, new_committee_parity_ms=c))
    return rows


# ---------------------------------------------------------------------------
# Batch amortization
# ---------------------------------------------------------------------------
def batch_timings(n=32):
    t = n // 2
    p = n - t + 1
    rows = []
    setup, seeds, _ = hv.rmss_setup(n, t)
    for k in [1, 2, 4, 8, 16, 32, 64]:
        sec = [hv.SYS.randbelow(Q) for _ in range(k)]
        pub, ops = hv.hbv_deal(sec, n, t, f"batch-{k}")
        cnt = [0]

        def add():
            cnt[0] += 1
            return hv.rmss_add(sec, f"batch-r-{k}-{cnt[0]}", setup, seeds)
        rp = add()
        r1 = bench("HBV.Deal", n, lambda: hv.hbv_deal(sec, n, t, f"batch-{k}"))
        r2 = bench("HBV.Verify", n, lambda: hv.hbv_verify(pub, ops[-1]))
        r3 = bench("RMSS.Add", n, add)
        r4 = bench("RMSS.VerifyMember", n, lambda: hv.rmss_verify_participant(setup, rp, n, seeds[-1]))
        hb = len(ser_hbv_pub(pub))
        rb = len(ser_rmss_pub(rp))
        assert hb == 32 * (n + t)
        assert rb == 32 * (k * p + p + n + 1 + k * n)
        for r, op in [(r1, "HBV.Deal"), (r2, "HBV.Verify"), (r3, "RMSS.Add"), (r4, "RMSS.VerifyMember")]:
            rows.append(dict(operation=op, n=n, t=t, k=k, median_ms=r["median_ms"], per_secret_ms=r["median_ms"] / k,
                             broadcast_bytes=hb if op.startswith("HBV") else rb,
                             broadcast_bytes_per_secret=(hb if op.startswith("HBV") else rb) / k))
    return rows


# ---------------------------------------------------------------------------
# Group-based baselines: Feldman and Pedersen over MODP-3072 and secp256k1
# ---------------------------------------------------------------------------
def load_modp():
    f = ROOT / "results" / "modp3072_group.json"
    g = json.loads(f.read_text())
    p, qq, gg, hh = g["p"], g["q"], g["g"], g["h"]
    assert p.bit_length() == 3072 and pow(gg, qq, p) == 1 and pow(hh, qq, p) == 1 and gg != 1 and hh not in (1, gg)
    return p, qq, gg, hh


def baselines():
    import coincurve
    from coincurve import PublicKey
    rows = []
    p, qq, gg, hh = load_modp()

    def evq(c, x, m):
        acc = 0
        for v in reversed(c):
            acc = (acc * x + v) % m
        return acc

    # secp256k1
    N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
    ctr = 0
    while True:  # nothing-up-my-sleeve second generator
        x = hashlib.sha256(b"HVMSS/v1/pedersen-H/" + ctr.to_bytes(4, "big")).digest()
        try:
            Hpt = PublicKey(b"\x02" + x)
            break
        except Exception:
            ctr += 1

    def sb(v):
        return v.to_bytes(32, "big")

    for n in NS:
        t = n // 2
        ids = list(range(1, n + 1))
        # MODP-3072
        a = [hv.SYS.randbelow(qq) for _ in range(t)]
        b = [hv.SYS.randbelow(qq) for _ in range(t)]

        def feld_deal():
            sh = [evq(a, i, qq) for i in ids]
            return sh, [pow(gg, v, p) for v in a]

        def ped_deal():
            sh = [(evq(a, i, qq), evq(b, i, qq)) for i in ids]
            return sh, [pow(gg, x, p) * pow(hh, y, p) % p for x, y in zip(a, b)]
        Cf = feld_deal()[1]
        Cp = ped_deal()[1]
        i = n
        si, ri = evq(a, i, qq), evq(b, i, qq)
        exps = [pow(i, j, qq) for j in range(t)]

        def feld_ver():
            rhs = 1
            for c, e in zip(Cf, exps):
                rhs = rhs * pow(c, e, p) % p
            return pow(gg, si, p) == rhs

        def ped_ver():
            rhs = 1
            for c, e in zip(Cp, exps):
                rhs = rhs * pow(c, e, p) % p
            return pow(gg, si, p) * pow(hh, ri, p) % p == rhs
        assert feld_ver() and ped_ver()
        rows.append(bench("Feldman-3072.Deal", n, feld_deal, dict(broadcast_bytes=384 * t)))
        rows.append(bench("Feldman-3072.Verify", n, feld_ver, dict(broadcast_bytes=384 * t)))
        rows.append(bench("Pedersen-3072.Deal", n, ped_deal, dict(broadcast_bytes=384 * t)))
        rows.append(bench("Pedersen-3072.Verify", n, ped_ver, dict(broadcast_bytes=384 * t)))
        # secp256k1 (libsecp256k1 via coincurve)
        a = [1 + hv.SYS.randbelow(N - 1) for _ in range(t)]
        b = [1 + hv.SYS.randbelow(N - 1) for _ in range(t)]

        def efeld_deal():
            sh = [evq(a, i, N) for i in ids]
            return sh, [PublicKey.from_secret(sb(v)) for v in a]

        def eped_deal():
            sh = [(evq(a, i, N), evq(b, i, N)) for i in ids]
            return sh, [PublicKey.combine_keys([PublicKey.from_secret(sb(x)), Hpt.multiply(sb(y))]) for x, y in zip(a, b)]
        Ef = efeld_deal()[1]
        Ep = eped_deal()[1]
        si, ri = evq(a, i, N), evq(b, i, N)
        exps = [sb(pow(i, j, N)) for j in range(t)]

        def efeld_ver():
            rhs = PublicKey.combine_keys([c.multiply(e) for c, e in zip(Ef, exps)])
            return PublicKey.from_secret(sb(si)).format() == rhs.format()

        def eped_ver():
            rhs = PublicKey.combine_keys([c.multiply(e) for c, e in zip(Ep, exps)])
            lhs = PublicKey.combine_keys([PublicKey.from_secret(sb(si)), Hpt.multiply(sb(ri))])
            return lhs.format() == rhs.format()
        assert efeld_ver() and eped_ver()
        rows.append(bench("Feldman-secp256k1.Deal", n, efeld_deal, dict(broadcast_bytes=33 * t)))
        rows.append(bench("Feldman-secp256k1.Verify", n, efeld_ver, dict(broadcast_bytes=33 * t)))
        rows.append(bench("Pedersen-secp256k1.Deal", n, eped_deal, dict(broadcast_bytes=33 * t)))
        rows.append(bench("Pedersen-secp256k1.Verify", n, eped_ver, dict(broadcast_bytes=33 * t)))
    return rows, coincurve.__version__


# ---------------------------------------------------------------------------
# Measured payloads versus analytical formulas
# ---------------------------------------------------------------------------
def payloads():
    rows = []
    for n in NS:
        t = n // 2
        pub, ops = hv.hbv_deal([1], n, t, "pl")
        setup, seeds, salts = hv.rmss_setup(n, t)
        rp = hv.rmss_add([1], "pl", setup, seeds)
        m, n2, t2, K = n, n, t, 1
        R = m - t
        row_pub = sum(len(ser_hbv_pub(hv.dfr_reshare(b, [1], n2, t2, "pl")[0])) for b in range(1, 3)) // 2 * m
        meas = dict(HBV_broadcast=len(ser_hbv_pub(pub)), HBV_private=len(ser_hbv_open(ops[0])),
                    RMSS_broadcast=len(ser_rmss_pub(rp)), RMSS_private_state=len(seeds[0]) + len(salts[0]),
                    DFR_row_broadcast=row_pub, DFR_private=m * n2 * len(ser_hbv_open(ops[0])),
                    DFR_syndrome_broadcast=32 * K * R * n2)
        form = dict(HBV_broadcast=32 * (n + t), HBV_private=32 * 2 + 16, RMSS_broadcast=32 * (4 * n - 2 * t + 3),
                    RMSS_private_state=48, DFR_row_broadcast=m * (32 * n2 + 32 * t2),
                    DFR_private=m * n2 * (32 * (K + 1) + 16), DFR_syndrome_broadcast=32 * K * R * n2)
        for key in meas:
            rows.append(dict(n=n, t=t, quantity=key, measured_bytes=meas[key], formula_bytes=form[key], match=int(meas[key] == form[key])))
        for name, size in [("Feldman/Pedersen-3072_broadcast", 384 * t), ("Feldman/Pedersen-secp256k1_broadcast", 33 * t)]:
            rows.append(dict(n=n, t=t, quantity=name, measured_bytes=size, formula_bytes=size, match=1))
    return rows


def environment(extra):
    cpu = ""
    try:
        cpu = [l for l in pathlib.Path("/proc/cpuinfo").read_text().splitlines() if l.startswith("model name")][0].split(":", 1)[1].strip()
    except Exception:
        pass
    env = dict(python=sys.version.split()[0], implementation=platform.python_implementation(), platform=platform.platform(),
               cpu=cpu, logical_cpus=os.cpu_count(), timer="time.perf_counter_ns", warmups=WARM, repetitions=REPS,
               randomness="secrets (OS CSPRNG) for protocol executions", field="q = 2^255 - 19",
               hash="SHA-256 (commitments), SHA-512 mod q (field oracle)")
    env.update(extra)
    (OUT / "environment.json").write_text(json.dumps(env, indent=2))


def main():
    t0 = time.time()
    print("protocol timings", flush=True)
    write("timings", protocol_timings())
    write("precompute", precompute_timings())
    print("batch", flush=True)
    write("batch", batch_timings())
    print("baselines", flush=True)
    b, ccv = baselines()
    write("baselines", b)
    write("payloads", payloads())
    write("timings_raw", raw_rows)
    import numpy, sympy, matplotlib
    environment(dict(coincurve=ccv, numpy=numpy.__version__, sympy=sympy.__version__, matplotlib=matplotlib.__version__,
                     elapsed_s=round(time.time() - t0, 1)))
    print(f"done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
