"""Rebuild all nine manuscript tables from project data and assessed protocol definitions."""
import csv
import math
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tables"
OUT.mkdir(exist_ok=True)
TAB = r"\begin{tabularx}{\linewidth}"
END = r"\end{tabularx}"
RULE = r"\midrule"
ROW = r" \\"
def csvrows(source):
    with (ROOT / "data" / (source + ".csv")).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
def nfmt(n):
    return format(int(n),",d").replace(",",r"\,")
def sig(v,d=3):
    return nfmt(round(float(v))) if abs(float(v)) >= 1000 else format(float(v),f".{d}g")
def row(*args):
    return " & ".join(map(str,args)) + ROW
def table(key, caption, contents, note=""):
    text = [r"\begin{table}[htbp]",r"\caption{"+caption+r"}\label{tab:"+key+"}",r"\centering\small",r"\setlength{\tabcolsep}{3pt}", *contents]
    if note:
        text.extend([r"\par\smallskip",r"\begin{minipage}{\linewidth}\small "+note+r"\end{minipage}"])
    (OUT / (key+".tex")).write_text("\n".join([*text, r"\end{table}", ""]), encoding="utf-8")
def tabx(cols, headings, rows):
    return [TAB+"{@{}"+cols+"@{}}", r"\toprule",row(*headings),RULE,*rows,r"\bottomrule",END]
def plain(cols,headings,rows):
    return [r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}"+cols+"@{}}",r"\toprule",row(*headings),RULE,*rows,r"\bottomrule",r"\end{tabular*}"]
def theory_tables():
    families=[
      (r"Shamir~\cite{r0}","Polynomial threshold sharing","An honest dealer distributes fresh shares. Any coalition smaller than the threshold has perfect privacy."),
      (r"Feldman~\cite{r3}","Coefficient commitments","The public record fixes group elements for coefficients. The constant commitment permits testing candidate secrets."),
      (r"Pedersen~\cite{r4}","Hiding coefficient commitments","Public parameters require generators of unknown relative discrete logarithm. Hiding is perfect and binding computational."),
      (r"Atapoor et al.; Baghery~\cite{r5,r6}","Proof-based verification","Security and delivery guarantees depend on the particular VSS construction and communication model."),
      (r"Yang et al. and variants~\cite{r7,r8,r9}","Multi-secret interpolation","The dealer publishes auxiliary evaluations. Authentication of participant inputs depends on the variant."),
      (r"Shao~\cite{shaohash}","Hash-based verifiable multi-secret sharing","Reusable multi-secret verification has prior art. The present analysis concerns a particular interpolation and disclosure interface."),
      (r"CHURP~\cite{r11}","Dynamic committee service","Committee changes and proactive security are analyzed under the protocol's own corruption and communication assumptions."),
      ("HBV, RMSS and DFR","Recipient checks, seed reuse, committee transfer","RMSS trusts the setup dealer. Fixed-set consistency permits abort. DFR assumes a valid old sharing and authenticated broadcasts.")]
    table("prior","Representative constructions and the functionality relevant to this comparison.",tabx(r"p{.23\linewidth}p{.24\linewidth}X",("Construction","Mechanism","Trust and scope"),[row(*i) for i in families]))
    symbols=[
      (r"$q,b$","Prime field order and byte width of a field element."),
      (r"$n,t;\ n',t'$","Old and new committee sizes and reconstruction thresholds."),
      (r"$m,p;\ C,X'$","Number and set of participating old members; number and set of authenticated public coordinates, respectively."),
      (r"$d,L,R$","Code dimension, evaluation length, and redundancy in the coding analysis; $R=L-d=m-t$ for DFR."),
      (r"$K,k$","Number of sessions and number of secrets in one batch."),
      (r"$h,\ell,\kappa$","Digest length, secret opening-salt length, and persistent seed length in bits."),
      (r"$Q_F,Q_C,Q_S$","Query budgets for challenges, commitments, and guesses of a seed across the applicable oracle domains."),
      (r"$B,M,V,N_C$","Number of attempts, distinct digest inputs, late opening evaluations, and digest targets for late openings."),
      (r"$N_F,\delta_q$","Number of field samples and single-sample statistical distance from uniform."),
      (r"$S,A,A'$","Honest checked set, corrupt old set, and corrupt new set."),
      (r"$P,\rho$","Parity-check matrix and rank of the matrix of secret-vector syndromes.")]
    table("notation","Notation used in the protocol definitions and bounds.",tabx(r"p{.23\linewidth}X",("Symbol","Meaning"),[row(*i) for i in symbols]))
    scopes=[
      ("HBV consistency",r"A feasible affine system admits a response with probability $q^{-\rho}$, an infeasible system with probability zero.","Fixed honest set, fixed tuples, and independent uniform challenges. Hash instantiation introduces separate terms."),
      ("HBV privacy","The masked algebraic transcript has equal distributions across secrets.","Honest dealer, fewer than $t$ exposed positions. Unopened hash labels require the finite-query privacy hybrid."),
      ("RMSS",r"$t$ authentic honest-dealer openings plus $p$ public evaluations reconstruct. The consistency bound controls joint acceptance and inconsistency.","Agreed public record, honest setup and distinct session identifiers. The dealer retains all seeds; privacy is finite-session and static."),
      ("DFR preservation","Exact syndrome checks link valid row constants to the original codeword.","Consistent rows and at least $t$ honest participating old and $t'$ honest new members. Authentication, agreement and delivery are external."),
      ("DFR privacy and recovery","A row translation preserves the algebraic view. Each stage has its own unique-decoding radius.","Identical prior auxiliary information. Recovery requires error counts within the respective radii; private randomized checks add a failure event."),
      ("Repeated epochs","A first-failure union bound composes conditional per-epoch estimates.","Each estimate must hold after every admissible prior history. Mobile corruption requires a separate model.")]
    table("scope","Established properties and the assumptions that delimit them.",tabx(r"p{.18\linewidth}XX",("Property","Established statement","Required conditions or limits"),[row(*i) for i in scopes]))
