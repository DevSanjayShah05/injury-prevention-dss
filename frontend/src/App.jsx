import { useMemo, useState } from "react";
import "./App.css";

const API_BASE = "http://127.0.0.1:8000";

function riskTheme(level) {
  switch (level) {
    case "low":
      return { bg: "#e7f7ee", border: "#b7ebc6", text: "#0f5132" };
    case "moderate":
      return { bg: "#fff8e6", border: "#ffe2a8", text: "#664d03" };
    case "high":
      return { bg: "#fdecec", border: "#f5c2c7", text: "#842029" };
    default:
      return { bg: "#f1f3f5", border: "#dee2e6", text: "#212529" };
  }
}

function scoreTheme(score) {
  if (score >= 70) return riskTheme("high");
  if (score >= 35) return riskTheme("moderate");
  return riskTheme("low");
}

export default function App() {
  const [form, setForm] = useState({
    training_days_per_week: 4,
    session_minutes: 60,
    rpe: 7,
    weekly_sets: 80,
    rest_days_per_week: 2,
    sleep_hours: 7,
    pain_score: 0,
    pain_location: "none",
    experience_level: "intermediate",
  });

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  // AI Coach
  const [coachLoading, setCoachLoading] = useState(false);
  const [coachNotes, setCoachNotes] = useState("");

  // Dashboard
  const [dash, setDash] = useState({
    summary: null,
    dist: null,
    pain: [],
    recent: [],
  });
  const [dashLoading, setDashLoading] = useState(false);

  const canSubmit = useMemo(() => {
    return (
      form.training_days_per_week >= 0 &&
      form.training_days_per_week <= 7 &&
      form.rest_days_per_week >= 0 &&
      form.rest_days_per_week <= 7 &&
      form.rpe >= 1 &&
      form.rpe <= 10 &&
      form.pain_score >= 0 &&
      form.pain_score <= 10
    );
  }, [form]);

  function updateField(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setResult(null);
    setCoachNotes(""); // reset AI output when new assessment is made
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/assess`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`API error ${res.status}: ${text}`);
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function getAICoach() {
    setCoachLoading(true);
    setCoachNotes("");

    try {
      const res = await fetch(`${API_BASE}/ai/coach`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`AI error ${res.status}: ${text}`);
      }

      const data = await res.json();
      setCoachNotes(data.coach_notes);
    } catch (e) {
      alert(e.message || "Failed to generate AI coaching.");
    } finally {
      setCoachLoading(false);
    }
  }

  async function loadDashboard() {
    setDashLoading(true);

    try {
      const [summaryRes, distRes, painRes, recentRes] = await Promise.all([
        fetch(`${API_BASE}/dashboard/summary`),
        fetch(`${API_BASE}/dashboard/risk_distribution`),
        fetch(`${API_BASE}/dashboard/top_pain_locations?limit=5`),
        fetch(`${API_BASE}/dashboard/recent?limit=10`),
      ]);

      if (!summaryRes.ok || !distRes.ok || !painRes.ok || !recentRes.ok) {
        throw new Error("Dashboard API call failed. Check backend is running.");
      }

      const summary = await summaryRes.json();
      const dist = await distRes.json();
      const pain = await painRes.json();
      const recent = await recentRes.json();

      setDash({ summary, dist, pain, recent });
    } catch (e) {
      console.error(e);
      alert(e.message || "Failed to load dashboard.");
    } finally {
      setDashLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 24, fontFamily: "system-ui" }}>
      <h1>Injury Prevention DSS</h1>
      <p>Enter your training and recovery details to receive an injury risk score and recommendations.</p>

      <form
        onSubmit={handleSubmit}
        style={{ display: "grid", gap: 12, padding: 16, border: "1px solid #ddd", borderRadius: 10 }}
      >
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <label>
            Training days / week
            <input
              type="number"
              min="0"
              max="7"
              value={form.training_days_per_week}
              onChange={(e) => updateField("training_days_per_week", Number(e.target.value))}
            />
          </label>

          <label>
            Rest days / week
            <input
              type="number"
              min="0"
              max="7"
              value={form.rest_days_per_week}
              onChange={(e) => updateField("rest_days_per_week", Number(e.target.value))}
            />
          </label>

          <label>
            Session duration (minutes)
            <input
              type="number"
              min="0"
              max="300"
              value={form.session_minutes}
              onChange={(e) => updateField("session_minutes", Number(e.target.value))}
            />
          </label>

          <label>
            Weekly sets (total)
            <input
              type="number"
              min="0"
              max="300"
              value={form.weekly_sets}
              onChange={(e) => updateField("weekly_sets", Number(e.target.value))}
            />
          </label>

          <label>
            Intensity (RPE 1–10)
            <input
              type="number"
              min="1"
              max="10"
              value={form.rpe}
              onChange={(e) => updateField("rpe", Number(e.target.value))}
            />
          </label>

          <label>
            Sleep (hours)
            <input
              type="number"
              step="0.5"
              min="0"
              max="16"
              value={form.sleep_hours}
              onChange={(e) => updateField("sleep_hours", Number(e.target.value))}
            />
          </label>

          <label>
            Pain score (0–10)
            <input
              type="number"
              min="0"
              max="10"
              value={form.pain_score}
              onChange={(e) => updateField("pain_score", Number(e.target.value))}
            />
          </label>

          <label>
            Pain location
            <select value={form.pain_location} onChange={(e) => updateField("pain_location", e.target.value)}>
              <option value="none">None</option>
              <option value="shoulder">Shoulder</option>
              <option value="wrist">Wrist</option>
              <option value="elbow">Elbow</option>
              <option value="knee">Knee</option>
              <option value="lower_back">Lower back</option>
              <option value="other">Other</option>
            </select>
          </label>

          <label>
            Experience level
            <select
              value={form.experience_level}
              onChange={(e) => updateField("experience_level", e.target.value)}
            >
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
            </select>
          </label>
        </div>

        <button type="submit" disabled={!canSubmit || loading} style={{ padding: 10, borderRadius: 8 }}>
          {loading ? "Assessing..." : "Assess Injury Risk"}
        </button>

        {!canSubmit && <p style={{ color: "crimson" }}>Please check your inputs (ranges are enforced).</p>}
      </form>

      {error && (
        <div style={{ marginTop: 16, padding: 12, border: "1px solid #f5c2c7", borderRadius: 10 }}>
          <strong style={{ color: "crimson" }}>Error:</strong> <span>{error}</span>
        </div>
      )}

      {result && (
        <div style={{ marginTop: 20, padding: 16, border: "1px solid #ddd", borderRadius: 10 }}>
          <h2>Result</h2>

          {/* Risk level badge */}
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <p style={{ margin: 0 }}>
              <strong>Risk level:</strong>
            </p>

            <span
              style={{
                padding: "4px 10px",
                borderRadius: 999,
                border: `1px solid ${riskTheme(result.risk_level).border}`,
                background: riskTheme(result.risk_level).bg,
                color: riskTheme(result.risk_level).text,
                fontWeight: 700,
                letterSpacing: 0.4,
              }}
            >
              {result.risk_level.toUpperCase()}
            </span>
          </div>

          {/* Risk score bar */}
          <div style={{ marginTop: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <span style={{ fontWeight: 700 }}>Risk score</span>
              <span>{result.risk_score} / 100</span>
            </div>

            <div
              style={{
                height: 12,
                background: "#f1f3f5",
                borderRadius: 999,
                overflow: "hidden",
                border: "1px solid #dee2e6",
              }}
            >
              <div
                style={{
                  width: `${result.risk_score}%`,
                  height: "100%",
                  background: scoreTheme(result.risk_score).border,
                }}
              />
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: 12,
                opacity: 0.7,
                marginTop: 6,
              }}
            >
              <span>Low (0–34)</span>
              <span>Moderate (35–69)</span>
              <span>High (70–100)</span>
            </div>
          </div>

          <h3>Score breakdown</h3>
          <ul>
            {Object.entries(result.score_breakdown || {})
              .filter(([_, val]) => val > 0)
              .map(([key, val]) => (
                <li key={key}>
                  <strong>
                    {{
                      pain: "Pain",
                      volume: "Weekly training volume",
                      intensity: "Training intensity",
                      sleep: "Sleep",
                      rest: "Rest & recovery",
                      experience: "Experience level",
                    }[key] || key}
                    :
                  </strong>{" "}
                  +{val}
                </li>
              ))}
          </ul>

          <h3>Top factors</h3>
          <ul>
            {result.top_factors.map((f, idx) => (
              <li key={idx}>{f}</li>
            ))}
          </ul>

          <h3>Recommendations</h3>
          <ul>
            {result.recommendations.map((r, idx) => (
              <li key={idx}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {/* ✅ AI Coach only shows after result exists */}
      {result && (
        <div style={{ marginTop: 16, padding: 16, border: "1px solid #ddd", borderRadius: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <h2 style={{ margin: 0 }}>AI Coach</h2>
            <button
              onClick={getAICoach}
              disabled={coachLoading || !canSubmit}
              style={{ padding: 10, borderRadius: 8 }}
            >
              {coachLoading ? "Generating..." : "Generate coaching plan"}
            </button>
          </div>

          {!coachNotes && (
            <p style={{ marginTop: 10, opacity: 0.7 }}>
              Generates a short explanation + a 7-day training adjustment plan based on your inputs.
            </p>
          )}

          {coachNotes && (
            <div style={{ marginTop: 10, whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
              {coachNotes}
            </div>
          )}
        </div>
      )}

      {/* ✅ Dashboard */}
      <div style={{ marginTop: 24, padding: 16, border: "1px solid #ddd", borderRadius: 10 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <h2 style={{ margin: 0 }}>Dashboard</h2>
          <button onClick={loadDashboard} disabled={dashLoading} style={{ padding: 10, borderRadius: 8 }}>
            {dashLoading ? "Loading..." : "Load Dashboard"}
          </button>
        </div>

        {!dash.summary && (
          <p style={{ marginTop: 12, opacity: 0.7 }}>
            Click “Load Dashboard” to view analytics from your logged assessments.
          </p>
        )}

        {dash.summary && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 12 }}>
            <div style={{ padding: 12, border: "1px solid #eee", borderRadius: 10 }}>
              <div style={{ opacity: 0.7 }}>Total assessments</div>
              <div style={{ fontSize: 28, fontWeight: 800 }}>{dash.summary.total_assessments}</div>
            </div>

            <div style={{ padding: 12, border: "1px solid #eee", borderRadius: 10 }}>
              <div style={{ opacity: 0.7 }}>Average risk score</div>
              <div style={{ fontSize: 28, fontWeight: 800 }}>{dash.summary.avg_risk_score}</div>
            </div>
          </div>
        )}

        {dash.dist && (
          <div style={{ marginTop: 16 }}>
            <h3>Risk distribution</h3>
            <ul>
              <li><strong>Low:</strong> {dash.dist.low}</li>
              <li><strong>Moderate:</strong> {dash.dist.moderate}</li>
              <li><strong>High:</strong> {dash.dist.high}</li>
            </ul>
          </div>
        )}

        {dash.pain?.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h3>Top pain locations</h3>
            <ul>
              {dash.pain.map((p) => (
                <li key={p.key}>
                  <strong>{p.key}:</strong> {p.count}
                </li>
              ))}
            </ul>
          </div>
        )}

        {dash.recent?.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h3>Recent assessments</h3>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: 8 }}>ID</th>
                    <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: 8 }}>Time (UTC)</th>
                    <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: 8 }}>Score</th>
                    <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: 8 }}>Level</th>
                    <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: 8 }}>Pain</th>
                  </tr>
                </thead>
                <tbody>
                  {dash.recent.map((r) => (
                    <tr key={r.id}>
                      <td style={{ borderBottom: "1px solid #f3f3f3", padding: 8 }}>{r.id}</td>
                      <td style={{ borderBottom: "1px solid #f3f3f3", padding: 8 }}>{r.created_at}</td>
                      <td style={{ borderBottom: "1px solid #f3f3f3", padding: 8 }}>{r.risk_score}</td>
                      <td style={{ borderBottom: "1px solid #f3f3f3", padding: 8 }}>{r.risk_level}</td>
                      <td style={{ borderBottom: "1px solid #f3f3f3", padding: 8 }}>{r.pain_location}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <p style={{ marginTop: 18, opacity: 0.7 }}>
        Backend: {API_BASE} • Try changing pain score, weekly sets, or RPE to see the risk change.
      </p>
    </div>
  );
}