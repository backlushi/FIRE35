import { useState, useEffect } from "react";
import api from "../api";

const TRAINER_TOPICS = [
  {
    id: "investments",
    emoji: "💰",
    title: "Инвестиции",
    scenario: "У тебя 300 000 руб. Ты хочешь составить диверсифицированный портфель на 3 года с умеренным риском. Напиши промпт для AI-советника по инвестициям.",
  },
  {
    id: "budget",
    emoji: "📊",
    title: "Бюджет",
    scenario: "Твои расходы каждый месяц превышают доходы на 10-15%. Напиши промпт для AI-аналитика, который поможет найти утечки и оптимизировать бюджет.",
  },
  {
    id: "realestate",
    emoji: "🏠",
    title: "Недвижимость",
    scenario: "Рассматриваешь покупку квартиры для сдачи в аренду за 5 млн руб. Хочешь понять — выгодно ли это. Напиши промпт для AI-эксперта по недвижимости.",
  },
  {
    id: "career",
    emoji: "💼",
    title: "Карьера",
    scenario: "Ты работаешь 3 года на одном месте, зарплата не растёт. Хочешь повысить зарплату на 30% или сменить компанию. Напиши промпт для AI-карьерного консультанта.",
  },
  {
    id: "mindset",
    emoji: "🧠",
    title: "Психология",
    scenario: "Ты зарабатываешь достаточно, но деньги «утекают» — импульсивные покупки, нет подушки. Напиши промпт для AI-коуча по психологии денег.",
  },
];

export default function AiBattlePage({ user }) {
  return (
    <div style={{ paddingBottom: 16 }}>
      <TrainerView />
    </div>
  );
}

