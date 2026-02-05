from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Literal, Dict, Optional

import requests
import sqlite3
from datetime import datetime, timezone
import json
from pathlib import Path
import os


# =========================================
# App + Config
# =========================================
app = FastAPI(title="Injury Prevention DSS", version="0.3.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = Path(__file__).parent / "assessments.db"

# Ollama config
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "90"))


# =========================================
# Database helpers
# =========================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Base table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            request_json TEXT NOT NULL,
            risk_score INTEGER NOT NULL,
            risk_level TEXT NOT NULL,
            score_breakdown_json TEXT NOT NULL
        )
    """)

    # Add new columns safely (no data loss)
    cur.execute("PRAGMA table_info(assessments)")
    cols = {row[1] for row in cur.fetchall()}  # row[1] is column name

    if "ai_mode" not in cols:
        cur.execute("ALTER TABLE assessments ADD COLUMN ai_mode TEXT")

    if "ai_model" not in cols:
        cur.execute("ALTER TABLE assessments ADD COLUMN ai_model TEXT")

    if "ai_coach_json" not in cols:
        cur.execute("ALTER TABLE assessments ADD COLUMN ai_coach_json TEXT")

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


# =========================================
# Models
# =========================================
class AssessmentRequest(BaseModel):
    training_days_per_week: int = Field(ge=0, le=7)
    session_minutes: int = Field(ge=0, le=300)
    rpe: int = Field(ge=1, le=10)
    weekly_sets: int = Field(ge=0, le=300)
    rest_days_per_week: int = Field(ge=0, le=7)
    sleep_hours: float = Field(ge=0, le=16)
    pain_score: int = Field(ge=0, le=10)
    pain_location: Literal["none", "shoulder", "wrist", "elbow", "knee", "lower_back", "other"] = "none"
    experience_level: Literal["beginner", "intermediate", "advanced"]


class AssessmentResponse(BaseModel):
    risk_score: int
    risk_level: Literal["low", "moderate", "high"]
    top_factors: List[str]
    recommendations: List[str]
    score_breakdown: Dict[str, int]


# Structured coach schema for frontend rendering
class AICoachStructured(BaseModel):
    risk_level_summary: str
    top_drivers: List[str]
    seven_day_plan: Dict[str, List[str]]  # keep/reduce/add lists
    red_flags: List[str]


class AICoachResponse(BaseModel):
    mode: Literal["ollama", "fallback"]
    model_used: str
    coach: AICoachStructured
    raw_text: Optional[str] = None  # store raw ollama response (debug)


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


# =========================================
# DSS logic
# =========================================
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


def save_ai_coach_for_latest_assessment(ai_mode: str, ai_model: str, ai_coach: Dict[str, object]):
    """
    Saves AI output to the most recent assessment row.
    Assumption: UI calls /assess then /ai/coach (your UI does this).
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT id FROM assessments ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        conn.close()
        return

    latest_id = row[0]
    cur.execute(
        """
        UPDATE assessments
        SET ai_mode = ?, ai_model = ?, ai_coach_json = ?
        WHERE id = ?
        """,
        (ai_mode, ai_model, json.dumps(ai_coach), latest_id),
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

    # Pain
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

    # Sleep
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

    score = max(0, min(100, score))

    if score >= 70:
        level: Literal["low", "moderate", "high"] = "high"
    elif score >= 35:
        level = "moderate"
    else:
        level = "low"

    recs: List[str] = []
    if req.pain_score >= 7:
        recs.append("Stop aggravating movements and consult a licensed clinician if pain persists or worsens.")
    if req.pain_location != "none" and req.pain_score >= 4:
        recs.append(f"Reduce load on the {req.pain_location.replace('_', ' ')} and prioritize technique.")
    if req.weekly_sets >= 80:
        recs.append("Reduce weekly volume by 10–25% for 1–2 weeks (deload) and reassess symptoms.")
    if req.rpe >= 8:
        recs.append("Lower intensity for 3–7 days (aim RPE 6–7) and avoid grinding reps.")
    if req.sleep_hours < 7:
        recs.append("Aim for 7–9 hours of sleep to improve recovery and reduce risk.")
    if req.rest_days_per_week <= 1 and req.training_days_per_week >= 5:
        recs.append("Add 1 additional rest day this week to improve recovery capacity.")
    if not recs:
        recs.append("Maintain current plan; progress gradually and monitor discomfort.")

    top = factors[:3] if factors else ["No major risk factors detected from provided inputs."]

    return AssessmentResponse(
        risk_score=score,
        risk_level=level,
        top_factors=top,
        recommendations=recs,
        score_breakdown=breakdown,
    )


# =========================================
# Coach fallback (deterministic structured)
# =========================================
def build_fallback_structured(req: AssessmentRequest, resp: AssessmentResponse) -> AICoachStructured:
    if resp.risk_level == "high":
        vol_cut = "25–40%"
        rpe_target = "5–6"
        rest_note = "Add 1–2 extra rest days this week"
    elif resp.risk_level == "moderate":
        vol_cut = "10–25%"
        rpe_target = "6–7"
        rest_note = "Add 1 extra rest day if possible"
    else:
        vol_cut = "0–10%"
        rpe_target = "6–8 (avoid frequent max effort)"
        rest_note = "Keep current rest schedule"

    keep = [
        "Warm-up 8–10 minutes + 2 light ramp-up sets for main lifts",
        "Technique-first reps; stop 1–3 reps before failure on most sets",
    ]

    reduce = [
        f"Reduce weekly sets by ~{vol_cut}",
        f"Keep intensity around RPE {rpe_target}",
        "Avoid grinders, forced reps, and high-fatigue finishers",
    ]
    if req.training_days_per_week >= 5:
        reduce.append("Consider dropping 1 training day this week (temporarily)")

    add = [
        rest_note,
        "Add 10 minutes mobility/activation after training (hips/shoulders/core)",
    ]
    if req.sleep_hours < 7:
        add.insert(1, "Sleep goal: 7–9 hours (even +45–60 minutes helps)")
    else:
        add.insert(1, "Keep sleep consistent; avoid large late-night variability")

    red_flags = [
        "Pain rising session-to-session",
        "Sharp pain",
        "Numbness/tingling",
        "Pain that changes movement pattern",
        "If symptoms worsen despite deloading, seek professional evaluation",
    ]
    if req.pain_score >= 7:
        red_flags.insert(0, "Pain is very high (7+): stop aggravating movements and consult a licensed clinician.")

    return AICoachStructured(
        risk_level_summary=f"Risk level: {resp.risk_level.upper()} (score {resp.risk_score}/100).",
        top_drivers=resp.top_factors[:3],
        seven_day_plan={"keep": keep, "reduce": reduce, "add": add},
        red_flags=red_flags,
    )


# =========================================
# Ollama Coach (returns structured JSON)
# =========================================
def ollama_generate_structured(req: AssessmentRequest, resp: AssessmentResponse) -> Optional[Dict[str, object]]:
    schema_hint = {
        "risk_level_summary": "string (1-2 sentences)",
        "top_drivers": ["string", "string", "string"],
        "seven_day_plan": {"keep": ["string"], "reduce": ["string"], "add": ["string"]},
        "red_flags": ["string"],
    }

    system_rules = (
        "You are a strength-training coach focused on injury risk reduction. "
        "Do NOT provide medical diagnosis. Be conservative. "
        "If pain is high (>=7), worsening, or includes red flags (numbness/tingling/sharp pain), "
        "advise consulting a licensed clinician."
    )

    payload = {
        "inputs": req.model_dump(),
        "dss_output": resp.model_dump(),
        "schema": schema_hint,
        "instruction": (
            "Return ONLY valid JSON matching the schema. "
            "No markdown. No extra commentary. Keep it short, specific, actionable."
        ),
    }

    prompt = (
        f"{system_rules}\n\n"
        "Return ONLY valid JSON matching the schema below.\n"
        f"SCHEMA:\n{json.dumps(schema_hint, ensure_ascii=False)}\n\n"
        f"DATA:\n{json.dumps(payload, ensure_ascii=False)}\n"
    )

    try:
        r = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=OLLAMA_TIMEOUT,
        )
        if not r.ok:
            return None

        raw = (r.json().get("response") or "").strip()
        if not raw:
            return None

        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None

        # sanity checks
        if "risk_level_summary" not in parsed:
            return None
        if "seven_day_plan" not in parsed or not isinstance(parsed["seven_day_plan"], dict):
            return None

        return parsed

    except Exception:
        return None


