"""Primality of q = 2^255 - 19 with FLINT's primality-proving routine (fmpz_is_prime)."""
import json, pathlib
import flint
q = 2**255 - 19
res = int(flint.fmpz(q).is_prime())
assert res == 1
out = {"q": "2^255-19", "python_flint": flint.__version__, "method": "fmpz.is_prime (primality proving)", "result": res}
(pathlib.Path(__file__).resolve().parents[1] / "results" / "primality_check.json").write_text(json.dumps(out, indent=2))
print(out)
