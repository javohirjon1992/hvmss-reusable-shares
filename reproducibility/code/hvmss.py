"""Reference implementation of hash-verified multi-secret sharing (HVMSS).

Components
----------
HBV   hash-based batch verification of Shamir sharings
RMSS  reusable-share multi-secret sharing with secret-salted pseudo-share commitments
DFR   dealer-free redistribution with Reed--Solomon syndrome verification

All arithmetic is over a prime field F_q (default q = 2^255 - 19).  The code is a
research prototype: Python integers are variable-time and no side-channel
protection is attempted.  Protocol randomness is drawn from the operating-system
CSPRNG unless a deterministic generator is passed explicitly for reproducible tests.
"""
from __future__ import annotations

import hashlib
import random
import secrets
from functools import lru_cache

Q = 2**255 - 19
SALT_BYTES = 16
SEED_BYTES = 32
DIGEST_BYTES = 32

# Domain-separation labels (protocol version is part of every label).
D_HBV_C = "HVMSS/v1/HBV/commit"
D_HBV_T = "HVMSS/v1/HBV/transcript"
D_HBV_A = "HVMSS/v1/HBV/challenge"
D_SET = "HVMSS/v1/RMSS/setup"
D_U = "HVMSS/v1/RMSS/u"
D_V = "HVMSS/v1/RMSS/v"
D_G = "HVMSS/v1/RMSS/salt"
D_E = "HVMSS/v1/RMSS/e"
D_RT = "HVMSS/v1/RMSS/transcript"
D_RA = "HVMSS/v1/RMSS/challenge"


# --------------------------------------------------------------------------
# Randomness
# --------------------------------------------------------------------------
class SystemRNG:
    """Operating-system CSPRNG (default for all protocol executions)."""

    @staticmethod
    def randbelow(q: int) -> int:
        return secrets.randbelow(q)

    @staticmethod
    def randbytes(n: int) -> bytes:
        return secrets.token_bytes(n)


class SeededRNG:
    """Deterministic generator for reproducible tests only (never for deployment)."""

    def __init__(self, seed: int):
        self._r = random.Random(seed)

    def randbelow(self, q: int) -> int:
        return self._r.randrange(q)

    def randbytes(self, n: int) -> bytes:
        return self._r.randbytes(n)


SYS = SystemRNG()


