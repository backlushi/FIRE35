import { useState } from "react";
import api from "../api";

const GREETING = `Вокруг тебя столько шума по поводу AI — и это только начало. Те, кто умеет с ним работать, уже зарабатывают на 30–50% больше.

Проверим: насколько легко ты адаптируешься к изменениям, которые уже идут?

Сможем ли мы заполнить твой профиль с одного сообщения — того, что сейчас называют промптом?

Напиши о себе: кто ты, чем занимаешься, что умеешь и чего хочешь достичь в клубе FIRE35.`;

export default function OnboardingScreen({ onDone }) {
  const [phase, setPhase]     = useState("intro");   // "intro" | "input" | "result"
  const [text, setText]       = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult]   = useState(null);
  const [error, setError]     = useState(null);

  async function handleEvaluate() {
    if (text.trim().length < 10) {
      setError("Напиши хотя бы пару предложений о себе");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.post("/onboarding/evaluate", { prompt_text: text });
      setResult(res.data);
      setPhase("result");
    } catch (e) {
      setError(e.response?.data?.detail || "Ошибка AI-оценки. Попробуй ещё раз.");
    }
    setLoading(false);
  }

  async function handleSkip() {
    await api.post("/onboarding/skip").catch(() => {});
    onDone();
  }

  // ── Интро-экран ──
  if (phase === "intro") {
    return (
      <div className="splash" style={{ padding: "24px 20px", justifyContent: "flex-start", paddingTop: 40 }}>
        <div style={{ fontSize: 40, marginBottom: 16 }}>🤖</div>
        <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 16, lineHeight: 1.3, textAlign: "center" }}>
          Добрый день!
        </h2>
        <div style={{
          fontSize: 15, lineHeight: 1.7, color: "#444", whiteSpace: "pre-line",
          textAlign: "left", background: "#f8f8f8", borderRadius: 12,
          padding: "16px 18px", marginBottom: 24,
        }}>
          {GREETING}
        </div>
        <button
          className="btn btn-primary btn-full"
          onClick={() => setPhase("input")}
          style={{ marginBottom: 12 }}
        >
          Попробовать →
        </button>
        <button
          className="btn btn-full"
          onClick={handleSkip}
          style={{ color: "#aaa", fontSize: 13 }}
        >
          Пропустить
        </button>
      </div>
    );
  }

  // ── Ввод промпта ──
  if (phase === "input") {
    return (
      <div className="splash" style={{ padding: "24px 20px", justifyContent: "flex-start", paddingTop: 32 }}>
        <div style={{ fontSize: 32, marginBottom: 12 }}>✍️</div>
        <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>Расскажи о себе</h2>
        <p style={{ fontSize: 14, color: "#666", marginBottom: 16, lineHeight: 1.5 }}>
          Напиши одно-два предложения: кто ты, чем занимаешься, что умеешь и зачем пришёл в клуб.
        </p>
        <textarea
          className="input"
          value={text}
          onChange={e => setText(e.target.value)}
          rows={6}
          placeholder="Например: Меня зовут Алина, я SMM-менеджер. Умею создавать контент и работать с аналитикой. Хочу выйти на пассивный доход через 7 лет и научиться инвестировать."
          style={{ resize: "none", fontFamily: "inherit", fontSize: 14, marginBottom: 8 }}
          disabled={loading}
          autoFocus
        />
        {error && <p className="error-text" style={{ fontSize: 13, marginBottom: 8 }}>{error}</p>}
        <button
          className="btn btn-primary btn-full"
          onClick={handleEvaluate}
          disabled={loading || text.trim().length < 10}
          style={{ marginBottom: 10 }}
        >
          {loading ? "⏳ Анализирую..." : "🚀 Оценить мой промпт"}
        </button>
        <button className="btn btn-full" onClick={handleSkip} style={{ color: "#aaa", fontSize: 13 }}>
          Пропустить
        </button>
      </div>
    );
  }

  // ── Результат ──
  if (phase === "result" && result) {
    const score = result.score;
    const color = score >= 75 ? "#2a9d8f" : score >= 45 ? "#e9c46a" : "#e76f51";
    const emoji = score >= 75 ? "🌟" : score >= 45 ? "👍" : "💪";

    return (
      <div className="splash" style={{ padding: "24px 20px", justifyContent: "flex-start", paddingTop: 32 }}>
        <div style={{ fontSize: 40, marginBottom: 8 }}>{emoji}</div>

        {/* Большой скор */}
        <div style={{ textAlign: "center", marginBottom: 20 }}>
          <div style={{ fontSize: 72, fontWeight: 900, color, lineHeight: 1 }}>{score}</div>
          <div style={{ fontSize: 14, color: "#888", marginBottom: 10 }}>из 100 баллов</div>
          <div style={{
            display: "inline-block", background: color + "18", color,
            padding: "6px 16px", borderRadius: 20, fontSize: 14, fontWeight: 600,
          }}>
            {result.verdict}
          </div>
        </div>

        {/* Шкала */}
        <div style={{ width: "100%", height: 8, background: "#eee", borderRadius: 4, marginBottom: 20, overflow: "hidden" }}>
          <div style={{
            width: score + "%", height: "100%", background: color, borderRadius: 4,
            transition: "width 1s ease",
          }} />
        </div>

        {/* Рекомендация */}
        {result.recommendation && (
          <div style={{
            background: "#fff8f0", borderRadius: 10, padding: "12px 14px",
            marginBottom: 16, fontSize: 14, lineHeight: 1.6,
          }}>
            <div style={{ fontWeight: 700, color: "#e9a84c", marginBottom: 4 }}>💡 Совет</div>
            {result.recommendation}
          </div>
        )}

        {/* Что извлекли */}
        {result.extracted && (
          <div style={{
            background: "#f0faf8", borderRadius: 10, padding: "12px 14px",
            marginBottom: 20, fontSize: 13,
          }}>
            <div style={{ fontWeight: 700, color: "#2a9d8f", marginBottom: 8 }}>✅ Заполнено в профиле</div>
            {result.extracted.first_name && <div>👤 Имя: <strong>{result.extracted.first_name}</strong></div>}
            {result.extracted.profession && <div>💼 Профессия: <strong>{result.extracted.profession}</strong></div>}
            {result.extracted.skills?.length > 0 && (
              <div>🎯 Навыки: <strong>{result.extracted.skills.join(", ")}</strong></div>
            )}
            {result.extracted.goal && <div>🎯 Цель: <strong>{result.extracted.goal}</strong></div>}
          </div>
        )}

        {/* Напоминание про тренажёр */}
        <div style={{
          background: "linear-gradient(135deg, #667eea18, #764ba218)",
          border: "1.5px solid #667eea33",
          borderRadius: 12, padding: "14px 16px", marginBottom: 16,
        }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#6c5ce7", marginBottom: 4 }}>
            🤖 Хочешь улучшить результат?
          </div>
          <div style={{ fontSize: 13, color: "#555", lineHeight: 1.6 }}>
            В разделе <strong>Игры → AI-Тренажёр</strong> ты можешь тренировать промпты на 5 темах — и смотреть как растёт твой скор.
          </div>
        </div>

        <button
          className="btn btn-primary btn-full"
          onClick={onDone}
          style={{ marginBottom: 8 }}
        >
          Войти в клуб →
        </button>
      </div>
    );
  }

  return null;
}