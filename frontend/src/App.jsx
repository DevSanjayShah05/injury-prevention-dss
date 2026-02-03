import { useMemo, useState } from "react";
import "./App.css";

const API_BASE = "http://127.0.0.1:8000";

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

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 24, fontFamily: "system-ui" }}>
      <h1>Injury Prevention DSS</h1>
      <p>
        Enter your training and recovery details to receive an injury risk score and recommendations.
      </p>

      <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12, padding: 16, border: "1px solid #ddd", borderRadius: 10 }}>
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
            <select
              value={form.pain_location}
              onChange={(e) => updateField("pain_location", e.target.value)}
            >
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
          <p>
            <strong>Risk score:</strong> {result.risk_score} / 100
          </p>
          <p>
            <strong>Risk level:</strong> {result.risk_level.toUpperCase()}
          </p>

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

      <p style={{ marginTop: 18, opacity: 0.7 }}>
        Backend: {API_BASE} • Try changing pain score, weekly sets, or RPE to see the risk change.
      </p>
    </div>
  );
}
