"""Generate a SYNTHETIC identity-verification funnel dataset.

No real user data is used. Behaviour (drop-offs, latency, failure reasons) is
simulated with known effects so the analysis has realistic patterns to find.
Run:  python src/generate_data.py
"""
import numpy as np
import pandas as pd
from pathlib import Path

SEED = 42
N = 60_000
rng = np.random.default_rng(SEED)

DOCS = ["Aadhaar", "PAN", "Driving Licence", "Passport", "Voter ID"]
DOC_P = [0.34, 0.26, 0.17, 0.12, 0.11]
DEVICES = ["Android (low-end)", "Android (mid/high)", "iOS", "Web"]
DEV_P = [0.30, 0.34, 0.22, 0.14]
TIERS = ["Tier 1", "Tier 2", "Tier 3"]
TIER_P = [0.42, 0.33, 0.25]
VERSIONS = ["4.7", "4.8", "4.9"]
VER_P = [0.25, 0.30, 0.45]

df = pd.DataFrame({
    "session_id": np.arange(1, N + 1),
    "doc_type": rng.choice(DOCS, N, p=DOC_P),
    "device_type": rng.choice(DEVICES, N, p=DEV_P),
    "city_tier": rng.choice(TIERS, N, p=TIER_P),
    "app_version": rng.choice(VERSIONS, N, p=VER_P),
})
df.loc[df.device_type == "Web", "app_version"] = "web"   # web has no app version

start = pd.Timestamp("2026-09-01")
day = rng.integers(0, 30, N)
hour_w = np.array([1, 1, 1, 1, 1, 2, 3, 5, 6, 7, 7, 7, 6, 6, 6, 6, 6, 7, 8, 8, 7, 5, 3, 2], float)
hour = rng.choice(24, N, p=hour_w / hour_w.sum())
df["started_at"] = (start + pd.to_timedelta(day, "D") + pd.to_timedelta(hour, "h")
                    + pd.to_timedelta(rng.integers(0, 3600, N), "s"))
df["hour"] = df.started_at.dt.hour

# ---- stage pass probabilities (known effects planted here) ----
dev_upload = {"Android (low-end)": -0.05, "Android (mid/high)": 0, "iOS": 0.01, "Web": -0.02}
tier_upload = {"Tier 1": 0.01, "Tier 2": 0, "Tier 3": -0.04}
p_upload = 0.94 + df.device_type.map(dev_upload) + df.city_tier.map(tier_upload)

doc_ocr = {"Aadhaar": 0.91, "PAN": 0.94, "Driving Licence": 0.84, "Passport": 0.87, "Voter ID": 0.80}
dev_ocr = {"Android (low-end)": -0.12, "Android (mid/high)": -0.01, "iOS": 0.02, "Web": -0.03}
p_ocr = df.doc_type.map(doc_ocr) + df.device_type.map(dev_ocr)
p_ocr -= ((df.doc_type == "Passport") & (df.device_type == "Android (low-end)")) * 0.10

p_face = pd.Series(0.93, index=df.index)
p_face -= (df.app_version == "4.8") * 0.13          # regression in app v4.8
p_face -= df.hour.between(0, 5) * 0.05                # low light at night
p_face -= (df.device_type == "Android (low-end)") * 0.03

p_final = pd.Series(0.97, index=df.index)

def draw(p):
    return (rng.random(N) < p.clip(0.05, 0.995)).to_numpy() if hasattr(p, "clip") else rng.random(N) < p

up = draw(p_upload)
ocr = up & draw(p_ocr)
face = ocr & draw(p_face)
ok = face & draw(p_final)
df["reached_upload"] = 1
df["upload_ok"] = up.astype(int)
df["ocr_ok"] = ocr.astype(int)
df["face_ok"] = face.astype(int)
df["approved"] = ok.astype(int)

# ---- failure stage + reason ----
stage = np.select([~up, ~ocr, ~face, ~ok], ["upload", "ocr", "face_match", "risk_review"], "none")
df["failure_stage"] = np.where(stage == "none", "", stage)

def pick(options, weights):
    w = np.array(weights, float)
    return rng.choice(options, p=w / w.sum())

reasons = []
for st, dev, hr, ver in zip(stage, df.device_type, df.hour, df.app_version):
    if st == "none":
        reasons.append("")
    elif st == "upload":
        reasons.append(pick(["network_timeout", "file_too_large", "user_abandoned"], [5, 2, 3]))
    elif st == "ocr":
        w = [6, 2, 2, 0.5] if dev == "Android (low-end)" else [2.5, 2.5, 4, 1]
        reasons.append(pick(["blurry_image", "glare", "field_extraction_failed", "unsupported_format"], w))
    elif st == "face_match":
        if ver == "4.8":
            w = [6, 1.5, 1.5, 1]
        elif hr <= 5:
            w = [2, 6, 1.5, 0.5]
        else:
            w = [2.5, 1.5, 4, 2]
        reasons.append(pick(["liveness_failed", "low_light", "face_mismatch", "camera_permission"], w))
    else:
        reasons.append(pick(["document_expired", "data_mismatch", "watchlist_review"], [3, 4, 1]))
df["failure_reason"] = reasons

# ---- latency (ms) ----
doc_lat = {"Aadhaar": 850, "PAN": 780, "Driving Licence": 1700, "Passport": 1450, "Voter ID": 1000}
dev_lat = {"Android (low-end)": 1.35, "Android (mid/high)": 1.0, "iOS": 0.9, "Web": 1.15}
median = (df.doc_type.map(doc_lat) * df.device_type.map(dev_lat)).to_numpy()
ocr_lat = rng.lognormal(np.log(median), 0.45)
ocr_lat *= np.where(rng.random(N) < 0.03, 4, 1)      # ~3% slow tail (retries/timeouts)
df["ocr_latency_ms"] = np.where(up, ocr_lat, np.nan).round(0)
other = rng.lognormal(np.log(1500), 0.4, N) * (1 + face * 0.6)
df["total_latency_ms"] = np.where(up, df.ocr_latency_ms.fillna(0) + other, np.nan).round(0)

df = df.drop(columns=["hour"]).sort_values("started_at").reset_index(drop=True)
df["session_id"] = np.arange(1, len(df) + 1)
Path("data").mkdir(exist_ok=True)
df.to_csv("data/verification_sessions.csv", index=False)
print(f"Wrote data/verification_sessions.csv  ({len(df):,} rows)")
print(f"Overall approval rate: {df.approved.mean():.1%}")
