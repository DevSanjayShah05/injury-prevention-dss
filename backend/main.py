from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Literal, Dict, Optional

import sqlite3
from datetime import datetime, timezone
import json
from pathlib import Path
import os

# Optional OpenAI (only used if available + billing enabled)
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore

app = FastAPI(title="Injury Prevention DSS", version="0.2.0")

# CORS so React can call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = Path(__file__).parent / "assessments.db"


# ---------------------------
# Database helpers
# ---------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            request_json TEXT NOT NULL,
            risk_score INTEGER NOT NULL,
            risk_level TEXT NOT NULL,
            score_breakdown_json TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


@app.on_event("startup")
def on_startup():
    init_db()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def safe_json_loads(s: str):
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}


# ---------------------------
# Models
# ---------------------------
class AssessmentRequest(BaseModel):
    training_days_per_week: int = Field(ge=0, le=7)
    session_minutes: int = Field(ge=0, le=300)
    rpe: int = Field(ge=1, le=10)
    weekly_sets: int = Field(ge=0, le=300)
    rest_days_per_week: int = Field(ge=0, le=7)
    sleep_hours: float = Field(ge=0, le=16)
    pain_score: int = Field(ge=0, le=10)
    pain_location: Literal[
        "none", "shoulder", "wrist", "elbow", "knee", "lower_back", "other"
    ] = "none"
    experience_level: Literal["beginner", "intermediate", "advanced"]


class AssessmentResponse(BaseModel):
    risk_score: int
    risk_level: Literal["low", "moderate", "high"]
    top_factors: List[str]
    recommendations: List[str]
    score_breakdown: Dict[str, int]


class AICoachResponse(BaseModel):
    coach_notes: str
    mode: Literal["fallback", "openai"] = "fallback"


class DashboardSummary(BaseModel):
    total_assessments: int
    avg_risk_score: float


class RiskLevelDistribution(BaseModel):
    low: int
    moderate: int
    high: int


class DashboardTopItem(BaseModel):
    key: str
    count: int


class RecentAssessment(BaseModel):
    id: int
    created_at: str
    risk_score: int
    risk_level: str
    pain_location: str


