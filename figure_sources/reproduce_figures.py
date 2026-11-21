"""Regenerate seven publication figures from the archived aggregate data."""
from pathlib import Path
import hashlib
import json
import os

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("SOURCE_DATE_EPOCH", "946684800")
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PNG = ROOT / "figures"
VECTOR = ROOT / "figure_sources" / "vectors"
REPORTS = ROOT / "reports"
for path in (PNG, VECTOR, REPORTS):
    path.mkdir(exist_ok=True, parents=True)
COLORS = ["#204F83", "#188A83", "#B56420", "#7862A6", "#515963", "#B84545"]
MARKERS = ["o", "s", "^", "D", "v", "P"]
STYLES = ["-", "--", "-.", ":", (0, (5, 2, 1, 2)), (0, (2, 2))]
N = [8,16,32,64,128,256]
K = [1,2,4,8,16,32,64]
WIDTH = 6.15
from matplotlib import font_manager
for face in sorted((ROOT / "assets" / "fonts").glob("P052-*.otf")):
    font_manager.fontManager.addfont(str(face))
mpl.rcParams.update({
    "font.family":"P052", "mathtext.fontset":"custom", "mathtext.rm":"P052", "mathtext.it":"P052:italic", "mathtext.bf":"P052:bold", "mathtext.fallback":"stix", "mathtext.cal":"P052:italic", "font.size":9, "axes.labelsize":9,
    "axes.titlesize":9.5, "legend.fontsize":8, "xtick.labelsize":8,
    "ytick.labelsize":8, "axes.spines.top":False, "axes.spines.right":False,
    "axes.edgecolor":"#6E7681", "axes.linewidth":.65, "axes.axisbelow":True,
    "xtick.major.width":.65, "ytick.major.width":.65,
    "svg.fonttype":"path", "svg.hashsalt":"hvmss-scientific-figures",
    "pdf.fonttype":3, "axes.titlelocation":"left",
    "legend.frameon":False, "savefig.facecolor":"white"
})
inventory = []
def table(name):
    return pd.read_csv(DATA / (name + ".csv"))

def chart(ax, x, y, index, label, lo=None, hi=None):
    color=COLORS[index]
    if lo is not None:
        assert np.all(lo <= y) and np.all(y <= hi)
        ax.errorbar(x, y, yerr=[y-lo,hi-y], fmt="none", ecolor=color,
                    elinewidth=.8, capsize=2.1, capthick=.75, zorder=1.5)
    return ax.plot(x,y,marker=MARKERS[index],ms=4.1,mfc="white",mec=color,
                   mew=.95,ls=STYLES[index],c=color,lw=1.4,label=label)[0]

def powers(ax, values):
    ax.set_xscale("log",base=2)
    ax.set_xticks(values, labels=[str(x) for x in values])
    ax.minorticks_off()
    ax.set_xlim(min(values)/1.15,max(values)*1.15)

def grid(ax):
    ax.grid(axis="y",which="major",lw=.55,color="#DFE3E8")

def export(fig, stem, sources, counts, equation, axes, caption):
    fig.savefig(VECTOR/(stem+".pdf"),metadata={"CreationDate":None,"ModDate":None})
    fig.savefig(VECTOR/(stem+".svg"), metadata={"Date":None})
    dest=PNG/(stem+".png")
    fig.savefig(dest,dpi=600)
    with Image.open(dest) as raw:
        rgb=raw.convert("RGB")
    rgb.save(dest,dpi=(600,600))
    inventory.append(dict(stem=stem,sources=sources,counts=counts,equation=equation,
                          axes=axes,pixels=list(rgb.size),caption=caption))
    plt.close(fig)