# --------------------------------------------------------------------------
# Typed, length-prefixed encoding and hash oracles
# --------------------------------------------------------------------------
def enc(*xs) -> bytes:
    """Injective typed encoding of nested tuples of int/bytes/str/list."""
    out = bytearray()
    for x in xs:
        if isinstance(x, bool):
            raise TypeError("bool is not an encodable type")
        if isinstance(x, int):
            if x < 0:
                raise ValueError("negative integers are not encodable")
            body = x.to_bytes(max(32, (x.bit_length() + 7) // 8), "big")
            tag = b"I"
        elif isinstance(x, (bytes, bytearray)):
            body, tag = bytes(x), b"B"
        elif isinstance(x, str):
            body, tag = x.encode(), b"S"
        elif isinstance(x, (list, tuple)):
            body, tag = enc(*x), b"L"
        else:
            raise TypeError(type(x))
        out += tag + len(body).to_bytes(4, "big") + body
    return bytes(out)


def H(*xs) -> bytes:
    """Commitment oracle H_C (SHA-256)."""
    return hashlib.sha256(enc(*xs)).digest()


def HF(q: int, *xs) -> int:
    """Field oracle H_F: SHA-512 reduced mod q (w = 512 bits) for q < 2^384,
    otherwise SHAKE-256 with (bitlen(q) + 256) output bits."""
    data = enc(*xs)
    if q.bit_length() <= 384:
        return int.from_bytes(hashlib.sha512(data).digest(), "big") % q
    nbytes = (q.bit_length() + 256 + 7) // 8
    return int.from_bytes(hashlib.shake_256(data).digest(nbytes), "big") % q


# --------------------------------------------------------------------------
# Polynomial arithmetic (coefficient lists, lowest degree first)
# --------------------------------------------------------------------------
def peval(c, x, q=Q):
    acc = 0
    for v in reversed(c):
        acc = (acc * x + v) % q
    return acc


def batch_inv(vals, q=Q):
    n = len(vals)
    pref = [1] * (n + 1)
    for i, v in enumerate(vals):
        pref[i + 1] = pref[i] * v % q
    inv = pow(pref[n], -1, q)
    out = [0] * n
    for i in range(n - 1, -1, -1):
        out[i] = inv * pref[i] % q
        inv = inv * vals[i] % q
    return out


def _check_points(xs, q):
    if len(set(xs)) != len(xs):
        raise ValueError("interpolation points must be distinct")
    if any(not (0 <= x < q) for x in xs):
        raise ValueError("non-canonical point")


def lagrange_at_zero(xs, q=Q):
    """Weights lambda_i with f(0) = sum_i lambda_i f(x_i); O(n^2)."""
    _check_points(xs, q)
    num = [1] * len(xs)
    den = [1] * len(xs)
    for i, xi in enumerate(xs):
        for j, xj in enumerate(xs):
            if i != j:
                num[i] = num[i] * xj % q
                den[i] = den[i] * (xj - xi) % q
    inv = batch_inv(den, q)
    return [a * b % q for a, b in zip(num, inv)]


def interp_coeffs(xs, ys, q=Q):
    """Coefficient form of the unique polynomial of degree < len(xs); O(n^2)."""
    _check_points(xs, q)
    n = len(xs)
    master = [1]
    for x in xs:  # master(X) = prod (X - x)
        nxt = [0] * (len(master) + 1)
        for k, v in enumerate(master):
            nxt[k] = (nxt[k] - x * v) % q
            nxt[k + 1] = (nxt[k + 1] + v) % q
        master = nxt
    dens = []
    for i, xi in enumerate(xs):
        d = 1
        for j, xj in enumerate(xs):
            if i != j:
                d = d * (xi - xj) % q
        dens.append(d)
    invd = batch_inv(dens, q)
    out = [0] * n
    for i, xi in enumerate(xs):
        scale = ys[i] * invd[i] % q
        if scale == 0:
            continue
        # synthetic division master / (X - xi), highest degree first
        rem = 0
        quo = [0] * n
        for k in range(n, 0, -1):
            rem = (master[k] + rem * xi) % q
            quo[k - 1] = rem
        for k in range(n):
            out[k] = (out[k] + scale * quo[k]) % q
    return out


def lagrange_matrix(src, dst, q=Q):
    """Matrix L with p(dst_a) = sum_i L[a][i] p(src_i) for deg p < |src|."""
    _check_points(src, q)
    if set(src) & set(dst):
        raise ValueError("destination points must not coincide with sources")
    w = []
    for i, xi in enumerate(src):
        d = 1
        for j, xj in enumerate(src):
            if i != j:
                d = d * (xi - xj) % q
        w.append(d)
    w = batch_inv(w, q)
    rows = []
    for x in dst:
        diffs = [(x - xi) % q for xi in src]
        inv = batch_inv(diffs, q)
        m = 1
        for dv in diffs:
            m = m * dv % q
        rows.append([m * wi % q * ii % q for wi, ii in zip(w, inv)])
    return rows


def matvec(A, v, q=Q):
    return [sum(a * b for a, b in zip(row, v)) % q for row in A]


def rs_parity(points, d, q=Q):
    """Parity matrix P (R x L, R = L - d) with P v = 0 iff v in RS_points(d)."""
    _check_points(points, q)
    L = len(points)
    if not 1 <= d <= L:
        raise ValueError("invalid dimension")
    den = []
    for i, x in enumerate(points):
        p = 1
        for j, y in enumerate(points):
            if i != j:
                p = p * (x - y) % q
        den.append(p)
    beta = batch_inv(den, q)
    rows = []
    powx = [1] * L
    for _ in range(L - d):
        rows.append([b * px % q for b, px in zip(beta, powx)])
        powx = [px * x % q for px, x in zip(powx, points)]
    return rows, beta


# --------------------------------------------------------------------------
# Generalized Reed--Solomon syndrome decoding (Berlekamp--Massey)
# --------------------------------------------------------------------------
def berlekamp_massey(s, q=Q):
    C, B = [1], [1]
    L, m, b = 0, 1, 1
    for n in range(len(s)):
        d = s[n]
        for i in range(1, L + 1):
            d = (d + C[i] * s[n - i]) % q
        if d == 0:
            m += 1
            continue
        coef = d * pow(b, -1, q) % q
        T = C[:]
        need = len(B) + m
        if len(C) < need:
            C = C + [0] * (need - len(C))
        for i, bi in enumerate(B):
            C[i + m] = (C[i + m] - coef * bi) % q
        if 2 * L <= n:
            L, B, b, m = n + 1 - L, T, d, 1
        else:
            m += 1
    C = C[: L + 1] + [0] * max(0, L + 1 - len(C))
    return C, L


def _solve(A, y, q=Q):
    n = len(A)
    M = [row[:] + [v] for row, v in zip(A, y)]
    for c in range(n):
        piv = next((r for r in range(c, n) if M[r][c] % q), None)
        if piv is None:
            return None
        M[c], M[piv] = M[piv], M[c]
        inv = pow(M[c][c], -1, q)
        M[c] = [v * inv % q for v in M[c]]
        for r in range(n):
            if r != c and M[r][c]:
                f = M[r][c]
                M[r] = [(a - f * b) % q for a, b in zip(M[r], M[c])]
    return [M[r][n] for r in range(n)]


def syndrome_decode(points, beta, syn, allowed, q=Q):
    """Find the unique error e (support in `allowed`, weight <= R/2) with P e = syn.

    Returns a dict {position: value}, {} for a zero syndrome, or None on failure."""
    R = len(syn)
    if not any(syn):
        return {}
    lam, L = berlekamp_massey(syn, q)
    if L == 0 or 2 * L > R:
        return None
    roots = []
    for x in allowed:
        xi = pow(x, -1, q)
        if peval(lam, xi, q) == 0:
            roots.append(x)
    if len(roots) != L:
        return None
    A = [[pow(x, r, q) for x in roots] for r in range(L)]
    Y = _solve(A, syn[:L], q)
    if Y is None:
        return None
    idx = {x: i for i, x in enumerate(points)}
    err = {x: Yx * pow(beta[idx[x]], -1, q) % q for x, Yx in zip(roots, Y)}
    # full consistency check of all R syndrome equations
    for r in range(R):
        if sum(beta[idx[x]] * e * pow(x, r, q) for x, e in err.items()) % q != syn[r]:
            return None
    return err


# --------------------------------------------------------------------------
# HBV: hash-based batch verification
# --------------------------------------------------------------------------
def _validate(n, t, ids, q):
    if not (1 <= t <= n < q):
        raise ValueError("require 1 <= t <= n < q")
    if len(ids) != n or len(set(ids)) != n or any(not (0 < i < q) for i in ids):
        raise ValueError("identifiers must be n distinct nonzero field elements")


def hbv_challenges(pub, mode="independent"):
    q = pub["q"]
    T = H(D_HBV_T, pub["ctx"], q, pub["n"], pub["t"], pub["k"], list(pub["ids"]), pub["C"])
    if mode == "independent":
        return [HF(q, D_HBV_A, T, j) for j in range(1, pub["k"] + 1)]
    a = HF(q, D_HBV_A, T, 0)  # scalar-power convention alpha^j
    out, acc = [], 1
    for _ in range(pub["k"]):
        acc = acc * a % q
        out.append(acc)
    return out


def hbv_deal(secrets_, n, t, ctx, q=Q, rng=SYS, ids=None, mode="independent"):
    ids = list(ids) if ids is not None else list(range(1, n + 1))
    _validate(n, t, ids, q)
    k = len(secrets_)
    F = [[s % q] + [rng.randbelow(q) for _ in range(t - 1)] for s in secrets_]
    r = [rng.randbelow(q) for _ in range(t)]
    C, openings = [], []
    for i in ids:
        sh = [peval(f, i, q) for f in F]
        ri = peval(r, i, q)
        salt = rng.randbytes(SALT_BYTES)
        C.append(H(D_HBV_C, ctx, q, n, t, k, i, sh, ri, salt))
        openings.append((i, sh, ri, salt))
    pub = dict(ctx=ctx, q=q, n=n, t=t, k=k, ids=ids, C=C, mode=mode)
    alphas = hbv_challenges(pub, mode)
    pub["z"] = [(r[c] + sum(a * f[c] for a, f in zip(alphas, F))) % q for c in range(t)]
    return pub, openings


def hbv_check_opening(pub, op):
    q = pub["q"]
    i, sh, ri, salt = op
    pos = pub.get("_pos")
    if pos is None:
        pos = pub["_pos"] = {x: c for c, x in enumerate(pub["ids"])}
    if i not in pos:
        return False
    if len(sh) != pub["k"] or any(not (0 <= v < q) for v in sh) or not (0 <= ri < q):
        return False
    if len(salt) != SALT_BYTES:
        return False
    return H(D_HBV_C, pub["ctx"], q, pub["n"], pub["t"], pub["k"], i, sh, ri, salt) == pub["C"][pos[i]]


def hbv_verify(pub, op, alphas=None):
    q = pub["q"]
    if len(pub["z"]) != pub["t"] or any(not (0 <= v < q) for v in pub["z"]):
        return False
    if not hbv_check_opening(pub, op):
        return False
    if alphas is None:
        alphas = hbv_challenges(pub, pub["mode"])
    i, sh, ri, _ = op
    return peval(pub["z"], i, q) == (ri + sum(a * s for a, s in zip(alphas, sh))) % q


def hbv_reconstruct(pub, openings):
    q, t = pub["q"], pub["t"]
    seen, good = set(), []
    for op in openings:
        if op[0] in seen:
            raise ValueError("duplicate identity")
        seen.add(op[0])
        if hbv_check_opening(pub, op):
            good.append(op)
        if len(good) == t:
            break
    if len(good) < t:
        raise ValueError("fewer than t valid openings")
    lam = lagrange_at_zero([op[0] for op in good], q)
    return [sum(l * op[1][j] for l, op in zip(lam, good)) % q for j in range(pub["k"])]


# --------------------------------------------------------------------------
# RMSS: reusable-share multi-secret sharing
# --------------------------------------------------------------------------
def rmss_setup(n, t, q=Q, rng=SYS):
    if not (1 <= t <= n) or 2 * n - t + 1 >= q:
        raise ValueError("require 1 <= t <= n and n + p < q")
    seeds = [rng.randbytes(SEED_BYTES) for _ in range(n)]
    salts = [rng.randbytes(SALT_BYTES) for _ in range(n)]
    D = [H(D_SET, q, n, t, i, s, g) for i, (s, g) in enumerate(zip(seeds, salts), 1)]
    return dict(q=q, n=n, t=t, D=D), seeds, salts


@lru_cache(maxsize=64)
def _rmss_geometry(n, t, q):
    p = n - t + 1
    src = tuple(range(n + 1))
    xp = tuple(range(n + 1, n + p + 1))
    return p, src, xp, lagrange_matrix(src, xp, q)


def rmss_derive(sid, i, seed, k, q=Q):
    u = [HF(q, D_U, sid, i, j, seed) for j in range(1, k + 1)]
    v = HF(q, D_V, sid, i, seed)
    g = [H(D_G, sid, i, j, seed)[:SALT_BYTES] for j in range(1, k + 1)]
    return u, v, g


def _rmss_e(sid, i, j, u, salt, salted):
    if salted:
        return H(D_E, sid, i, j, u, salt)
    return H(D_E, sid, i, j, u)


def rmss_challenges(setup, pub):
    q = setup["q"]
    T = H(D_RT, pub["sid"], q, setup["n"], setup["t"], pub["k"], setup["D"], pub["Y"], pub["M"], pub["E"])
    return [HF(q, D_RA, T, j) for j in range(1, pub["k"] + 1)]


def rmss_add(secrets_, sid, setup, seeds, rng=SYS, salted=True):
    q, n, t = setup["q"], setup["n"], setup["t"]
    k = len(secrets_)
    p, src, xp, Lm = _rmss_geometry(n, t, q)
    der = [rmss_derive(sid, i, s, k, q) for i, s in enumerate(seeds, 1)]
    Y = [matvec(Lm, [secrets_[j] % q] + [d[0][j] for d in der], q) for j in range(k)]
    omega = rng.randbelow(q)
    M = matvec(Lm, [omega] + [d[1] for d in der], q)
    E = [[_rmss_e(sid, i, j + 1, d[0][j], d[2][j], salted) for j in range(k)] for i, d in enumerate(der, 1)]
    pub = dict(sid=sid, k=k, Y=Y, M=M, E=E, salted=salted)
    alphas = rmss_challenges(setup, pub)
    zvals = [(omega + sum(a * s for a, s in zip(alphas, secrets_))) % q]
    zvals += [(d[1] + sum(a * u for a, u in zip(alphas, d[0]))) % q for d in der]
    pub["Z"] = interp_coeffs(list(src), zvals, q)
    return pub


def rmss_verify_participant(setup, pub, i, seed, alphas=None):
    q = setup["q"]
    u, v, g = rmss_derive(pub["sid"], i, seed, pub["k"], q)
    for j in range(pub["k"]):
        if pub["E"][i - 1][j] != _rmss_e(pub["sid"], i, j + 1, u[j], g[j], pub["salted"]):
            return False
    if alphas is None:
        alphas = rmss_challenges(setup, pub)
    return peval(pub["Z"], i, q) == (v + sum(a * x for a, x in zip(alphas, u))) % q


def rmss_verify_public(setup, pub, alphas=None):
    q, n, t = setup["q"], setup["n"], setup["t"]
    p, _, xp, _ = _rmss_geometry(n, t, q)
    if len(pub["Z"]) != n + 1 or any(not (0 <= c < q) for c in pub["Z"]):
        return False
    if alphas is None:
        alphas = rmss_challenges(setup, pub)
    for c, x in enumerate(xp):
        rhs = (pub["M"][c] + sum(a * pub["Y"][j][c] for j, a in enumerate(alphas))) % q
        if peval(pub["Z"], x, q) != rhs:
            return False
    return True


def rmss_open(sid, i, seed, k, q=Q):
    u, _, g = rmss_derive(sid, i, seed, k, q)
    return (i, u, g)


def rmss_reconstruct(setup, pub, openings):
    q, n, t = setup["q"], setup["n"], setup["t"]
    p, _, xp, _ = _rmss_geometry(n, t, q)
    seen, good = set(), []
    for i, u, g in openings:
        if i in seen or not (1 <= i <= n):
            raise ValueError("duplicate or invalid identity")
        seen.add(i)
        if all(pub["E"][i - 1][j] == _rmss_e(pub["sid"], i, j + 1, u[j], g[j], pub["salted"]) for j in range(pub["k"])):
            good.append((i, u))
        if len(good) == t:
            break
    if len(good) < t:
        raise ValueError("fewer than t valid openings")
    pts = [i for i, _ in good] + list(xp)
    lam = lagrange_at_zero(pts, q)
    return [sum(l * v for l, v in zip(lam, [u[j] for _, u in good] + list(pub["Y"][j]))) % q for j in range(pub["k"])]


# --------------------------------------------------------------------------
# DFR: dealer-free redistribution with syndrome verification
# --------------------------------------------------------------------------
@lru_cache(maxsize=128)
def dfr_geometry(C, Xp, t, q=Q):
    """Parity matrix and reconstruction weights for old points C and public points Xp."""
    T = list(C) + list(Xp)
    d = t + len(Xp)
    P, beta = rs_parity(T, d, q)
    B = list(C[:t]) + list(Xp)
    kappa = lagrange_at_zero(B, q)
    return P, beta, kappa


@lru_cache(maxsize=128)
def new_committee_parity(n2, t2, q=Q):
    """Parity of RS_{0..n2}(t2): (0, S(1..n2)) is a codeword iff deg S < t2 and S(0) = 0."""
    P, _ = rs_parity(list(range(n2 + 1)), t2, q)
    return P


def dfr_reshare(b, ub, n2, t2, epoch, q=Q, rng=SYS):
    """Old member b re-shares its K values ub (list) with an HBV row proof."""
    return hbv_deal(ub, n2, t2, ("DFR", epoch, b), q, rng)


def dfr_syndromes(C, Xp, yvals, t, rows_k, q=Q):
    """New member's syndrome evaluations S_r(k) for each secret component.

    rows_k[b_index][j] = phi_b^(j)(k); yvals[j][x_index] = public value."""
    P, _, _ = dfr_geometry(tuple(C), tuple(Xp), t, q)
    m = len(C)
    K = len(rows_k[0])
    out = []
    for r, Pr in enumerate(P):
        out.append([(sum(Pr[b] * rows_k[b][j] for b in range(m)) + sum(Pr[m + c] * yvals[j][c] for c in range(len(Xp)))) % q for j in range(K)])
    return out  # R x K


def dfr_check(n2, t2, S, q=Q, rng=SYS):
    """Batched consistency check of all syndrome polynomials.

    S[k-1][r][j] is member k's broadcast for row r and component j.  A private
    random linear combination reduces all R*K rows to one membership test."""
    if not S or not S[0]:
        return True
    R, K = len(S[0]), len(S[0][0])
    rho = [[rng.randbelow(q) for _ in range(K)] for _ in range(R)]
    comb = [0] + [sum(rho[r][j] * S[k][r][j] for r in range(R) for j in range(K)) % q for k in range(n2)]
    Pn = new_committee_parity(n2, t2, q)
    return not any(matvec(Pn, comb, q))


def dfr_check_exact(n2, t2, S, q=Q):
    if not S or not S[0]:
        return True
    Pn = new_committee_parity(n2, t2, q)
    R, K = len(S[0]), len(S[0][0])
    for r in range(R):
        for j in range(K):
            if any(matvec(Pn, [0] + [S[k][r][j] for k in range(n2)], q)):
                return False
    return True


def dfr_new_share(C, Xp, yvals, t, rows_k, q=Q):
    _, _, kappa = dfr_geometry(tuple(C), tuple(Xp), t, q)
    K = len(rows_k[0])
    return [(sum(kappa[b] * rows_k[b][j] for b in range(t)) + sum(kappa[t + c] * yvals[j][c] for c in range(len(Xp)))) % q for j in range(K)]


def dfr_run(C, old_vals, Xp, yvals, t, n2, t2, epoch="e1", q=Q, rng=SYS, verify_rows=True):
    """Honest end-to-end execution; returns new plain shares (list over members 1..n2)."""
    m = len(C)
    if m < t:
        raise ValueError("at least t old members must participate")
    rows = [dfr_reshare(b, old_vals[i], n2, t2, epoch, q, rng) for i, b in enumerate(C)]
    if verify_rows:
        for pub, ops in rows:
            al = hbv_challenges(pub, pub["mode"])
            if not all(hbv_verify(pub, op, al) for op in ops):
                raise RuntimeError("row proof failed; abort")
    S, shares = [], []
    for k in range(n2):
        rows_k = [ops[k][1] for _, ops in rows]
        S.append(dfr_syndromes(C, Xp, yvals, t, rows_k, q))
        shares.append(dfr_new_share(C, Xp, yvals, t, rows_k, q))
    if not dfr_check(n2, t2, S, q, rng):
        raise RuntimeError("syndrome inconsistency; abort")
    return shares, rows, S


def dfr_recover(C, Xp, t, n2, t2, S, q=Q):
    """Robust path after a failed syndrome check.

    1. Each syndrome row's broadcasts are corrected with GRS syndrome decoding on
       RS_{1..n2}(t2) (up to floor((n2 - t2)/2) false broadcasts).
    2. The corrected rows are interpolated at zero to obtain the old-code syndromes.
    3. The old error vector is decoded on the participating coordinates C
       (up to floor(R/2) wrong re-shared values).
    Returns a list (one dict {b: e_b} per secret component) or None if decoding fails."""
    pts = list(range(1, n2 + 1))
    Pn, bn = rs_parity(pts, t2, q)
    lam = lagrange_at_zero(pts[:t2], q)
    _, beta, _ = dfr_geometry(tuple(C), tuple(Xp), t, q)
    T = list(C) + list(Xp)
    R, K = len(S[0]), len(S[0][0])
    out = []
    for j in range(K):
        consts = []
        for r in range(R):
            v = [S[k][r][j] for k in range(n2)]
            err = syndrome_decode(pts, bn, matvec(Pn, v, q), pts, q)
            if err is None:
                return None
            vc = [(v[k] - err.get(k + 1, 0)) % q for k in range(n2)]
            consts.append(sum(l * x for l, x in zip(lam, vc[:t2])) % q)
        e = syndrome_decode(T, beta, consts, list(C), q)
        if e is None:
            return None
        out.append(e)
    return out


def dfr_new_share_corrected(C, Xp, yvals, t, rows_k, corr, q=Q):
    """New share computed from rows whose constants are corrected by the decoded errors."""
    fixed = [[(rows_k[b][j] - corr[j].get(C[b], 0)) % q for j in range(len(rows_k[b]))] for b in range(len(C))]
    return dfr_new_share(C, Xp, yvals, t, fixed, q)
