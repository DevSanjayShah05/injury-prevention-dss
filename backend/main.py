from collections import Counter
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import sqlite3
from typing import Dict, List, Literal, Optional

import requests
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field

# =========================================
# App + Config
# =========================================
app = FastAPI(title="Injury Prevention DSS", version="0.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = Path(__file__).parent / "assessments.db"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "90"))

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-to-a-long-random-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# =========================================
# Helpers
# =========================================
def iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def iso_cutoff_days(days: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    return dt.isoformat()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def safe_json_loads(s: Optional[str]):
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}


# =========================================
# Database init / migration
# =========================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Users table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            hashed_password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    # Assessments table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            created_at TEXT NOT NULL,
            request_json TEXT NOT NULL,
            risk_score INTEGER NOT NULL,
            risk_level TEXT NOT NULL,
            score_breakdown_json TEXT NOT NULL,
            ai_mode TEXT,
            ai_model TEXT,
            ai_coach_json TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    # Safe migration for older DBs
    cur.execute("PRAGMA table_info(assessments)")
    cols = {row[1] for row in cur.fetchall()}

    if "user_id" not in cols:
        cur.execute("ALTER TABLE assessments ADD COLUMN user_id INTEGER")

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


# =========================================
# Pydantic models
# =========================================
class UserRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


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


class AICoachStructured(BaseModel):
    risk_level_summary: str
    top_drivers: List[str]
    seven_day_plan: Dict[str, List[str]]
    red_flags: List[str]


class AICoachResponse(BaseModel):
    mode: Literal["ollama", "fallback"]
    model_used: str
    coach: AICoachStructured
    raw_text: Optional[str] = None


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


class TrendPoint(BaseModel):
    day: str
    avg_risk_score: float
    count: int


class AvgBreakdown(BaseModel):
    pain: float
    volume: float
    intensity: float
    sleep: float
    rest: float
    experience: float


# =========================================
# Auth helpers
# =========================================
def hash_password(password: str) -> str:
    password = password.strip()
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password.strip(), hashed_password)

