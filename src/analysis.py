"""Run the SQL queries, build charts and print findings.
Run:  python src/analysis.py   (after python src/generate_data.py)
"""
import sqlite3
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
IMG, REP = ROOT / "images", ROOT / "reports"
IMG.mkdir(exist_ok=True); REP.mkdir(exist_ok=True)
sns.set_theme(style="whitegrid", font_scale=0.95)

df = pd.read_csv(ROOT / "data" / "verification_sessions.csv", parse_dates=["started_at"])
con = sqlite3.connect(":memory:")
df.to_sql("verification_sessions", con, index=False)

def q(name):
    return pd.read_sql_query((ROOT / "sql" / name).read_text(), con)

funnel = q("01_funnel_overall.sql")
ocr_seg = q("02_ocr_by_doc_and_device.sql")
fail = q("03_failure_reasons.sql")
ver = q("04_app_version_regression.sql")

# python-side latency benchmark (same as sql/05 on PostgreSQL)
lat = (df.dropna(subset=["ocr_latency_ms"]).groupby("doc_type")["ocr_latency_ms"]
       .agg(calls="count", p50_ms=lambda s: s.quantile(.5), p95_ms=lambda s: s.quantile(.95),
            pct_over_3s=lambda s: 100 * (s > 3000).mean()).round(1).sort_values("p95_ms", ascending=False))

# ---------- charts ----------
# 1 funnel
fig, ax = plt.subplots(figsize=(7.5, 3.8))
ax.barh(funnel.stage[::-1], funnel.pct_of_start[::-1], color="#2f6fb5")
for i, (v, s) in enumerate(zip(funnel.pct_of_start[::-1], funnel.sessions[::-1])):
    ax.text(v + 1, i, f"{v:.1f}%  ({int(s):,})", va="center", fontsize=9)
ax.set_xlim(0, 118); ax.set_xlabel("% of sessions started"); ax.set_title("Verification funnel")
plt.tight_layout(); plt.savefig(IMG / "01_funnel.png", dpi=150); plt.close()

# 2 heatmap
pv = ocr_seg.pivot(index="doc_type", columns="device_type", values="ocr_success_pct")
fig, ax = plt.subplots(figsize=(7.5, 3.8))
sns.heatmap(pv, annot=True, fmt=".1f", cmap="RdYlGn", vmin=65, vmax=97, ax=ax, cbar_kws={"label": "OCR success %"})
ax.set_title("OCR success rate by document x device"); ax.set_xlabel(""); ax.set_ylabel("")
plt.tight_layout(); plt.savefig(IMG / "02_ocr_heatmap.png", dpi=150); plt.close()

# 3 pareto
top = fail.head(8)
fig, ax = plt.subplots(figsize=(8, 4))
lbl = top.failure_stage + " / " + top.failure_reason
ax.bar(lbl, top.pct_of_all_failures, color="#c0504d")
ax2 = ax.twinx(); ax2.plot(lbl, top.cumulative_pct, color="black", marker="o"); ax2.set_ylim(0, 105); ax2.grid(False)
ax.set_ylabel("% of all failures"); ax2.set_ylabel("cumulative %")
ax.set_title("Top failure reasons (Pareto)"); plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8)
plt.tight_layout(); plt.savefig(IMG / "03_failure_pareto.png", dpi=150); plt.close()

# 4 version regression
fig, ax = plt.subplots(figsize=(5.5, 3.6))
sns.barplot(data=ver, x="app_version", y="face_match_pass_pct", color="#2f6fb5", ax=ax)
for p in ax.patches: ax.annotate(f"{p.get_height():.1f}%", (p.get_x()+p.get_width()/2, p.get_height()), ha="center", va="bottom", fontsize=9)
ax.set_ylim(60, 100); ax.set_title("Face-match pass rate by app version"); ax.set_xlabel("app version"); ax.set_ylabel("%")
plt.tight_layout(); plt.savefig(IMG / "04_version_regression.png", dpi=150); plt.close()

# 5 latency
fig, ax = plt.subplots(figsize=(7.5, 3.8))
x = np.arange(len(lat)); w = .38
ax.bar(x - w/2, lat.p50_ms, w, label="p50", color="#2f6fb5"); ax.bar(x + w/2, lat.p95_ms, w, label="p95", color="#e08a2c")
ax.axhline(3000, ls="--", color="grey"); ax.text(len(lat) - .5, 3050, "3s SLA", ha="right", fontsize=8)
ax.set_xticks(x); ax.set_xticklabels(lat.index, rotation=15); ax.set_ylabel("OCR latency (ms)"); ax.legend()
ax.set_title("OCR latency by document type")
plt.tight_layout(); plt.savefig(IMG / "05_latency.png", dpi=150); plt.close()

# ---------- impact sizing ----------
n = len(df)
base_appr = df.approved.mean()

# (a) fix low-end Android OCR to match mid/high Android
le = df[df.device_type == "Android (low-end)"]
mh = df[df.device_type == "Android (mid/high)"]
le_ocr = le.ocr_ok.sum() / le.upload_ok.sum()
mh_ocr = mh.ocr_ok.sum() / mh.upload_ok.sum()
down = le.face_ok.sum() / le.ocr_ok.sum() * le.approved.sum() / le.face_ok.sum()
gain_a = le.upload_ok.sum() * (mh_ocr - le_ocr) * down / n

# (b) fix v4.8 face-match regression to v4.9 level
v48 = df[df.app_version == "4.8"]; v49 = df[df.app_version == "4.9"]
f48 = v48.face_ok.sum() / v48.ocr_ok.sum(); f49 = v49.face_ok.sum() / v49.ocr_ok.sum()
fin = v48.approved.sum() / v48.face_ok.sum()
gain_b = v48.ocr_ok.sum() * (f49 - f48) * fin / n

# (c) night low-light: lift night face-match to daytime level
hr = df.started_at.dt.hour
night = df[hr <= 5]; day = df[hr > 5]
fn = night.face_ok.sum() / night.ocr_ok.sum(); fd = day.face_ok.sum() / day.ocr_ok.sum()
gain_c = night.ocr_ok.sum() * (fd - fn) * (night.approved.sum() / night.face_ok.sum()) / n

summary = f"""# Auto-generated findings (python src/analysis.py)

Sessions: {n:,}   Overall approval: {base_appr:.1%}

## Funnel
{funnel.to_string(index=False)}

## Weakest OCR segments (doc x device)
{ocr_seg.head(6).to_string(index=False)}

## Failure reasons (top 8)
{fail.head(8).to_string(index=False)}

## Face-match by app version
{ver.to_string(index=False)}

## OCR latency
{lat.to_string()}

## Impact sizing (approval-rate points gained if fixed)
Low-end Android OCR {le_ocr:.1%} -> {mh_ocr:.1%} (mid/high Android):  +{gain_a*100:.2f} pts
v4.8 face-match {f48:.1%} -> {f49:.1%} (v4.9 level):                     +{gain_b*100:.2f} pts
Night (00-05h) face-match {fn:.1%} -> {fd:.1%} (daytime level):          +{gain_c*100:.2f} pts
"""
(REP / "findings.txt").write_text(summary)
print(summary)
