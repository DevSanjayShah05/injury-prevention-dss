from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Literal, Dict

import sqlite3
from datetime import datetime, timezone
import json
from pathlib import Path

app = FastAPI(title="Injury Prevention DSS", version="0.1.0")

# CORS so React can call this API
app.add_middleware(    
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = Path(__file__).parent / "assessments.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
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
    conn.commit()
    conn.close()

@app.on_event("startup")
def on_startup():
    init_db()




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
        factors.append("Very high insentity (RPE 9-10).")
    elif req.rpe >= 7:
        score += 10
        breakdown["intensity"] += 10
        factors.append("High intensity (RPE 7-8).")

    # Recovery
    if req.sleep_hours < 6:
        score += 12
        breakdown["sleep"] += 12
        factors.append("Low sleep duration (<6 hours).")
    elif req.sleep_hours < 7:
        score += 6
        breakdown["sleep"] += 6
        factors.append("Below-optimal sleep duration (6–7 hours).")

    #Rest
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
        recs.append("Stop aggravating movements and consider consulting a medical professional if pain persists.")
    if req.pain_location != "none" and req.pain_score >= 4:
        recs.append(f"Modify training to reduce load on the {req.pain_location.replace('_', ' ')} and prioritize technique.")
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

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/assess", response_model=AssessmentResponse)
def assess(req: AssessmentRequest):
    resp = calculate_risk_and_advice(req)
    log_assessment(req, resp)
    return resp