# ---------------------------
# DSS logic
# ---------------------------
def log_assessment(req: AssessmentRequest, resp: AssessmentResponse):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    created_at = datetime.now(timezone.utc).isoformat()

    cur.execute(
        """
        INSERT INTO assessments (created_at, request_json, risk_score, risk_level, score_breakdown_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            created_at,
            req.model_dump_json(),
            resp.risk_score,
            resp.risk_level,
            json.dumps(resp.score_breakdown),
        ),
    )

    conn.commit()
    conn.close()


def calculate_risk_and_advice(req: AssessmentRequest) -> AssessmentResponse:
    score = 0
    factors: List[str] = []

    breakdown: Dict[str, int] = {
        "pain": 0,
        "volume": 0,
        "intensity": 0,
        "sleep": 0,
        "rest": 0,
        "experience": 0,
    }

    # Pain is a strong signal
    if req.pain_score >= 7:
        score += 45
        breakdown["pain"] += 45
        factors.append("High pain score reported (7+).")
    elif req.pain_score >= 4:
        score += 25
        breakdown["pain"] += 25
        factors.append("Moderate pain score reported (4–6).")
    elif req.pain_score >= 1:
        score += 10
        breakdown["pain"] += 10
        factors.append("Mild pain score reported (1–3).")

    # Volume
    if req.weekly_sets >= 120:
        score += 20
        breakdown["volume"] += 20
        factors.append("Very high weekly training volume (sets).")
    elif req.weekly_sets >= 80:
        score += 12
        breakdown["volume"] += 12
        factors.append("High weekly training volume (sets).")

    # Intensity
    if req.rpe >= 9:
        score += 18
        breakdown["intensity"] += 18
        factors.append("Very high intensity (RPE 9–10).")
    elif req.rpe >= 7:
        score += 10
        breakdown["intensity"] += 10
        factors.append("High intensity (RPE 7–8).")

    # Recovery
    if req.sleep_hours < 6:
        score += 12
        breakdown["sleep"] += 12
        factors.append("Low sleep duration (<6 hours).")
    elif req.sleep_hours < 7:
        score += 6
        breakdown["sleep"] += 6
        factors.append("Below-optimal sleep duration (6–7 hours).")

    # Rest
    if req.rest_days_per_week <= 1 and req.training_days_per_week >= 5:
        score += 10
        breakdown["rest"] += 10
        factors.append("Low rest relative to training frequency.")

    # Experience adjustment
    if req.experience_level == "beginner" and req.rpe >= 8:
        score += 8
        breakdown["experience"] += 8
        factors.append("High intensity for beginner level.")

    # Cap score to 0–100
    score = max(0, min(100, score))

    # Risk level bands
    if score >= 70:
        level: Literal["low", "moderate", "high"] = "high"
    elif score >= 35:
        level = "moderate"
    else:
        level = "low"

    # Recommendations
    recs: List[str] = []
    if req.pain_score >= 7:
        recs.append(
            "Stop aggravating movements and consider consulting a medical professional if pain persists."
        )
    if req.pain_location != "none" and req.pain_score >= 4:
        recs.append(
            f"Modify training to reduce load on the {req.pain_location.replace('_', ' ')} and prioritize technique."
        )
    if req.weekly_sets >= 80:
        recs.append("Reduce weekly volume by 10–25% for 1–2 weeks (deload) and reassess symptoms.")
    if req.rpe >= 8:
        recs.append("Lower intensity for the next 3–7 days (aim RPE 6–7) and avoid grinding reps.")
    if req.sleep_hours < 7:
        recs.append("Aim for 7–9 hours of sleep to improve recovery and reduce injury risk.")
    if req.rest_days_per_week <= 1 and req.training_days_per_week >= 5:
        recs.append("Add 1 additional rest day per week to improve recovery capacity.")

    if not recs:
        recs.append("Maintain current plan; continue gradual progression and monitor any discomfort.")

    top = factors[:3] if factors else ["No major risk factors detected from provided inputs."]

    return AssessmentResponse(
        risk_score=score,
        risk_level=level,
        top_factors=top,
        recommendations=recs,
        score_breakdown=breakdown,
    )


# ---------------------------
# Fallback AI Coach (no OpenAI required)
# ---------------------------
def build_fallback_coach_notes(req: AssessmentRequest, resp: AssessmentResponse) -> str:
    # Build an "AI-like" but deterministic coaching plan
    lines: List[str] = []

    lines.append(f"Risk level: {resp.risk_level.upper()} (score {resp.risk_score}/100)")
    lines.append("")
    lines.append("Why this risk level (top drivers):")
    for f in resp.top_factors[:3]:
        lines.append(f"- {f}")
    lines.append("")

    # Targets based on score
    if resp.risk_level == "high":
        vol_cut = "25–40%"
        rpe_target = "5–6"
        extra_rest = "Add 1–2 extra rest days this week"
    elif resp.risk_level == "moderate":
        vol_cut = "10–25%"
        rpe_target = "6–7"
        extra_rest = "Add 1 extra rest day if possible"
    else:
        vol_cut = "0–10%"
        rpe_target = "6–8 (avoid frequent max effort)"
        extra_rest = "Keep current rest schedule"

    # Special pain handling
    pain_note = ""
    if req.pain_score >= 7:
        pain_note = (
            "Red flag: pain is very high (7+). Stop aggravating movements and consult a licensed clinician if worsening/persistent."
        )
    elif req.pain_score >= 4 and req.pain_location != "none":
        pain_note = (
            f"Pain focus: reduce loading on the {req.pain_location.replace('_',' ')} for 7 days; keep pain ≤3/10 during training."
        )

    lines.append("7-day plan (simple + actionable):")
    lines.append("1) What to KEEP")
    lines.append("- Warm-up 8–10 minutes + 2 light ramp-up sets for main lifts")
    lines.append("- Technique-first reps; stop 1–3 reps before failure on most sets")
    lines.append("")
    lines.append("2) What to REDUCE")
    lines.append(f"- Reduce weekly sets by ~{vol_cut}")
    lines.append(f"- Keep intensity around RPE {rpe_target}")
    lines.append("- Avoid grinders, forced reps, and high-fatigue finishers")
    if req.training_days_per_week >= 5:
        lines.append("- Consider dropping 1 training day this week (temporarily)")
    lines.append("")
    lines.append("3) What to ADD (recovery + prehab)")
    lines.append(f"- {extra_rest}")
    if req.sleep_hours < 7:
        lines.append("- Sleep goal: 7–9 hours (even +45–60 minutes helps)")
    else:
        lines.append("- Keep sleep consistent; avoid large late-night variability")
    lines.append("- Add 10 minutes of mobility/activation after training (hips/shoulders/core)")
    lines.append("")
    lines.append("4) Red flags (stop/modify)")
    if pain_note:
        lines.append(f"- {pain_note}")
    else:
        lines.append("- Pain rising session-to-session, sharp pain, numbness/tingling, or pain that changes movement pattern")
    lines.append("- If symptoms worsen despite deloading, seek professional evaluation")

    return "\n".join(lines)


def try_openai_coach(req: AssessmentRequest, resp: AssessmentResponse) -> Optional[str]:
    """
    Attempts OpenAI generation if:
    - OPENAI_API_KEY is set
    - openai package is installed
    - billing/quota allows calls
    If anything fails, returns None (fallback will be used).
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or OpenAI is None:
        return None

    try:
        client = OpenAI(api_key=api_key)

        system_msg = (
            "You are a helpful strength-training coach focused on injury risk reduction. "
            "You MUST avoid medical diagnosis. Suggest conservative training modifications. "
            "If pain is high or worsening, advise consulting a licensed clinician. "
            "Be specific, short, and actionable."
        )

        user_msg = {
            "athlete_profile": {"experience_level": req.experience_level},
            "inputs": req.model_dump(),
            "dss_output": resp.model_dump(),
            "instruction": (
                "Explain why the risk is at this level, list top drivers, and give a 7-day plan "
                "to reduce risk (volume/intensity/rest/sleep changes). "
                "Include: (1) what to keep, (2) what to reduce, (3) what to add (warmup/prehab), "
                "and (4) red flags."
            ),
        }

        r = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": json.dumps(user_msg)},
            ],
        )

        coach_text = getattr(r, "output_text", None)
        if coach_text and isinstance(coach_text, str) and coach_text.strip():
            return coach_text.strip()

        return None

    except Exception:
        # Any OpenAI error (including 429 insufficient_quota) => fallback
        return None


