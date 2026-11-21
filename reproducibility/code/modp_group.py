"""Generation of the MODP-3072 Schnorr group used by the Feldman/Pedersen baselines.

p = k*q + 1 is a 3072-bit prime with a 256-bit prime-order subgroup; g = 2^k mod p and
h = 3^k mod p are subgroup elements whose mutual discrete logarithm is unknown.
The stored parameters in ../results/modp3072_group.json were produced by this script.
"""
import json, math, pathlib, random, sympy
OUT = pathlib.Path(__file__).resolve().parents[1] / "results" / "modp3072_group.json"
rng = random.Random(8032026)
q = int(sympy.nextprime(2**256 - 2**32))
small = math.prod(sympy.primerange(3, 2000))
attempts = 0
while True:
    k = (rng.getrandbits(2816) | (1 << 2815)) & ~1
    p = k * q + 1
    attempts += 1
    if p.bit_length() != 3072 or math.gcd(p, small) != 1:
        continue
    if sympy.isprime(p):
        break
g, h = pow(2, k, p), pow(3, k, p)
assert g != 1 and h not in (1, g) and pow(g, q, p) == 1 and pow(h, q, p) == 1
if __name__ == "__main__":
    OUT.write_text(json.dumps(dict(p=p, q=q, g=g, h=h, attempts=attempts, primality="SymPy BPSW probable-prime test", seed=8032026), indent=2))
    print("written", OUT)