def architecture():
    fig=plt.figure(figsize=(WIDTH,4.88))
    ax=fig.add_axes([.005,.01,.99,.98]); ax.set_xlim(0,10); ax.set_ylim(0,8); ax.axis("off")
    heights=.85
    def node(x,y,w,msg,col):
        r=patches.FancyBboxPatch((x,y),w,heights,boxstyle="round,pad=0.06,rounding_size=0.10",
                ec=col,lw=.9,fc="#F7FAFB")
        ax.add_patch(r); ax.text(x+w/2,y+heights/2,msg,ha="center",va="center",fontsize=8.25)
    def arrow(x1,y1,x2,y2,col="#56606B",dash=False):
        ax.annotate("", xy=(x2,y2),xytext=(x1,y1),
                    arrowprops=dict(arrowstyle="-|>",color=col,linewidth=1,
                                    shrinkA=1.25,shrinkB=1.25,linestyle="--" if dash else "-"))
    ax.text(.15,7.62,"(a)  Reusable-share multi-secret sharing",weight="bold",color=COLORS[0])
    for x,msg in [(.2,"Trusted dealer\nseed setup"),(3.62,"Private seeds\n$\\sigma_i$"),(7.04,"Session values\n$u_{i,j}, v_i, \\gamma_{i,j}$")]:
        node(x,6.18,2.7,msg,COLORS[0])
    arrow(2.98,6.6,3.54,6.6,dash=True)
    arrow(6.4,6.6,6.97,6.6)
    node(6.94,4.5,2.8,"Public values at $X'$\nsalted digests, response",COLORS[0])
    node(3.52,4.5,2.9,"Verify public record\nand recipient values",COLORS[0])
    node(.2,4.5,2.7,"Reconstruct from $t$\nopenings and $X'$",COLORS[0])
    arrow(8.39,6.09,8.39,5.43)
    arrow(6.87,4.93,6.49,4.93)
    arrow(3.44,4.93,2.97,4.93)
    ax.text(.15,3.78,"(b)  Dealer-free redistribution",weight="bold",color=COLORS[1])
    for x,msg in [(.2,"Old committee\nthreshold $t$"),(3.62,"Subdealer rows\nand HBV row proofs"),(7.04,"New members publish\nsyndrome evaluations")]:
        node(x,2.35,2.7,msg,COLORS[1])
    arrow(2.98,2.78,3.55,2.78)
    arrow(6.4,2.78,6.96,2.78,dash=True)
    node(6.92,.66,2.82,"Check syndromes\ndecode or abort",COLORS[1])
    node(3.52,.66,2.9,"Combine valid rows\nusing old weights",COLORS[1])
    node(.2,.66,2.7,"New Shamir shares\nthreshold $t'$",COLORS[1])
    arrow(8.39,2.26,8.39,1.58)
    arrow(6.84,1.08,6.49,1.08)
    arrow(3.45,1.08,2.98,1.08)
    ax.text(.18,.16,"Dashed arrows indicate private delivery. Public records use authenticated broadcast.",fontsize=8,color="#46525A")
    export(fig,"fig01_architecture",["main.tex"],"2 protocol stages",
           "p = n − t + 1","Protocol roles and data dependencies",
           "RMSS begins with trusted private seed delivery. The dealer and each participant derive session-specific values. Reconstruction uses t authenticated openings and the public interpolation values. During DFR, old members privately deliver row values and broadcast row proofs. The new committee retains ordinary Shamir shares at threshold t′. DFR does not provision fresh RMSS seeds.")

def security():
    q=2**255-19
    b=np.linspace(0,80,321)
    Q=np.exp2(b)
    challenge=(Q+1)/float(q)
    collision=np.exp2(2*b-257)
    total=challenge+collision
    assert np.log2(collision[-1])==-97 and np.all(total>=challenge)
    fig,ax=plt.subplots(figsize=(WIDTH,3.35))
    fig.subplots_adjust(left=.125,right=.975,bottom=.18,top=.81)
    ax.plot(b,np.log2(total),c=COLORS[2],lw=3.0,label="Sum of bounds",alpha=.85)
    ax.plot(b,np.log2(challenge),c=COLORS[0],ls="--",lw=1.5,label="Challenge")
    ax.plot(b,np.log2(collision),c=COLORS[4],ls=":",lw=1.65,label="Collision")
    ax.axhline(-128,lw=.8,ls=(0,(5,3)),c="#B84545")
    ax.text(1,-124,r"$2^{-128}$ reference",color="#9B3838",fontsize=8)
    ax.scatter(80,-97,c=COLORS[2],s=16,zorder=4)
    ax.annotate(r"$Q=2^{80}$: collision term $2^{-97}$",xy=(80,-97),xytext=(39,-88),
                fontsize=8,arrowprops=dict(arrowstyle="-",lw=.7,color=COLORS[2]))
    ax.set(xticks=[0,16,32,48,64,80],xlim=(0,82),ylim=(-263,-78),
           xlabel=r"Oracle-query budget, $\log_2 Q$",ylabel=r"$\log_2$ probability upper bound")
    grid(ax); ax.legend(loc="lower left",bbox_to_anchor=(-.03,1.01),ncol=3)
    export(fig,"fig02_security",[],"321 formula evaluations",
           "(Q+1)/q + Q²/2²⁵⁷, q = 2²⁵⁵ − 19; illustrative two-term bound only",
           "x: log2 Q; y: log2 probability upper bound",
           "Illustrative two-term consistency upper bound for independent challenges. The orange line sums the challenge and collision contributions. At Q = 2⁸⁰ the collision term equals 2⁻⁹⁷; the sum lies slightly above it. Late openings, sampling bias and other deployment-specific events require separate accounting.")