def experiment_tables():
    good=csvrows("correctness")
    counts=plain("lrrrr",("Component","Executions","Checks","Reconstructions","Failures"),[row(i["component"],*[nfmt(i[x]) for x in ("executions","verifications","reconstructions","failures")]) for i in good])
    attacks=csvrows("detection")
    counts += [r"\par\medskip"]+tabx("Xrr",("Injected deviation","Detected","Trials"),[row(i["deviation"].replace("y_x","$y_x$"),nfmt(i["detected"]),nfmt(i["trials"])) for i in attacks])
    table("tests",r"Recorded functional and deviation tests at $q=2^{255}-19$.",counts,"Checks count recipient openings for HBV, public and member verifications for RMSS, and row-opening verifications for DFR. The DFR sample comprises 20 chains of 50 transitions. The lower panel counts detections for the specified deviations.")
    examples=[]
    cases={"solvable":"Feasible","unsolvable":"Infeasible","adversarial roots":"Chosen roots","same vectors":"Paired vectors"}
    for i in csvrows("soundness_exhaustive"):
        q,k,rank=int(i["q"]),int(i["k"]),int(i["rank"])
        powers=i["challenge"]=="scalar-power"; inf=i["case"]=="unsolvable"
        expected=Fraction(0) if inf else (Fraction(k,q) if powers else Fraction(1,q**rank))
        num,den=int(i["accepted"]),int(i["total"])
        assert Fraction(num,den)==expected and math.isclose(float(expected),float(i["theory"]))
        if q==13:
            theory="0" if inf else (r"k/q" if powers else r"q^{-"+str(rank)+"}")
            examples.append(row("Powers" if powers else "Independent",k,rank,cases[i["case"]],nfmt(num)+"/"+nfmt(den),"$"+theory+"$"))
    table("exhaustive",r"Exact response-feasibility counts over $\mathbb{F}_{13}$ for a length-six, dimension-two code.",plain("lrrlrr",("Challenge","$k$",r"$\rho$","Instance","Accepted/total","Prediction"),examples),r"The chosen-root examples attain the scalar-power upper bound for their specific vectors. Independent challenges on the same vectors give the paired rows. The archived data cover 48 instances at $q\in\{7,11,13,17\}$.")
    rates=[]
    for i in csvrows("grinding"):
        if not i["q"].isdigit():
            continue
        small=i["q"].isdigit(); attempts=int(i["total_attempts"]);hits=int(i["successes"])
        assert math.isclose(hits/attempts,float(i["per_attempt_acceptance"]))
        q=i["q"] if small else r"$2^{255}-19$"
        mean=(f"{float(i['mean_attempts']):,.1f}".replace(",",r"\,")+r" $\pm$ "+f"{float(i['ci95_half']):.1f}") if small else "--"
        rates.append(row(q,nfmt(hits)+"/"+nfmt(attempts),f"{hits/attempts:.5f}" if hits else "0",mean,f"$1/{q}$" if small else r"$1/(2^{255}-19)$"))
    table("grinding","Fiat--Shamir challenge trials with eight recipients and threshold three.",plain("lrrrr",("$q$","Hits/trials","Fraction","Trials/hit","Theory per trial"),rates),r"Small-field runs stopped at 1000 hits. Trials/hit gives the sample mean and approximate 95\% confidence half-width.")
    privacy=csvrows("privacy")
    names=[r"RMSS algebraic view at $q=7,n=3,t=2$, fixed challenge",r"Same RMSS view augmented with honest pseudo-shares",r"HBV algebraic view at $q=7,n=4,t=3$, fixed challenge",r"DFR transcript-preserving translation at $q=2^{255}-19$"]
    results=[]
    for name,i in zip(names,privacy):
        val=i["max_tv_distance"]
        results.append(row(name,nfmt(i['instances']),("TV $="+str(int(float(val)))+"$") if val else nfmt(i["passed"])+"/"+nfmt(i["instances"])))
    table("privacy","Finite-field privacy enumerations and a separate DFR translation check.",tabx("Xrr",("Experiment","Instances","Result"),results),r"TV is the maximum total-variation distance between the distribution for secret zero and each other secret. The second row exposes actual honest pseudo-shares, modeling injective deterministic labels on the small domain. The fourth row counts passing checks. These experiments exclude the computational hidden-input guessing term.")
