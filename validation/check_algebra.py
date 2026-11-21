"""Independent finite-field checks for the mathematical audit (standard library)."""

from collections import Counter
from itertools import product
import json
from pathlib import Path


def vectors(q, n):
    return product(range(q), repeat=n)


def evaluate(coeffs, x, q):
    return sum(c * pow(x, j, q) for j, c in enumerate(coeffs)) % q


def rank(vs, q):
    rows = [list(row) for row in vs]
    used = 0
    for j in range(len(rows[0])):
        pivot = next((i for i in range(used, len(rows)) if rows[i][j] % q), None)
        if pivot is None:
            continue
        rows[pivot], rows[used] = rows[used], rows[pivot]
        inv = pow(rows[used][j], -1, q)
        rows[used] = [v * inv % q for v in rows[used]]
        for i, r in enumerate(rows):
            if i != used:
                factor = r[j]
                rows[i] = [(v - factor * w) % q for v, w in zip(r, rows[used])]
        used += 1
    return used


def affine_counts():
    cases = 0
    for q in (2, 3, 5):
        for k in (1, 2):
            for a in vectors(q, 2*k):
                matrix = [a[:k], a[k:]]
                r = rank(matrix, q)
                counts = Counter(tuple(sum(i*j for i, j in zip(row, x)) % q
                                       for row in matrix) for x in vectors(q, k))
                for rhs in vectors(q, 2):
                    solvable = rank([list(row)+[b] for row, b in zip(matrix, rhs)], q) == r
                    assert counts[rhs] == (q**(k-r) if solvable else 0)
                    cases += 1
    return cases


def syndrome_bijection():
    # q=7, three old member points, one public point, threshold two,
    # new threshold two, one corrupt old and one corrupt new participant.
    q, old, pub = 7, (1, 2, 3), 4
    points = old + (pub,)
    weights = []
    for x in points:
        den = 1
        for y in points:
            if y != x:
                den = den*(x-y) % q
        weights.append(pow(den, -1, q))
    def view(old_polynomial, slopes):
        constants = [evaluate(old_polynomial, i, q) for i in points]
        private = tuple((a+b) % q for a,b in zip(constants, slopes))
        const = sum(w*x for w,x in zip(weights,constants)) % q
        slope = sum(w*x for w,x in zip(weights,slopes)) % q
        return private,const,slope
    g = (2, 5, 3)
    base = Counter(view(g, s) for s in vectors(q, 3))
    cases = 0
    # Every degree-<3 alternative agreeing on old point 1 and public point 4.
    for u in range(q):
        g2 = tuple((v+u*d) % q for v,d in zip(g,(4,-5,1)))
        assert base == Counter(view(g2, s) for s in vectors(q,3))
        for slopes in vectors(q,3):
            ds = [evaluate(g2,x,q)-evaluate(g,x,q) for x in old]
            mapped = tuple((s-d) % q for s,d in zip(slopes,ds))
            assert view(g,slopes) == view(g2,mapped)
            assert mapped[0] == slopes[0]
            cases += 1
    return cases


def shortened_distances():
    checks = 0
    q = 7
    for m in range(1,5):
        for p in range(0, 6-m):
            for t in range(1,m+1):
                weights=[]
                for x in range(1,m+1):
                    v=1
                    for y in range(m+1,m+p+1):
                        v=v*(x-y) % q
                    weights.append(v)
                distance = min(sum((w*evaluate(f,x,q))%q != 0
                                   for x,w in enumerate(weights,1))
                               for f in vectors(q,t) if any(f))
                assert distance == m-t+1
                checks += 1
    return checks


if __name__ == '__main__':
    summary = dict(affine_rhs_cases=affine_counts(),
                   pointwise_coupling_cases=syndrome_bijection(),
                   shortened_distance_cases=shortened_distances())
    print(json.dumps(summary, indent=2))
