import { useMemo, useState } from "react";

const API_BASE = "http://127.0.0.1:8000";

function riskLabel(level) {
  const map = {
    low: {
      text: "Low",
      pill: "bg-emerald-500/15 text-emerald-200 ring-emerald-500/30",
      dot: "bg-emerald-400",
    },
    moderate: {
      text: "Moderate",
      pill: "bg-amber-500/15 text-amber-200 ring-amber-500/30",
      dot: "bg-amber-400",
    },
    high: {
      text: "High",
      pill: "bg-rose-500/15 text-rose-200 ring-rose-500/30",
      dot: "bg-rose-400",
    },
  };
  return (
    map[level] || {
      text: level || "Unknown",
      pill: "bg-slate-500/15 text-slate-200 ring-slate-500/30",
      dot: "bg-slate-400",
    }
  );
}

function scoreColor(score) {
  if (score >= 70) return "bg-rose-500";
  if (score >= 35) return "bg-amber-500";
  return "bg-emerald-500";
}

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
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

  // ✅ AI Coach (structured)
  const [coachLoading, setCoachLoading] = useState(false);
  const [coachData, setCoachData] = useState(null);
  const [coachError, setCoachError] = useState("");

  // ✅ Dashboard (extended)
  const [dash, setDash] = useState({
    summary: null,
    dist: null,
    pain: [],
    recent: [],
    aiUsage: null,
    riskTrend: [],
    topFactors: [],
    avgBreakdown: null,
  });
  const [dashLoading, setDashLoading] = useState(false);
  const [dashError, setDashError] = useState("");

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

    // reset coach output on new assessment
    setCoachData(null);
    setCoachError("");

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
    setCoachError("");
    setCoachData(null);

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
      setCoachData(data);

      // optional: refresh dashboard after generating coach so ai_usage updates
      // (only if user already loaded dashboard once)
      // you can uncomment this if you want auto-refresh:
      // await loadDashboard();
    } catch (e) {
      setCoachError(e.message || "Failed to generate AI coaching.");
    } finally {
      setCoachLoading(false);
    }
  }

  async function loadDashboard() {
    setDashLoading(true);
    setDashError("");

    try {
      const [
        summaryRes,
        distRes,
        painRes,
        recentRes,
        aiUsageRes,
        trendRes,
        topFactorsRes,
        avgBreakdownRes,
      ] = await Promise.all([
        fetch(`${API_BASE}/dashboard/summary`),
        fetch(`${API_BASE}/dashboard/risk_distribution`),
        fetch(`${API_BASE}/dashboard/top_pain_locations?limit=5`),
        fetch(`${API_BASE}/dashboard/recent?limit=10`),

        // ✅ new endpoints
        fetch(`${API_BASE}/dashboard/ai_usage`),
        fetch(`${API_BASE}/dashboard/risk_trend?days=30`),
        fetch(`${API_BASE}/dashboard/top_factors?limit=8&days=30`),
        fetch(`${API_BASE}/dashboard/avg_breakdown?days=30`),
      ]);

      const allOk = [
        summaryRes,
        distRes,
        painRes,
        recentRes,
        aiUsageRes,
        trendRes,
        topFactorsRes,
        avgBreakdownRes,
      ].every((r) => r.ok);

      if (!allOk) {
        throw new Error("Dashboard API call failed. Check backend is running.");
      }

      const summary = await summaryRes.json();
      const dist = await distRes.json();
      const pain = await painRes.json();
      const recent = await recentRes.json();

      const aiUsage = await aiUsageRes.json();
      const riskTrend = await trendRes.json();
      const topFactors = await topFactorsRes.json();
      const avgBreakdown = await avgBreakdownRes.json();

      setDash({
        summary,
        dist,
        pain,
        recent,
        aiUsage,
        riskTrend,
        topFactors,
        avgBreakdown,
      });
    } catch (e) {
      console.error(e);
      setDashError(e.message || "Failed to load dashboard.");
    } finally {
      setDashLoading(false);
    }
  }

  const levelUI = result?.risk_level ? riskLabel(result.risk_level) : null;

  // for trend visualization scaling
  const trendMax = useMemo(() => {
    if (!dash.riskTrend?.length) return 100;
    const maxAvg = Math.max(...dash.riskTrend.map((p) => Number(p.avg_risk_score || 0)));
    return Math.max(10, Math.min(100, Math.ceil(maxAvg)));
  }, [dash.riskTrend]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* subtle background */}
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute -top-24 left-1/2 h-72 w-[48rem] -translate-x-1/2 rounded-full bg-indigo-500/20 blur-3xl" />
        <div className="absolute top-64 left-10 h-64 w-64 rounded-full bg-emerald-500/10 blur-3xl" />
        <div className="absolute bottom-10 right-10 h-72 w-72 rounded-full bg-rose-500/10 blur-3xl" />
      </div>

      {/* content wrapper */}
      <div className="relative mx-auto max-w-6xl px-5 py-8">
        {/* Nav */}
        <div className="flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/5 px-5 py-3 backdrop-blur">
          <div className="flex items-center gap-3">
            <span className="h-3 w-3 rounded-full bg-indigo-400 shadow-[0_0_20px_rgba(99,102,241,0.8)]" />
            <div className="font-semibold tracking-tight">Injury Prevention DSS</div>
          </div>
          <div className="hidden sm:flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            Local • {API_BASE}
          </div>
        </div>

        {/* Hero */}
        <div className="mt-8">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Reduce injury risk with smarter training decisions
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-300 sm:text-base">
            Enter your training and recovery details to get a risk score, recommendations, dashboard analytics,
            and an AI coaching plan.
          </p>
        </div>

        {/* Layout */}
        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          {/* LEFT */}
          <div className="space-y-6">
            {/* Assessment Card */}
            <div className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-xl shadow-black/20 backdrop-blur">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-lg font-semibold tracking-tight">Assessment</h2>
                  <p className="text-xs text-slate-300">Fill out the inputs and run the assessment.</p>
                </div>

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={loadDashboard}
                    disabled={dashLoading}
                    className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {dashLoading ? "Loading..." : "Refresh Dashboard"}
                  </button>
                </div>
              </div>

              <form onSubmit={handleSubmit} className="mt-5">
                <div className="grid gap-4 sm:grid-cols-2">
                  <FieldNumber
                    label="Training days / week"
                    min={0}
                    max={7}
                    value={form.training_days_per_week}
                    onChange={(v) => updateField("training_days_per_week", v)}
                  />
                  <FieldNumber
                    label="Rest days / week"
                    min={0}
                    max={7}
                    value={form.rest_days_per_week}
                    onChange={(v) => updateField("rest_days_per_week", v)}
                  />
                  <FieldNumber
                    label="Session duration (minutes)"
                    min={0}
                    max={300}
                    value={form.session_minutes}
                    onChange={(v) => updateField("session_minutes", v)}
                  />
                  <FieldNumber
                    label="Weekly sets (total)"
                    min={0}
                    max={300}
                    value={form.weekly_sets}
                    onChange={(v) => updateField("weekly_sets", v)}
                  />
                  <FieldNumber
                    label="Intensity (RPE 1–10)"
                    min={1}
                    max={10}
                    value={form.rpe}
                    onChange={(v) => updateField("rpe", v)}
                  />
                  <FieldNumber
                    label="Sleep (hours)"
                    min={0}
                    max={16}
                    step={0.5}
                    value={form.sleep_hours}
                    onChange={(v) => updateField("sleep_hours", v)}
                  />
                  <FieldNumber
                    label="Pain score (0–10)"
                    min={0}
                    max={10}
                    value={form.pain_score}
                    onChange={(v) => updateField("pain_score", v)}
                  />

                  <div>
                    <label className="text-xs font-medium text-slate-200">Pain location</label>
                    <select
                      value={form.pain_location}
                      onChange={(e) => updateField("pain_location", e.target.value)}
                      className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-indigo-400/60"
                    >
                      <option value="none">None</option>
                      <option value="shoulder">Shoulder</option>
                      <option value="wrist">Wrist</option>
                      <option value="elbow">Elbow</option>
                      <option value="knee">Knee</option>
                      <option value="lower_back">Lower back</option>
                      <option value="other">Other</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-xs font-medium text-slate-200">Experience level</label>
                    <select
                      value={form.experience_level}
                      onChange={(e) => updateField("experience_level", e.target.value)}
                      className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-indigo-400/60"
                    >
                      <option value="beginner">Beginner</option>
                      <option value="intermediate">Intermediate</option>
                      <option value="advanced">Advanced</option>
                    </select>
                  </div>
                </div>

                <div className="mt-5 flex flex-wrap gap-2">
                  <button
                    type="submit"
                    disabled={!canSubmit || loading}
                    className="rounded-xl bg-indigo-500 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {loading ? "Assessing..." : "Assess Injury Risk"}
                  </button>

                  {result && (
                    <button
                      type="button"
                      onClick={getAICoach}
                      disabled={coachLoading || !canSubmit}
                      className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-slate-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {coachLoading ? "Generating..." : "Generate coaching plan"}
                    </button>
                  )}
                </div>

                {!canSubmit && (
                  <p className="mt-3 text-xs text-rose-200">
                    Please check your inputs (ranges are enforced).
                  </p>
                )}
              </form>
            </div>

            {/* Error */}
            {error && (
              <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
                <span className="font-semibold">Error:</span> {error}
              </div>
            )}

            {/* Result */}
            {result && (
              <div className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-xl shadow-black/20 backdrop-blur">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold tracking-tight">Result</h2>
                    <p className="text-xs text-slate-300">Your risk score + key drivers.</p>
                  </div>

                  <span
                    className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs ring-1 ${
                      levelUI?.pill || "bg-slate-500/15 text-slate-200 ring-slate-500/30"
                    }`}
                  >
                    <span className={`h-2 w-2 rounded-full ${levelUI?.dot || "bg-slate-400"}`} />
                    {(levelUI?.text || "UNKNOWN").toUpperCase()}
                  </span>
                </div>

                {/* Score */}
                <div className="mt-5">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-semibold text-slate-200">Risk score</span>
                    <span className="text-slate-200">{result.risk_score} / 100</span>
                  </div>

                  <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                      className={`h-full ${scoreColor(result.risk_score)} transition-all`}
                      style={{ width: `${result.risk_score}%` }}
                    />
                  </div>

                  <div className="mt-2 flex justify-between text-[11px] text-slate-400">
                    <span>Low (0–34)</span>
                    <span>Moderate (35–69)</span>
                    <span>High (70–100)</span>
                  </div>
                </div>

                {/* Breakdown */}
                <Section title="Score breakdown">
                  <ul className="mt-2 space-y-1 text-sm text-slate-200">
                    {Object.entries(result.score_breakdown || {})
                      .filter(([_, val]) => val > 0)
                      .map(([key, val]) => (
                        <li key={key} className="flex justify-between gap-3">
                          <span className="text-slate-200">
                            {{
                              pain: "Pain",
                              volume: "Weekly training volume",
                              intensity: "Training intensity",
                              sleep: "Sleep",
                              rest: "Rest & recovery",
                              experience: "Experience level",
                            }[key] || key}
                          </span>
                          <span className="text-slate-100">+{val}</span>
                        </li>
                      ))}
                  </ul>
                </Section>

                <Section title="Top factors">
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-200">
                    {result.top_factors.map((f, idx) => (
                      <li key={idx}>{f}</li>
                    ))}
                  </ul>
                </Section>

                <Section title="Recommendations">
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-200">
                    {result.recommendations.map((r, idx) => (
                      <li key={idx}>{r}</li>
                    ))}
                  </ul>
                </Section>
              </div>
            )}

            {/* AI Coach (Structured Render) */}
            {result && (
              <div className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-xl shadow-black/20 backdrop-blur">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold tracking-tight">AI Coach</h2>
                    <p className="text-xs text-slate-300">Structured coaching plan (7-day).</p>
                  </div>

                  <button
                    onClick={getAICoach}
                    disabled={coachLoading || !canSubmit}
                    className="rounded-xl bg-white/10 px-4 py-2 text-sm font-semibold text-slate-100 hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {coachLoading ? "Generating..." : "Generate plan"}
                  </button>
                </div>

                {coachError && (
                  <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-100">
                    {coachError}
                  </div>
                )}

                {!coachLoading && !coachData && !coachError && (
                  <p className="mt-4 text-sm text-slate-300">
                    Click “Generate plan” to get a tailored 7-day adjustment plan based on your inputs.
                  </p>
                )}

                {coachData?.coach && (
                  <div className="mt-4 space-y-4">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-300">
                      <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">
                        Mode: <span className="text-slate-100">{coachData.mode}</span>
                      </span>
                      <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">
                        Model: <span className="text-slate-100">{coachData.model_used}</span>
                      </span>
                    </div>

                    <div className="rounded-xl border border-white/10 bg-slate-950/40 p-4">
                      <div className="text-sm font-semibold text-slate-100">Summary</div>
                      <div className="mt-2 text-sm text-slate-200">
                        {coachData.coach.risk_level_summary}
                      </div>
                    </div>

                    <div className="rounded-xl border border-white/10 bg-slate-950/40 p-4">
                      <div className="text-sm font-semibold text-slate-100">Top drivers</div>
                      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-200">
                        {(coachData.coach.top_drivers || []).map((d, idx) => (
                          <li key={idx}>{d}</li>
                        ))}
                      </ul>
                    </div>

                    <div className="rounded-xl border border-white/10 bg-slate-950/40 p-4">
                      <div className="text-sm font-semibold text-slate-100">7-day plan</div>

                      <div className="mt-3 grid gap-4 md:grid-cols-3">
                        <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                          <div className="text-xs font-semibold uppercase tracking-wide text-emerald-200">
                            Keep
                          </div>
                          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-200">
                            {(coachData.coach.seven_day_plan?.keep || []).map((x, idx) => (
                              <li key={idx}>{x}</li>
                            ))}
                          </ul>
                        </div>

                        <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                          <div className="text-xs font-semibold uppercase tracking-wide text-amber-200">
                            Reduce
                          </div>
                          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-200">
                            {(coachData.coach.seven_day_plan?.reduce || []).map((x, idx) => (
                              <li key={idx}>{x}</li>
                            ))}
                          </ul>
                        </div>

                        <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                          <div className="text-xs font-semibold uppercase tracking-wide text-sky-200">
                            Add
                          </div>
                          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-200">
                            {(coachData.coach.seven_day_plan?.add || []).map((x, idx) => (
                              <li key={idx}>{x}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-4">
                      <div className="text-sm font-semibold text-rose-200">Red flags</div>
                      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-rose-100/90">
                        {(coachData.coach.red_flags || []).map((x, idx) => (
                          <li key={idx}>{x}</li>
                        ))}
                      </ul>
                    </div>

                    {coachData.raw_text && (
                      <details className="rounded-xl border border-white/10 bg-slate-950/30 p-3 text-sm text-slate-200">
                        <summary className="cursor-pointer text-xs text-slate-300">
                          Debug: raw model output
                        </summary>
                        <pre className="mt-2 whitespace-pre-wrap text-xs leading-relaxed">
                          {coachData.raw_text}
                        </pre>
                      </details>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* RIGHT */}
          <div className="space-y-6">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-xl shadow-black/20 backdrop-blur">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold tracking-tight">Dashboard</h2>
                  <p className="text-xs text-slate-300">Analytics from saved assessments.</p>
                </div>
                <button
                  onClick={loadDashboard}
                  disabled={dashLoading}
                  className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-slate-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {dashLoading ? "Loading..." : "Load"}
                </button>
              </div>

              {/* dashboard error */}
              {dashError && (
                <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-100">
                  {dashError}
                </div>
              )}

              <div className="mt-4">
                {!dash.summary ? (
                  <p className="text-sm text-slate-300">
                    Click “Load” to view analytics from your logged assessments.
                  </p>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    <Stat label="Total assessments" value={dash.summary.total_assessments} />
                    <Stat label="Avg risk score" value={dash.summary.avg_risk_score} />
                  </div>
                )}
              </div>

              {/* ✅ NEW: AI usage */}
              {dash.aiUsage && (
                <Section title="AI usage">
                  <div className="mt-2 grid grid-cols-3 gap-2">
                    <MiniStat label="Ollama" value={dash.aiUsage.ollama ?? 0} tone="emerald" />
                    <MiniStat label="Fallback" value={dash.aiUsage.fallback ?? 0} tone="amber" />
                    <MiniStat label="Total" value={dash.aiUsage.total_assessments ?? 0} tone="rose" />
                  </div>
                  <p className="mt-2 text-xs text-slate-400">
                    If these stay at 0, make sure you press <span className="text-slate-200">Generate plan</span> after an assessment.
                  </p>
                </Section>
              )}

              {dash.dist && (
                <Section title="Risk distribution">
                  <div className="mt-2 grid grid-cols-3 gap-2">
                    <MiniStat label="Low" value={dash.dist.low} tone="emerald" />
                    <MiniStat label="Moderate" value={dash.dist.moderate} tone="amber" />
                    <MiniStat label="High" value={dash.dist.high} tone="rose" />
                  </div>
                </Section>
              )}

              {/* ✅ NEW: Risk trend */}
              {dash.riskTrend?.length > 0 && (
                <Section title="Risk trend (last 30 days)">
                  <div className="mt-2 space-y-2">
                    {dash.riskTrend.slice(-10).map((p) => {
                      const w = clamp((Number(p.avg_risk_score || 0) / trendMax) * 100, 3, 100);
                      return (
                        <div key={p.day} className="flex items-center gap-3">
                          <div className="w-[86px] shrink-0 text-xs text-slate-400">{p.day}</div>
                          <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/10">
                            <div className="h-full bg-indigo-500/70" style={{ width: `${w}%` }} />
                          </div>
                          <div className="w-[76px] shrink-0 text-right text-xs text-slate-300">
                            {Number(p.avg_risk_score).toFixed(1)}{" "}
                            <span className="text-slate-500">({p.count})</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    Showing last 10 days with activity. (Avg risk • count)
                  </p>
                </Section>
              )}

              {/* ✅ NEW: Top factors */}
              {dash.topFactors?.length > 0 && (
                <Section title="Top factors (last 30 days)">
                  <ul className="mt-2 space-y-1 text-sm text-slate-200">
                    {dash.topFactors.map((t) => (
                      <li key={t.key} className="flex justify-between gap-3">
                        <span className="text-slate-200">{t.key}</span>
                        <span className="text-slate-100">{t.count}</span>
                      </li>
                    ))}
                  </ul>
                </Section>
              )}

              {/* ✅ NEW: Avg breakdown */}
              {dash.avgBreakdown && (
                <Section title="Avg score breakdown (last 30 days)">
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    <SmallStat label="Pain" value={dash.avgBreakdown.pain} />
                    <SmallStat label="Volume" value={dash.avgBreakdown.volume} />
                    <SmallStat label="Intensity" value={dash.avgBreakdown.intensity} />
                    <SmallStat label="Sleep" value={dash.avgBreakdown.sleep} />
                    <SmallStat label="Rest" value={dash.avgBreakdown.rest} />
                    <SmallStat label="Experience" value={dash.avgBreakdown.experience} />
                  </div>
                </Section>
              )}

              {dash.pain?.length > 0 && (
                <Section title="Top pain locations">
                  <ul className="mt-2 space-y-1 text-sm text-slate-200">
                    {dash.pain.map((p) => (
                      <li key={p.key} className="flex justify-between">
                        <span className="text-slate-200">{p.key}</span>
                        <span className="text-slate-100">{p.count}</span>
                      </li>
                    ))}
                  </ul>
                </Section>
              )}

              {dash.recent?.length > 0 && (
                <Section title="Recent assessments">
                  <div className="mt-2 overflow-x-auto rounded-xl border border-white/10">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-white/5 text-xs text-slate-300">
                        <tr>
                          <th className="px-3 py-2">ID</th>
                          <th className="px-3 py-2">Time (UTC)</th>
                          <th className="px-3 py-2">Score</th>
                          <th className="px-3 py-2">Level</th>
                          <th className="px-3 py-2">Pain</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/10">
                        {dash.recent.map((r) => (
                          <tr key={r.id} className="hover:bg-white/5">
                            <td className="px-3 py-2 text-slate-200">{r.id}</td>
                            <td className="px-3 py-2 text-slate-300">{r.created_at}</td>
                            <td className="px-3 py-2 text-slate-200">{r.risk_score}</td>
                            <td className="px-3 py-2 text-slate-200">{r.risk_level}</td>
                            <td className="px-3 py-2 text-slate-200">{r.pain_location}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Section>
              )}
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-xs text-slate-300">
              Tip: Try increasing pain score / weekly sets / RPE to see risk change.
            </div>
          </div>
        </div>

        <div className="mt-8 text-center text-xs text-slate-500">
          Injury Prevention DSS • Local development build
        </div>
      </div>
    </div>
  );
}

/* ---------- Small UI helpers ---------- */

function FieldNumber({ label, value, onChange, min, max, step }) {
  return (
    <div>
      <label className="text-xs font-medium text-slate-200">{label}</label>
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-indigo-400/60"
      />
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="mt-5">
      <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
      {children}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold tracking-tight text-slate-100">{value}</div>
    </div>
  );
}

function SmallStat({ label, value }) {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/30 p-3">
      <div className="text-[11px] text-slate-400">{label}</div>
      <div className="mt-1 text-base font-semibold text-slate-100">{Number(value ?? 0).toFixed(2)}</div>
    </div>
  );
}

function MiniStat({ label, value, tone }) {
  const toneClass =
    tone === "emerald"
      ? "bg-emerald-500/10 ring-emerald-500/20"
      : tone === "amber"
      ? "bg-amber-500/10 ring-amber-500/20"
      : "bg-rose-500/10 ring-rose-500/20";

  return (
    <div className={`rounded-xl p-3 ring-1 ${toneClass}`}>
      <div className="text-xs text-slate-300">{label}</div>
      <div className="mt-1 text-lg font-semibold text-slate-100">{value}</div>
    </div>
  );
}