def perf_tables():
    times=csvrows("timings")
    time={(v["operation"],int(v["n"])):v for v in times}
    names={"HBV.Deal":"HBV deal","HBV.Verify":"HBV verify","HBV.Reconstruct":"HBV reconstruct","RMSS.Add":"RMSS add","RMSS.VerifyMember":"RMSS member check","RMSS.VerifyPublic":"RMSS public check","RMSS.Reconstruct":"RMSS reconstruct","DFR.Reshare":"DFR re-share","DFR.VerifyRows":"DFR verify rows","DFR.Syndromes":"DFR syndromes","DFR.Check":"DFR batched check","DFR.CheckExact":"DFR exact check","DFR.NewShare":"DFR new share","DFR.CriticalPath":"DFR sum of medians"}
    trows=[]
    for name,lab in names.items():
        v=time[name,256]
        quarts=sig(v["q1_ms"])+"--"+sig(v["q3_ms"]) if v["q1_ms"] else "--"
        trows.append(row(lab,*[sig(time[name,n]["median_ms"]) for n in (8,16,32,64,128,256)],quarts))
    table("timings","Reference operation times in milliseconds for one secret.",plain("lrrrrrrr",("Operation","8","16","32","64","128","256",r"$Q_1$--$Q_3$, 256"),trows),r"The numbered columns give medians by committee size $n$ with $m=n'=n$ and $t=t'=n/2$. Each directly measured operation used 21 runs after three warm-ups. The final column gives quartiles at $n=256$. The DFR aggregate adds separate component medians; the archive contains no paired epoch measurements for its quartiles.")
    bl={(v["operation"],int(v["n"])):v for v in csvrows("baselines")}
    base=[("HBV","HBV.Deal","HBV.Verify",time,80,"Recipient verifies its opening."),("RMSS","RMSS.Add","RMSS.VerifyMember",time,0,"Reusable seeds and public session addition."),("Feldman EC","Feldman-secp256k1.Deal","Feldman-secp256k1.Verify",bl,32,"Group commitment to each coefficient."),("Pedersen EC","Pedersen-secp256k1.Deal","Pedersen-secp256k1.Verify",bl,64,"Hiding coefficient commitments."),("Feldman MODP","Feldman-3072.Deal","Feldman-3072.Verify",bl,32,"Group commitment to each coefficient."),("Pedersen MODP","Pedersen-3072.Deal","Pedersen-3072.Verify",bl,64,"Hiding coefficient commitments.")]
    pay={v["quantity"]:int(v["measured_bytes"]) for v in csvrows("payloads") if int(v["n"])==256}
    tr=[];pr=[]
    for lab,deal,verify,source,p,func in base:
        def med(op,n):return float(source[op,n]["median_ms"])
        ratio=med(verify,256)/float(time["HBV.Verify",256]["median_ms"])
        key=lab+"_broadcast" if lab in {"HBV","RMSS"} else ("Feldman/Pedersen-secp256k1_broadcast" if lab.endswith("EC") else "Feldman/Pedersen-3072_broadcast")
        tr.append(row(lab,sig(med(deal,64)),sig(med(deal,256)),sig(med(verify,64)),sig(med(verify,256)),f"{ratio:,.1f}".replace(",",r"\,")))
        pr.append(row(lab,nfmt(pay[key]),nfmt(p),func))
    content=plain("lrrrrr",("Scheme","Deal 64","Deal 256","Verify 64","Verify 256","Ratio"),tr)
    content += [r"\par\medskip"] + tabx("lrrX",("Scheme","Public (B)","Private (B)","Verified functionality"),pr)
    table("baselines",r"Implementation comparison at $t=n/2$ for one secret.",content,r"Top: medians in milliseconds at the stated $n$. Ratio divides the unrounded verification median at 256 by the HBV median. Bottom: logical public payload per dealing and private payload per recipient at $n=256$. RMSS setup stores 48 private bytes per recipient. EC uses secp256k1 and MODP uses a 3072-bit modulus. Authentication, network replication and transport framing add further costs.")
if __name__ == "__main__":
    theory_tables()
    experiment_tables()
    perf_tables()