def dictionary():
    df=table("dictionary_attack")
    assert set(df.field_bits)=={127,255,521}
    a=df[df.salted==0]; s=df[df.salted==1]
    assert a.recovered.sum()==a.trials.sum()==160 and s.trials.sum()==79 and s.total_matches.sum()==0
    assert np.allclose(2.**df.dictionary_bits / df.mean_time_s,df.candidates_per_s)
    fig,axes=plt.subplots(1,2,figsize=(WIDTH,3.42),gridspec_kw=dict(width_ratios=[1.2,1]))
    fig.subplots_adjust(left=.12,right=.98,top=.72,bottom=.17,wspace=.42)
    for idx,field in enumerate([127,255,521]):
        t=a[a.field_bits==field].sort_values("dictionary_bits")
        chart(axes[0],t.dictionary_bits,t.mean_time_s,idx,str(field)+"-bit field")
        chart(axes[1],t.dictionary_bits,t.candidates_per_s/1e6,idx,str(field)+"-bit field")
    bits=np.array([8,12,16,20,24])
    ref=2.**bits/4.0e6
    axes[0].plot(bits,ref,ls=(0,(2,3)),lw=1,c=COLORS[4],label=r"Reference $T\propto D$")
    axes[0].set_yscale("log");axes[0].set_ylabel("Mean time (s)")
    axes[1].set_ylabel("Million candidates/s");axes[1].set_ylim(0,2.05)
    axes[0].set_title("(a)  Enumeration time");axes[1].set_title("(b)  Candidate rate")
    for ax in axes:
        ax.set_xticks(bits,[f"$2^{{{x}}}$" for x in bits]);ax.set_xlabel("Dictionary size, $D$")
        grid(ax)
    fig.legend(*axes[0].get_legend_handles_labels(),loc="upper center",bbox_to_anchor=(.51,1.01),ncol=2)
    export(fig,"fig03_dictionary",["data/dictionary_attack.csv"],"26 aggregate records; 160 deterministic and 79 salted trials",
           "rate = D / mean elapsed time; illustrative T = D/(4×10⁶) seconds",
           "x: dictionary size in powers of two; y: mean seconds (log scale), millions of candidates per second",
           "Time and candidate rate for deterministic commitments, n = 5 and t = 3. Points average 1–20 exhaustive trials per setting. The dotted proportionality guide is theoretical and its normalization is illustrative. In 79 separate salted controls the same candidate-only procedure found zero matches; those runs consumed positive time. Only the 255-bit configuration includes a dictionary of size 2²⁴. The candidate count is fixed by the dictionary, while measured throughput varies with field size.")