def create_access_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload["exp"] = expire
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_user_by_email(email: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()
    return row


def get_user_by_id(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_current_user(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.split(" ", 1)[1]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = get_user_by_id(int(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


# =========================================
# Core DSS logic
# =========================================
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

    if req.weekly_sets >= 120:
        score += 20
        breakdown["volume"] += 20
        factors.append("Very high weekly training volume (sets).")
    elif req.weekly_sets >= 80:
        score += 12
        breakdown["volume"] += 12
        factors.append("High weekly training volume (sets).")

    if req.rpe >= 9:
        score += 18
        breakdown["intensity"] += 18
        factors.append("Very high intensity (RPE 9–10).")
    elif req.rpe >= 7:
        score += 10
        breakdown["intensity"] += 10
        factors.append("High intensity (RPE 7–8).")

    if req.sleep_hours < 6:
        score += 12
        breakdown["sleep"] += 12
        factors.append("Low sleep duration (<6 hours).")
    elif req.sleep_hours < 7:
        score += 6
        breakdown["sleep"] += 6
        factors.append("Below-optimal sleep duration (6–7 hours).")

    if req.rest_days_per_week <= 1 and req.training_days_per_week >= 5:
        score += 10
        breakdown["rest"] += 10
        factors.append("Low rest relative to training frequency.")

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


def log_assessment(req: AssessmentRequest, resp: AssessmentResponse, user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO assessments (
            user_id,
            created_at,
            request_json,
            risk_score,
            risk_level,
            score_breakdown_json
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            iso_utc_now(),
            req.model_dump_json(),
            resp.risk_score,
            resp.risk_level,
            json.dumps(resp.score_breakdown),
        ),
    )
    conn.commit()
    conn.close()


def save_ai_coach_for_latest_assessment(user_id: int, ai_mode: str, ai_model: str, ai_coach: Dict[str, object]):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id
        FROM assessments
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    )
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


# =========================================
# AI coach
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
        if "risk_level_summary" not in parsed:
            return None
        if "seven_day_plan" not in parsed or not isinstance(parsed["seven_day_plan"], dict):
            return None

        return parsed
    except Exception:
        return None


# =========================================
# Auth routes
# =========================================
@app.post("/auth/register", response_model=UserResponse)
def register_user(req: UserRegisterRequest):
    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO users (name, email, hashed_password, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (req.name, req.email, hash_password(req.password), iso_utc_now()),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()

    return UserResponse(id=user_id, name=req.name, email=req.email)


@app.post("/auth/login", response_model=TokenResponse)
def login_user(req: UserLoginRequest):
    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": str(user["id"])})

    return TokenResponse(
        access_token=token,
        user=UserResponse(id=user["id"], name=user["name"], email=user["email"]),
    )


@app.get("/auth/me", response_model=UserResponse)
def get_me(current_user=Depends(get_current_user)):
    return UserResponse(
        id=current_user["id"],
        name=current_user["name"],
        email=current_user["email"],
    )


# =========================================
# General routes
# =========================================
@app.get("/")
def root():
    return {"message": "Backend running. Visit /docs for API documentation."}


@app.get("/health")
def health():
    return {"status": "ok"}


# =========================================
# Protected assessment / AI routes
# =========================================
@app.post("/assess", response_model=AssessmentResponse)
def assess(req: AssessmentRequest, current_user=Depends(get_current_user)):
    resp = calculate_risk_and_advice(req)
    log_assessment(req, resp, current_user["id"])
    return resp


@app.post("/ai/coach", response_model=AICoachResponse)
def ai_coach(req: AssessmentRequest, current_user=Depends(get_current_user)):
    resp = calculate_risk_and_advice(req)

    structured_dict = ollama_generate_structured(req, resp)
    if structured_dict:
        try:
            coach = AICoachStructured(**structured_dict)
            save_ai_coach_for_latest_assessment(
                current_user["id"], "ollama", OLLAMA_MODEL, structured_dict
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
    save_ai_coach_for_latest_assessment(
        current_user["id"], "fallback", OLLAMA_MODEL, fallback.model_dump()
    )
    return AICoachResponse(
        mode="fallback",
        model_used=OLLAMA_MODEL,
        coach=fallback,
        raw_text=None,
    )


# =========================================
# Protected dashboard routes
# =========================================
@app.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(current_user=Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) AS n, AVG(risk_score) AS avg_score FROM assessments WHERE user_id = ?",
        (current_user["id"],),
    )
    row = cur.fetchone()
    conn.close()

    return DashboardSummary(
        total_assessments=int(row["n"] or 0),
        avg_risk_score=round(float(row["avg_score"] or 0.0), 2),
    )


@app.get("/dashboard/risk_distribution", response_model=RiskLevelDistribution)
def dashboard_risk_distribution(current_user=Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT risk_level, COUNT(*) AS n
        FROM assessments
        WHERE user_id = ?
        GROUP BY risk_level
        """,
        (current_user["id"],),
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
def dashboard_top_pain_locations(limit: int = 5, current_user=Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT request_json FROM assessments WHERE user_id = ?",
        (current_user["id"],),
    )
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
def dashboard_recent(limit: int = 10, current_user=Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, created_at, request_json, risk_score, risk_level
        FROM assessments
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (current_user["id"], max(1, min(limit, 50))),
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


@app.get("/dashboard/ai_usage")
def dashboard_ai_usage(current_user=Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT ai_mode, COUNT(*) AS n
        FROM assessments
        WHERE user_id = ? AND ai_mode IS NOT NULL AND ai_mode != ''
        GROUP BY ai_mode
        """,
        (current_user["id"],),
    )
    rows = cur.fetchall()

    cur.execute(
        "SELECT COUNT(*) AS n FROM assessments WHERE user_id = ?",
        (current_user["id"],),
    )
    total = int(cur.fetchone()["n"] or 0)
    conn.close()

    out = {"ollama": 0, "fallback": 0, "total_assessments": total}
    for r in rows:
        mode = r["ai_mode"]
        if mode in out:
            out[mode] = int(r["n"])

    return out


@app.get("/dashboard/risk_trend", response_model=List[TrendPoint])
def dashboard_risk_trend(days: int = 30, current_user=Depends(get_current_user)):
    cutoff = iso_cutoff_days(days)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT substr(created_at, 1, 10) AS day,
               AVG(risk_score) AS avg_score,
               COUNT(*) AS n
        FROM assessments
        WHERE user_id = ? AND created_at >= ?
        GROUP BY substr(created_at, 1, 10)
        ORDER BY day ASC
        """,
        (current_user["id"], cutoff),
    )
    rows = cur.fetchall()
    conn.close()

    return [
        TrendPoint(
            day=r["day"],
            avg_risk_score=round(float(r["avg_score"]), 2),
            count=int(r["n"]),
        )
        for r in rows
    ]


@app.get("/dashboard/top_factors", response_model=List[DashboardTopItem])
def dashboard_top_factors(limit: int = 8, days: int = 30, current_user=Depends(get_current_user)):
    cutoff = iso_cutoff_days(days)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT request_json
        FROM assessments
        WHERE user_id = ? AND created_at >= ?
        """,
        (current_user["id"], cutoff),
    )
    rows = cur.fetchall()
    conn.close()

    c = Counter()
    for r in rows:
        reqj = safe_json_loads(r["request_json"])
        try:
            req = AssessmentRequest(**reqj)
        except Exception:
            continue
        resp = calculate_risk_and_advice(req)
        for f in resp.top_factors:
            c[f] += 1

    top = c.most_common(max(1, limit))
    return [DashboardTopItem(key=k, count=v) for k, v in top]


@app.get("/dashboard/avg_breakdown", response_model=AvgBreakdown)
def dashboard_avg_breakdown(days: int = 30, current_user=Depends(get_current_user)):
    cutoff = iso_cutoff_days(days)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT score_breakdown_json
        FROM assessments
        WHERE user_id = ? AND created_at >= ?
        """,
        (current_user["id"], cutoff),
    )
    rows = cur.fetchall()
    conn.close()

    totals = Counter({"pain": 0, "volume": 0, "intensity": 0, "sleep": 0, "rest": 0, "experience": 0})
    n = 0

    for r in rows:
        bj = safe_json_loads(r["score_breakdown_json"])
        if not isinstance(bj, dict):
            continue
        n += 1
        for k in totals.keys():
            try:
                totals[k] += int(bj.get(k, 0) or 0)
            except Exception:
                pass

    if n == 0:
        return AvgBreakdown(pain=0, volume=0, intensity=0, sleep=0, rest=0, experience=0)

    return AvgBreakdown(
        pain=round(totals["pain"] / n, 2),
        volume=round(totals["volume"] / n, 2),
        intensity=round(totals["intensity"] / n, 2),
        sleep=round(totals["sleep"] / n, 2),
        rest=round(totals["rest"] / n, 2),
        experience=round(totals["experience"] / n, 2),
    )