# ---------------------------
# Routes
# ---------------------------
@app.get("/")
def root():
    return {"message": "Backend running. Visit /docs for API documentation."}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/assess", response_model=AssessmentResponse)
def assess(req: AssessmentRequest):
    resp = calculate_risk_and_advice(req)
    log_assessment(req, resp)
    return resp


@app.post("/ai/coach", response_model=AICoachResponse)
def ai_coach(req: AssessmentRequest):
    # Grounded in DSS output
    resp = calculate_risk_and_advice(req)

    # Try OpenAI if available; otherwise fallback
    coach_text = try_openai_coach(req, resp)
    if coach_text:
        return AICoachResponse(coach_notes=coach_text, mode="openai")

    fallback = build_fallback_coach_notes(req, resp)
    return AICoachResponse(coach_notes=fallback, mode="fallback")


@app.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS n, AVG(risk_score) AS avg_score FROM assessments")
    row = cur.fetchone()
    conn.close()

    total = int(row["n"] or 0)
    avg_score = float(row["avg_score"] or 0.0)

    return DashboardSummary(total_assessments=total, avg_risk_score=round(avg_score, 2))


@app.get("/dashboard/risk_distribution", response_model=RiskLevelDistribution)
def dashboard_risk_distribution():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT risk_level, COUNT(*) AS n
        FROM assessments
        GROUP BY risk_level
        """
    )
    rows = cur.fetchall()
    conn.close()

    counts = {"low": 0, "moderate": 0, "high": 0}
    for r in rows:
        lvl = r["risk_level"]
        if lvl in counts:
            counts[lvl] = int(r["n"])

    return RiskLevelDistribution(**counts)


@app.get("/dashboard/top_pain_locations", response_model=List[DashboardTopItem])
def dashboard_top_pain_locations(limit: int = 5):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT request_json FROM assessments")
    rows = cur.fetchall()
    conn.close()

    freq: Dict[str, int] = {}
    for r in rows:
        req = safe_json_loads(r["request_json"])
        loc = req.get("pain_location", "unknown")
        freq[loc] = freq.get(loc, 0) + 1

    top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[: max(1, limit)]
    return [DashboardTopItem(key=k, count=v) for k, v in top]


@app.get("/dashboard/recent", response_model=List[RecentAssessment])
def dashboard_recent(limit: int = 10):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, created_at, request_json, risk_score, risk_level
        FROM assessments
        ORDER BY id DESC
        LIMIT ?
        """,
        (max(1, min(limit, 50)),),
    )
    rows = cur.fetchall()
    conn.close()

    out: List[RecentAssessment] = []
    for r in rows:
        reqj = safe_json_loads(r["request_json"])
        out.append(
            RecentAssessment(
                id=int(r["id"]),
                created_at=r["created_at"],
                risk_score=int(r["risk_score"]),
                risk_level=r["risk_level"],
                pain_location=reqj.get("pain_location", "unknown"),
            )
        )

    return out