def corruption():
    df=table("dfr_errors")
    assert (df.trials==200).all()
    assert ((df.correct_output+df.wrong_output+df.aborted)==df.trials).all()
    old=df[df.setting=="old"];new=df[df.setting=="new"]
    assert len(old)==34 and len(new)==13
    oldsel=[("Random: detected","random","detected"),("Random: correct output","random","correct_output"),
            ("Structured: detected","structured","detected"),("Structured: correct output","structured","correct_output")]
    newsel=[("Detected","random","detected"),("Recovered syndrome","random","correct_output"),("Aborted","random","aborted")]
    fig,axes=plt.subplots(2,1,figsize=(WIDTH,4.26),gridspec_kw=dict(height_ratios=[4,3]))
    fig.subplots_adjust(left=.315,right=.98,top=.90,bottom=.18,hspace=.76)
    cmap=LinearSegmentedColormap.from_list("outcomes",["#F3F5F6",COLORS[0]])
    for panel,(ax,subset,selection) in enumerate(zip(axes,[old,new],[oldsel,newsel])):
        arr=np.array([(x[field]/x.trials).values for _,kind,field in selection
                      for x in [subset[subset.kind==kind].sort_values("corrupted")]])
        assert set(arr.flatten())=={0,1}
        ax.imshow(arr,aspect="auto",cmap=cmap,vmin=0,vmax=1,interpolation="nearest")
        ax.set_yticks(range(len(selection)),[v[0] for v in selection])
        ax.tick_params(axis="y",length=0)
        xs=np.arange(arr.shape[1]); ax.set_xticks(xs[::2],xs[::2])
        ax.set_xticks(xs[:-1]+.5,minor=True); ax.set_yticks(np.arange(len(selection)-1)+.5,minor=True)
        ax.grid(which="minor",c="white",lw=.55);ax.tick_params(which="minor",length=0)
        ax.spines[["top","bottom","left","right"]].set_visible(False)
        if panel==0:
            marks=[(4.5,"$c=4$"),(8.5,"$c=8$")]
            title="(a)  Old-coordinate errors"
        else:
            marks=[(7.5,"$c'=7$")]
            title="(b)  False new broadcasts"
        for x_at,note in marks:
            ax.axvline(x_at,c="#C16A13",lw=1.4)
            ax.text(x_at,-.65,note,va="bottom",ha="center",fontsize=7.7)
        ax.set_title(title,pad=15,loc="left")
        ax.set_xlabel("Corrupt old members, $c$" if panel==0 else "Corrupt new members, $c'$")
    fig.legend(handles=[patches.Patch(fc=cmap(0.),ec="#CCD2D8",label="0 / 200 trials"),
                        patches.Patch(fc=cmap(1.),label="200 / 200 trials")],
               loc="lower center",bbox_to_anchor=(.59,.004),ncol=2)
    export(fig,"fig04_corruption",["data/dfr_errors.csv"],"47 configurations × 200 = 9,400 generated trials",
           "Old radius floor((16−8)/2) = 4; last guaranteed old agreement c=8. New radius floor((20−6)/2)=7.",
           "x: corruption count; rows: recorded outcomes; color: successes out of 200",
           "Exact syndrome checking in 200 trials per configuration. (a) Old coordinate errors with m = 16, t = 8 and R = 8. Recovery is guaranteed through four errors; the old honest-count condition holds through eight. Random errors were detected in the sampled nonzero-error trials; the modeled structured shift escaped detection above eight. (b) False syndrome broadcasts with n′ = 20 and t′ = 6. The recovered old-error map was empty through seven errors; the harness recorded abort beyond seven. At zero corruptions a correct result needs no correction. Vertical lines follow the last count covered by each indicated boundary.")