# =========================================
# Routes
# =========================================
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
    resp = calculate_risk_and_advice(req)

    structured_dict = ollama_generate_structured(req, resp)
    if structured_dict:
        try:
            coach = AICoachStructured(**structured_dict)

            # ✅ SAVE to DB
            save_ai_coach_for_latest_assessment(
                ai_mode="ollama",
                ai_model=OLLAMA_MODEL,
                ai_coach=coach.model_dump(),
            )

            return AICoachResponse(
                mode="ollama",
                model_used=OLLAMA_MODEL,
                coach=coach,
                raw_text=json.dumps(structured_dict, ensure_ascii=False),
            )
        except Exception:
            pass

    fallback = build_fallback_structured(req, resp)

    # ✅ SAVE fallback to DB too
    save_ai_coach_for_latest_assessment(
        ai_mode="fallback",
        ai_model=OLLAMA_MODEL,
        ai_coach=fallback.model_dump(),
    )

    return AICoachResponse(
        mode="fallback",
        model_used=OLLAMA_MODEL,
        coach=fallback,
        raw_text=None,
    )


@app.get("/dashboard/ai_usage")
def dashboard_ai_usage():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT ai_mode, COUNT(*) AS n
        FROM assessments
        WHERE ai_mode IS NOT NULL
        GROUP BY ai_mode
    """)
    rows = cur.fetchall()
    conn.close()

    out = {"ollama": 0, "fallback": 0}
    for r in rows:
        if r["ai_mode"] in out:
            out[r["ai_mode"]] = int(r["n"])
    return out


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
    cur.execute("""
        SELECT risk_level, COUNT(*) AS n
        FROM assessments
        GROUP BY risk_level
    """)
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
        reqj = safe_json_loads(r["request_json"])
        loc = reqj.get("pain_location", "unknown")
        freq[loc] = freq.get(loc, 0) + 1

    top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[: max(1, limit)]
    return [DashboardTopItem(key=k, count=v) for k, v in top]


@app.get("/dashboard/recent", response_model=List[RecentAssessment])
def dashboard_recent(limit: int = 10):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, created_at, request_json, risk_score, risk_level
        FROM assessments
        ORDER BY id DESC
        LIMIT ?
    """, (max(1, min(limit, 50)),))
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