/* ─── Батл недели ─────────────────────────────────────────── */
function BattleView() {
  const [view, setView] = useState("challenge");
  const [challenge, setChallenge] = useState(null);
  const [submission, setSubmission] = useState(null);
  const [promptText, setPromptText] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [leaderboard, setLeaderboard] = useState(null);
  const [lbLoading, setLbLoading] = useState(false);

  useEffect(() => { loadCurrent(); }, []);

  async function loadCurrent() {
    setLoading(true); setError(null);
    try {
      const res = await api.get("/ai-battle/current");
      setChallenge(res.data.challenge);
      if (res.data.submission) {
        setSubmission(res.data.submission);
        setResult(res.data.submission.feedback);
        setPromptText(res.data.submission.prompt_text);
      }
    } catch (e) {
      setError(e.response?.data?.detail || "Не удалось загрузить задание");
    }
    setLoading(false);
  }

  async function loadLeaderboard() {
    setLbLoading(true);
    try {
      const res = await api.get("/ai-battle/leaderboard");
      setLeaderboard(res.data);
    } catch { setLeaderboard({ entries: [] }); }
    setLbLoading(false);
  }

  async function handleSubmit() {
    if (promptText.trim().length < 10) { setError("Промпт слишком короткий"); return; }
    setSubmitting(true); setError(null);
    try {
      const res = await api.post("/ai-battle/submit", { prompt_text: promptText });
      setResult(res.data.feedback);
      setSubmission({ score: res.data.score, prompt_text: promptText, feedback: res.data.feedback });
      if (leaderboard) loadLeaderboard();
    } catch (e) {
      setError(e.response?.data?.detail || "Ошибка отправки. Попробуй ещё раз.");
    }
    setSubmitting(false);
  }

  if (loading) return <div className="center-text" style={{ padding: 24 }}>Загружаю задание...</div>;
  if (error && !challenge) return <div className="card error-text">{error}</div>;

  const maxScore = challenge?.criteria?.reduce((s, c) => s + c.max, 0) || 100;

  return (
    <>
      <div className="card" style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div style={{ fontSize: 11, color: "#888", marginBottom: 4 }}>🤖 AI-БАТЛ · {challenge?.week}</div>
            <div style={{ fontWeight: 700, fontSize: 15 }}>{challenge?.theme}</div>
          </div>
          <button className="btn" style={{ fontSize: 12, padding: "4px 10px" }}
            onClick={() => { setView("leaderboard"); if (!leaderboard) loadLeaderboard(); }}>
            🏆 Топ
          </button>
        </div>
      </div>

      {view === "challenge" && (
        <>
          <div className="card" style={{ marginBottom: 12 }}>
            <div className="field-label" style={{ marginBottom: 8 }}>📋 Задание недели</div>
            <p style={{ fontSize: 14, lineHeight: 1.6, margin: 0 }}>{challenge?.task}</p>
          </div>

          <div className="card" style={{ marginBottom: 12 }}>
            <div className="field-label" style={{ marginBottom: 8 }}>📊 Критерии оценки</div>
            {challenge?.criteria.map(c => (
              <div key={c.name} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontSize: 13, color: "#555" }}>
                  <span style={{ fontWeight: 600 }}>{c.name}</span>
                  <span style={{ fontSize: 11, color: "#999", marginLeft: 6 }}>{c.hint}</span>
                </span>
                <span style={{ fontSize: 13, fontWeight: 600, color: "#2a9d8f", minWidth: 40, textAlign: "right" }}>+{c.max} б.</span>
              </div>
            ))}
            <div style={{ borderTop: "1px solid #eee", marginTop: 8, paddingTop: 8, display: "flex", justifyContent: "flex-end" }}>
              <span style={{ fontSize: 13, fontWeight: 700 }}>Максимум: {maxScore} баллов</span>
            </div>
          </div>

          {!result && (
            <div className="card" style={{ marginBottom: 12 }}>
              <div className="field-label" style={{ marginBottom: 8 }}>✍️ Твой промпт</div>
              <textarea className="input" value={promptText} onChange={e => setPromptText(e.target.value)}
                rows={7} placeholder="Напиши промпт здесь..."
                style={{ resize: "vertical", fontFamily: "inherit", fontSize: 14 }} disabled={submitting} />
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
                <span style={{ fontSize: 11, color: "#aaa" }}>{promptText.length} / 3000</span>
                {error && <span className="error-text" style={{ fontSize: 12 }}>{error}</span>}
              </div>
              <button className="btn btn-primary btn-full" style={{ marginTop: 10 }}
                onClick={handleSubmit} disabled={submitting || promptText.trim().length < 10}>
                {submitting ? "⏳ Оцениваю через AI..." : "🚀 Отправить на оценку"}
              </button>
            </div>
          )}

          {result && submission && (
            <div className="card" style={{ marginBottom: 12 }}>
              <ScoreDisplay score={submission.score} maxScore={maxScore} criteria={challenge.criteria} feedback={result} />
              <button className="btn" style={{ marginTop: 12, width: "100%", fontSize: 13 }}
                onClick={() => { setResult(null); setSubmission(null); setPromptText(""); }}>
                ✏️ Переписать промпт
              </button>
            </div>
          )}
        </>
      )}

      {view === "leaderboard" && (
        <>
          <button className="btn" style={{ marginBottom: 12, fontSize: 13 }} onClick={() => setView("challenge")}>
            ← Назад к заданию
          </button>
          <div className="card">
            <div className="field-label" style={{ marginBottom: 10 }}>
              🏆 Топ недели — {leaderboard?.theme || challenge?.theme}
            </div>
            {lbLoading && <div className="center-text">Загрузка...</div>}
            {!lbLoading && leaderboard?.entries?.length === 0 && (
              <div className="center-text" style={{ color: "#999", fontSize: 14 }}>Пока никто не прошёл батл — будь первым!</div>
            )}
            {!lbLoading && leaderboard?.entries?.map(e => (
              <div key={e.pid} style={{
                display: "flex", alignItems: "center", padding: "8px 0",
                borderBottom: "1px solid #f0f0f0",
                background: e.is_me ? "#f0faf8" : "transparent",
                borderRadius: e.is_me ? 6 : 0, paddingLeft: e.is_me ? 6 : 0,
              }}>
                <span style={{ width: 30, fontWeight: 700, color: rankColor(e.rank) }}>{rankEmoji(e.rank)}</span>
                <span style={{ flex: 1, fontSize: 14 }}>
                  {e.name}
                  {e.is_me && <span style={{ fontSize: 11, color: "#2a9d8f", marginLeft: 6 }}>Вы</span>}
                </span>
                <ScoreBar score={e.score} max={maxScore} />
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}

/* ─── Тренажёр ────────────────────────────────────────────── */
function TrainerView() {
  const [selectedTopic, setSelectedTopic] = useState(null);
  const [history, setHistory] = useState({});
  const [promptText, setPromptText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [idealPrompt, setIdealPrompt] = useState(null);
  const [showIdeal, setShowIdeal] = useState(false);
  const [loadingIdeal, setLoadingIdeal] = useState(false);
  const [aiResponse, setAiResponse] = useState(null);
  const [loadingResponse, setLoadingResponse] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [personalScenario, setPersonalScenario] = useState(null); // null = дефолтный
  const [personalTopicId, setPersonalTopicId] = useState(null);
  const [loadingPersonal, setLoadingPersonal] = useState(false);

  useEffect(() => {
    api.get("/ai-battle/trainer/history").then(r => setHistory(r.data)).catch(() => {});
  }, []);

  async function loadPersonalScenario() {
    setLoadingPersonal(true);
    try {
      const res = await api.post("/ai-battle/trainer/generate-scenario", {
        topic_id: selectedTopic?.id || undefined,
      });
      setPersonalScenario(res.data.scenario);
      setPersonalTopicId(res.data.topic_id || null);
    } catch {
      setPersonalScenario(null);
      setPersonalTopicId(null);
    }
    setLoadingPersonal(false);
  }

  async function handleEvaluate() {
    if (promptText.trim().length < 10) { setError("Промпт слишком короткий"); return; }
    setSubmitting(true); setError(null); setResult(null); setIdealPrompt(null); setAiResponse(null); setShowIdeal(false);
    try {
      const res = await api.post("/ai-battle/trainer", {
        topic_id: selectedTopic.id,
        prompt_text: promptText,
        custom_scenario: personalScenario || undefined,
      });
      setResult(res.data);
      api.get("/ai-battle/trainer/history").then(r => setHistory(r.data)).catch(() => {});
    } catch (e) {
      setError(e.response?.data?.detail || "Ошибка оценки. Попробуй ещё раз.");
    }
    setSubmitting(false);
  }

  async function handleIdeal() {
    if (idealPrompt) { setShowIdeal(v => !v); return; }
    setLoadingIdeal(true);
    try {
      const res = await api.post("/ai-battle/trainer/ideal", { topic_id: selectedTopic.id });
      setIdealPrompt(res.data.ideal_prompt);
      setShowIdeal(true);
    } catch {
      setIdealPrompt("Не удалось сгенерировать. Попробуй ещё раз.");
      setShowIdeal(true);
    }
    setLoadingIdeal(false);
  }

  async function handleRunPrompt() {
    setLoadingResponse(true); setAiResponse(null);
    try {
      const res = await api.post("/ai-battle/trainer/run", {
        topic_id: selectedTopic.id,
        prompt_text: promptText,
      });
      setAiResponse(res.data.response);
    } catch {
      setAiResponse("Не удалось получить ответ. Попробуй ещё раз.");
    }
    setLoadingResponse(false);
  }

  function reset() {
    setSelectedTopic(null); setPromptText(""); setResult(null);
    setError(null); setIdealPrompt(null); setShowIdeal(false);
    setAiResponse(null); setShowHistory(false); setPersonalScenario(null); setPersonalTopicId(null);
  }

  const topicHistory = selectedTopic ? (history[selectedTopic.id] || []) : [];

  // Выбор темы
  if (!selectedTopic) {
    return (
      <>
        {/* ── Персональное задание — вверху ── */}
        <div style={{
          background: "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)",
          borderRadius: 14, padding: "16px", marginBottom: 14,
          boxShadow: "0 4px 16px rgba(42,157,143,0.2)",
        }}>
          <div style={{ color: "#fff", fontWeight: 700, fontSize: 15, marginBottom: 4 }}>
            ✨ Персональное задание
          </div>
          <div style={{ color: "rgba(255,255,255,0.7)", fontSize: 12, lineHeight: 1.5, marginBottom: 12 }}>
            AI анализирует твой профиль, навыки и финансовые отчёты — чем точнее заполнен профиль и отчёты, тем персональнее задание.
          </div>
          {personalScenario ? (
            <>
              <div style={{
                background: "rgba(255,255,255,0.1)", borderRadius: 10,
                padding: "10px 12px", marginBottom: 10,
                fontSize: 13, color: "#e8f5e9", lineHeight: 1.6,
              }}>
                {personalScenario}
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={() => {
                    const t = (personalTopicId && TRAINER_TOPICS.find(t => t.id === personalTopicId))
                      || TRAINER_TOPICS[0];
                    setSelectedTopic(t);
                  }}
                  style={{
                    flex: 1, background: "#2a9d8f", border: "none", color: "#fff",
                    borderRadius: 10, padding: "10px", fontSize: 13, fontWeight: 700, cursor: "pointer",
                  }}
                >
                  🚀 Начать это задание
                </button>
                <button
                  onClick={loadPersonalScenario}
                  disabled={loadingPersonal}
                  style={{
                    background: "rgba(255,255,255,0.15)", border: "none", color: "#fff",
                    borderRadius: 10, padding: "10px 14px", fontSize: 12, cursor: "pointer",
                  }}
                >
                  {loadingPersonal ? "⏳" : "🔄"}
                </button>
              </div>
            </>
          ) : (
            <button
              onClick={loadPersonalScenario}
              disabled={loadingPersonal}
              style={{
                width: "100%", background: "#2a9d8f", border: "none", color: "#fff",
                borderRadius: 10, padding: "12px", fontSize: 14, fontWeight: 700, cursor: "pointer",
              }}
            >
              {loadingPersonal ? "⏳ Анализирую профиль..." : "🎯 Получить моё задание"}
            </button>
          )}
        </div>

        <div style={{ fontSize: 12, color: "#aaa", marginBottom: 8, paddingLeft: 4 }}>Или выбери тему сам:</div>

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {TRAINER_TOPICS.map(t => {
            const th = history[t.id] || [];
            const best = th.length ? Math.max(...th.map(a => a.score)) : null;
            return (
              <button key={t.id} onClick={() => setSelectedTopic(t)}
                style={{
                  background: "#fff", border: "1.5px solid #e8e8e8", borderRadius: 12,
                  padding: "14px 16px", textAlign: "left", cursor: "pointer",
                  display: "flex", alignItems: "center", gap: 12,
                  boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
                }}>
                <span style={{ fontSize: 28 }}>{t.emoji}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 2 }}>{t.title}</div>
                  <div style={{ fontSize: 12, color: "#888" }}>{t.scenario.slice(0, 65)}...</div>
                </div>
                <div style={{ textAlign: "right", flexShrink: 0 }}>
                  {best !== null
                    ? <div style={{ fontSize: 13, fontWeight: 700, color: best >= 80 ? "#2a9d8f" : best >= 50 ? "#e9a84c" : "#e76f51" }}>{best}/100</div>
                    : <div style={{ fontSize: 11, color: "#ccc" }}>не начато</div>
                  }
                  {th.length > 0 && <div style={{ fontSize: 10, color: "#bbb" }}>{th.length} попыт.</div>}
                </div>
              </button>
            );
          })}
        </div>
      </>
    );
  }

  return (
    <>
      <button className="btn" style={{ marginBottom: 12, fontSize: 13 }} onClick={reset}>
        ← Выбрать другую тему
      </button>

      <div className="card" style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
          <div style={{ fontSize: 18 }}>{selectedTopic.emoji} {selectedTopic.title}</div>
          {!result && (
            <button
              onClick={loadPersonalScenario}
              disabled={loadingPersonal}
              style={{
                background: personalScenario ? "#e8f5e9" : "#f5f3ff",
                border: personalScenario ? "1px solid #2a9d8f" : "1px solid #c4b5fd",
                borderRadius: 8, padding: "4px 10px",
                fontSize: 11, fontWeight: 600, cursor: "pointer",
                color: personalScenario ? "#2a9d8f" : "#7c3aed",
              }}
            >
              {loadingPersonal ? "⏳ Генерирую..." : personalScenario ? "🔄 Другое задание" : "🎯 Моё задание"}
            </button>
          )}
        </div>
        {personalScenario ? (
          <>
            <div style={{
              fontSize: 11, color: "#2a9d8f", fontWeight: 600, marginBottom: 4,
              display: "flex", alignItems: "center", gap: 4,
            }}>
              ✨ Персонализировано под тебя
            </div>
            <div style={{ fontSize: 14, lineHeight: 1.6, color: "#222" }}>{personalScenario}</div>
          </>
        ) : (
          <div style={{ fontSize: 14, lineHeight: 1.6, color: "#444" }}>{selectedTopic.scenario}</div>
        )}
      </div>

      {/* История попыток */}
      {topicHistory.length > 0 && (
        <div className="card" style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>
              📈 История ({topicHistory.length} попыт., лучший: {Math.max(...topicHistory.map(a => a.score))}/100)
            </div>
            <button onClick={() => setShowHistory(h => !h)}
              style={{ background: "none", border: "none", fontSize: 12, color: "#2a9d8f", cursor: "pointer" }}>
              {showHistory ? "Скрыть" : "Показать"}
            </button>
          </div>
          {showHistory && (
            <div style={{ marginTop: 10 }}>
              {topicHistory.map((a, i) => {
                const pct = Math.round((a.score / a.max) * 100);
                const color = pct >= 80 ? "#2a9d8f" : pct >= 50 ? "#e9a84c" : "#e76f51";
                return (
                  <div key={a.id} style={{ padding: "8px 0", borderBottom: i < topicHistory.length - 1 ? "1px solid #f0f0f0" : "none" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                      <span style={{ fontSize: 11, color: "#aaa" }}>{a.created_at}</span>
                      <span style={{ fontSize: 14, fontWeight: 700, color }}>{a.score}/{a.max}</span>
                    </div>
                    <div style={{ height: 5, background: "#eee", borderRadius: 3, overflow: "hidden" }}>
                      <div style={{ width: pct + "%", height: "100%", background: color, borderRadius: 3 }} />
                    </div>
                    <div style={{ fontSize: 12, color: "#888", marginTop: 4, fontStyle: "italic" }}>
                      {a.feedback?.verdict}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Форма ввода */}
      {!result && (
        <div className="card" style={{ marginBottom: 12 }}>
          <div className="field-label" style={{ marginBottom: 8 }}>✍️ Твой промпт</div>
          <textarea className="input" value={promptText} onChange={e => setPromptText(e.target.value)}
            rows={7} placeholder="Напиши промпт для этого сценария..."
            style={{ resize: "vertical", fontFamily: "inherit", fontSize: 14 }} disabled={submitting} />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
            <span style={{ fontSize: 11, color: "#aaa" }}>{promptText.length} символов</span>
            {error && <span className="error-text" style={{ fontSize: 12 }}>{error}</span>}
          </div>
          <button className="btn btn-primary btn-full" style={{ marginTop: 10 }}
            onClick={handleEvaluate} disabled={submitting || promptText.trim().length < 10}>
            {submitting ? "⏳ Оцениваю..." : "🎯 Оценить промпт"}
          </button>
        </div>
      )}

      {/* Результат */}
      {result && (
        <div className="card" style={{ marginBottom: 12 }}>
          <ScoreDisplay score={result.score} maxScore={result.max} criteria={result.criteria} feedback={result.feedback} />

          {/* Ответ AI на промпт */}
          <div style={{ marginTop: 14, borderTop: "1px solid #f0f0f0", paddingTop: 12 }}>
            {!aiResponse ? (
              <button className="btn btn-full" style={{ fontSize: 13 }}
                onClick={handleRunPrompt} disabled={loadingResponse}>
                {loadingResponse ? "⏳ AI отвечает на твой промпт..." : "▶ Получить ответ AI на промпт"}
              </button>
            ) : (
              <>
                <div style={{ fontSize: 12, fontWeight: 700, color: "#2a9d8f", marginBottom: 6 }}>▶ Ответ AI на твой промпт</div>
                <div style={{
                  background: "#f0faf8", borderRadius: 8, padding: "10px 12px",
                  fontSize: 13, lineHeight: 1.7, whiteSpace: "pre-wrap", color: "#333",
                  maxHeight: 300, overflowY: "auto",
                }}>
                  {aiResponse}
                </div>
              </>
            )}
          </div>

          {/* Эталонный промпт */}
          <div style={{ marginTop: 10, borderTop: "1px solid #f0f0f0", paddingTop: 10 }}>
            <button className="btn btn-full" style={{ fontSize: 13 }}
              onClick={handleIdeal} disabled={loadingIdeal}>
              {loadingIdeal ? "⏳ Генерирую эталон..." : showIdeal ? "▲ Скрыть эталонный промпт" : "🔮 Показать эталонный промпт"}
            </button>
            {showIdeal && idealPrompt && (
              <div style={{ marginTop: 8 }}>
                <div style={{
                  background: "#f5f3ff", borderRadius: 8, padding: "10px 12px",
                  fontSize: 13, lineHeight: 1.6, whiteSpace: "pre-wrap", color: "#444",
                }}>
                  {idealPrompt}
                </div>
                <div style={{ fontSize: 11, color: "#aaa", marginTop: 6 }}>
                  Сравни со своим — что можно было добавить?
                </div>
              </div>
            )}
          </div>

          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button className="btn" style={{ flex: 1, fontSize: 13 }}
              onClick={() => { setResult(null); setIdealPrompt(null); }}>
              ✏️ Ещё раз
            </button>
            <button className="btn" style={{ flex: 1, fontSize: 13 }} onClick={reset}>
              🔄 Другая тема
            </button>
          </div>
        </div>
      )}
    </>
  );
}

/* ─── Общие компоненты ────────────────────────────────────── */
function ScoreDisplay({ score, maxScore, criteria, feedback }) {
  const pct = Math.round((score / maxScore) * 100);
  const color = pct >= 80 ? "#2a9d8f" : pct >= 50 ? "#e9c46a" : "#e76f51";

  return (
    <>
      <div style={{ textAlign: "center", marginBottom: 16 }}>
        <div style={{ fontSize: 48, fontWeight: 800, color, lineHeight: 1 }}>{score}</div>
        <div style={{ fontSize: 13, color: "#888" }}>из {maxScore} баллов · {pct}%</div>
        {feedback?.verdict && (
          <div style={{
            marginTop: 8, fontSize: 14, fontWeight: 600,
            background: color + "18", color, padding: "6px 12px",
            borderRadius: 20, display: "inline-block"
          }}>{feedback.verdict}</div>
        )}
      </div>

      {feedback?.scores && criteria?.map(c => {
        const got = feedback.scores[c.name] ?? 0;
        const pctC = Math.round((got / c.max) * 100);
        return (
          <div key={c.name} style={{ marginBottom: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 3 }}>
              <span>{c.name}</span>
              <span style={{ fontWeight: 600 }}>{got}/{c.max}</span>
            </div>
            <div style={{ height: 6, background: "#eee", borderRadius: 3, overflow: "hidden" }}>
              <div style={{
                width: pctC + "%", height: "100%", borderRadius: 3,
                background: pctC >= 80 ? "#2a9d8f" : pctC >= 50 ? "#e9c46a" : "#e76f51",
                transition: "width 0.6s ease",
              }} />
            </div>
          </div>
        );
      })}

      {feedback?.strengths && (
        <div style={{ marginTop: 12, padding: "10px 12px", background: "#f0faf8", borderRadius: 8 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#2a9d8f", marginBottom: 4 }}>✅ Что хорошо</div>
          <div style={{ fontSize: 13 }}>{feedback.strengths}</div>
        </div>
      )}
      {feedback?.improvements && (
        <div style={{ marginTop: 8, padding: "10px 12px", background: "#fff8f0", borderRadius: 8 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#e9a84c", marginBottom: 4 }}>💡 Как улучшить</div>
          <div style={{ fontSize: 13 }}>{feedback.improvements}</div>
        </div>
      )}
    </>
  );
}

function ScoreBar({ score, max }) {
  const pct = Math.round((score / max) * 100);
  const color = pct >= 80 ? "#2a9d8f" : pct >= 50 ? "#e9c46a" : "#e76f51";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ width: 60, height: 6, background: "#eee", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: pct + "%", height: "100%", background: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 13, fontWeight: 700, color, minWidth: 28 }}>{score}</span>
    </div>
  );
}

function rankEmoji(rank) {
  if (rank === 1) return "🥇";
  if (rank === 2) return "🥈";
  if (rank === 3) return "🥉";
  return `${rank}.`;
}

function rankColor(rank) {
  if (rank === 1) return "#f4a261";
  if (rank === 2) return "#aaa";
  if (rank === 3) return "#cd7f32";
  return "#555";
}