def scale_series(ax,df,op,idx,name):
    d=df[df.operation==op].sort_values("n")
    assert list(d.n)==N and all(d.t==d.n//2)
    med=d.median_ms.values
    if d.q1_ms.isna().all():
        assert op=="DFR.CriticalPath"
        chart(ax, d.n, med, idx, name)
    else:
        chart(ax,d.n,med,idx,name,d.q1_ms.values,d.q3_ms.values)

def scalability():
    df=table("timings")
    fig,ax=plt.subplots(figsize=(WIDTH,3.60))
    fig.subplots_adjust(left=.12,right=.98,top=.76,bottom=.17)
    ops=["HBV.Deal","HBV.Verify","RMSS.Add","RMSS.VerifyMember","RMSS.VerifyPublic","DFR.CriticalPath"]
    names=["HBV deal","HBV verify","RMSS add","RMSS verify","RMSS public check","DFR path (modeled)"]
    for idx,(op,name) in enumerate(zip(ops,names)):
        scale_series(ax,df,op,idx,name)
    powers(ax,N);ax.set_yscale("log");grid(ax)
    ax.set(xlabel="Committee size, $n$",ylabel="Computation time (ms)")
    fig.legend(*ax.get_legend_handles_labels(),loc="upper center",ncol=3,bbox_to_anchor=(.52,.99))
    export(fig,"fig05_scalability",["data/timings.csv","data/timings_raw.csv"],"30 measured medians × 21 timings plus 6 calculated DFR sums",
           "DFR path = re-sharing + row verification + syndrome evaluation + batched check + share formation; sum of operation medians",
           "x: n, base-2 log scale; y: milliseconds, log scale",
           "Computation by committee size for one secret and t = n/2. Each directly timed operation shows the median of 21 runs after three warm-ups; whiskers give the interquartile range. Some whiskers fall inside the markers. The DFR path sums five operation medians with m = n′ = n and t′ = t. No distribution of end-to-end DFR latency was measured.")

def comparison():
    df=table("timings");b=table("baselines")
    fig,axes=plt.subplots(1,2,figsize=(WIDTH,3.81),sharey=True)
    fig.subplots_adjust(left=.12,right=.98,bottom=.16,top=.69,wspace=.16)
    items=[("HBV.Verify","HBV.Deal","HBV"),("RMSS.VerifyMember","RMSS.Add","RMSS"),
           ("Feldman-secp256k1.Verify","Feldman-secp256k1.Deal","Feldman / secp256k1"),
           ("Pedersen-secp256k1.Verify","Pedersen-secp256k1.Deal","Pedersen / secp256k1"),
           ("Feldman-3072.Verify","Feldman-3072.Deal","Feldman / MODP"),
           ("Pedersen-3072.Verify","Pedersen-3072.Deal","Pedersen / MODP")]
    for idx,(ver,deal,name) in enumerate(items):
        for ax,op in zip(axes,[ver,deal]):
            scale_series(ax,df if idx<2 else b,op,idx,name)
    for ax,label in zip(axes,["(a)  Share verification","(b)  Dealing / session addition"]):
        powers(ax,N);ax.set_yscale("log");grid(ax);ax.set_title(label)
        ax.set_xlabel("Committee size, $n$")
    axes[0].set_ylabel("Computation time (ms)")
    fig.legend(*axes[0].get_legend_handles_labels(),loc="upper center",bbox_to_anchor=(.51,.99),ncol=2,columnspacing=1.1)
    f=b[(b.operation=="Feldman-secp256k1.Verify") & (b.n==256)].median_ms.iloc[0]
    h=df[(df.operation=="HBV.Verify") & (df.n==256)].median_ms.iloc[0]
    assert round(f/h,1)==17.9
    export(fig,"fig06_comparison",["data/timings.csv","data/baselines.csv","data/timings_raw.csv"],
           "72 operation/configuration medians × 21 observations",
           "Selected 256-member verification-time ratio = "+format(f/h,".4f"),
           "x: n, base-2 log scale; y: milliseconds, log scale with common limits",
           "Single-recipient verification and dealing for t = n/2, one secret, medians and interquartile ranges of 21 runs. HBV and RMSS use Python; secp256k1 uses Python with the native libsecp256k1 backend; MODP-3072 uses Python modular exponentiation. Group parameters, dealing coefficients and verification exponents are prepared outside the group timings; HBV dealing includes fresh randomness, and RMSS addition uses precomputed interpolation geometry. The measurement compares implementations with different verification and trust guarantees. At n = 256 the selected secp256k1 Feldman verification median was 17.9 times the HBV median.")

def batching():
    df=table("batch")
    n,t=32,16;p=n-t+1
    assert set(df.n)=={n} and set(df.t)=={t}
    fig,axes=plt.subplots(1,2,figsize=(WIDTH,3.74))
    fig.subplots_adjust(left=.11,right=.98,top=.74,bottom=.18,wspace=.43)
    labels=["HBV deal","HBV verify","RMSS add","RMSS verify"]
    for idx,op in enumerate(["HBV.Deal","HBV.Verify","RMSS.Add","RMSS.VerifyMember"]):
        d=df[df.operation==op].sort_values("k")
        assert list(d.k)==K and np.allclose(d.median_ms/d.k,d.per_secret_ms)
        expected=32*(n+t) if idx<2 else 32*(d.k*p+p+n+1+d.k*n)
        assert np.all(d.broadcast_bytes==expected)
        assert np.allclose(d.broadcast_bytes/d.k,d.broadcast_bytes_per_secret)
        chart(axes[0],d.k,d.per_secret_ms,idx,labels[idx])
        if idx in [0,2]:
            chart(axes[1],d.k,d.broadcast_bytes_per_secret,idx,["HBV","RMSS"][idx//2])
    axes[1].axhline(32*(p+n),ls=":",lw=1.3,c="#515963",label="RMSS limit")
    for ax,label in zip(axes,["(a)  Computation","(b)  Public payload"]):
        powers(ax,K);ax.set_yscale("log");grid(ax);ax.set_title(label);ax.set_xlabel("Secrets per batch, $k$")
    axes[0].set_ylabel("Median ms / secret"); axes[1].set_ylabel("Bytes / secret")
    for ax in axes:
        ax.legend(loc="lower center",bbox_to_anchor=(.49,1.15),ncol=2,fontsize=7.5,columnspacing=.7,handlelength=1.6)
    export(fig,"fig07_batching",["data/batch.csv"],"28 aggregate timing/payload records; 7 batch sizes",
           "HBV = 32(n+t)/k; RMSS = 32(p+n)+32(p+n+1)/k = 1568+1600/k bytes",
           "x: secrets per batch, base-2 log scale; y: median milliseconds or logical public bytes per secret, log scale",
           "Amortization at n = 32, t = 16 and p = 17. (a) Median time for a batch divided by k. (b) Logical broadcast bytes divided by k, excluding authentication, network framing and replication. HBV transmits 1536 bytes per batch; the RMSS per-secret payload is 1568 + 1600/k bytes and approaches 1568 bytes.")

def check_archive():
    # Archive writes the protocol block before batch blocks; "run" is a rank
    # within sorted samples rather than a chronological timestamp.
    raw=table("timings_raw")
    groups=raw.groupby(["operation","n"],sort=False)
    for name in ("timings","baselines"):
        for row in table(name).itertuples():
            if str(row.reps)!="21":
                continue
            first=groups.get_group((row.operation,row.n)).ms.iloc[:21]
            assert len(first)==21
            assert np.allclose(np.quantile(first,[.25,.5,.75]),
                               [row.q1_ms,row.median_ms,row.q3_ms],rtol=1e-10)
    for row in table("batch").itertuples():
        data=groups.get_group((row.operation,row.n)).ms.to_numpy().reshape(-1,21)
        block=K.index(row.k)+1
        assert np.isclose(np.median(data[block]),row.median_ms,rtol=1e-10)

def write_reports():
    report=["# Figure validation","",
            "All seven figures were redrawn. Original figure images were not inputs. Numerically plotted source records are archived aggregates; probability curves are analytical. PNG files use 600 dpi and RGB. PDF and SVG exports are vector graphics. Each graphic is 6.15 inches wide at its nominal size.","",
            "Regenerate from any working directory with `python figure_sources/reproduce_figures.py` from the project root (or pass the absolute path to the script). Dependencies: Python 3, NumPy, Pandas, Matplotlib and Pillow.",""]
    for i,entry in enumerate(inventory,1):
        report += ["## Figure "+str(i)+" · "+entry["stem"],"",
                   "- Inputs: "+(", ".join(entry["sources"]) or "analytical expression in script"),
                   "- Scope: "+entry["counts"],"- Quantities: "+entry["equation"],"- Axes or layout: "+entry["axes"],
                   "- Raster dimensions: "+" × ".join(map(str,entry["pixels"]))+" px; RGB PNG. Editable SVG and vector PDF in figure_sources/vectors/.",
                   "",entry["caption"],""]
    (REPORTS/"figure_validation.md").write_text("\n".join(report),encoding="utf-8")
    for entry in inventory:
        entry["input_sha256"]={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                               for name in entry["sources"] if name.startswith("data/")}
    (REPORTS/"figure_metadata.json").write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":
    check_archive()
    architecture();security();dictionary();corruption();scalability();comparison();batching();write_reports()
