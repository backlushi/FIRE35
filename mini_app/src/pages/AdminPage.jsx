import { useState, useEffect } from "react";
import api from "../api";

const MONTHS = [
  { value: "2026-03", label: "Март 2026" },
  { value: "2026-02", label: "Февраль 2026" },
  { value: "2026-01", label: "Январь 2026" },
];

const SECTIONS = [
  { id: "members",         label: "Участники" },
  { id: "questions",       label: "Вопросы" },
  { id: "experts",         label: "Эксперты" },
  { id: "duplicates",      label: "Дубл." },
  { id: "recommendations", label: "Рекоменд." },
  { id: "analytics",       label: "Аналитика" },
  { id: "broadcast",       label: "Рассылка" },
];

export default function AdminPage() {
  const [section, setSection] = useState("members");

  return (
    <div className="page">
      <h1 className="page-title">⚙️ Администратор</h1>

      <div className="admin-section-tabs">
        {SECTIONS.map(s => (
          <button
            key={s.id}
            className={"admin-sec-btn" + (section === s.id ? " active" : "")}
            onClick={() => setSection(s.id)}
          >
            {s.label}
          </button>
        ))}
      </div>

      {section === "members"         && <MembersSection />}
      {section === "questions"       && <QuestionsSection />}
      {section === "experts"         && <ExpertsSection />}
      {section === "duplicates"      && <DuplicatesSection />}
      {section === "recommendations" && <RecommendationsSection />}
      {section === "analytics"       && <AnalyticsSection />}
      {section === "broadcast"       && <BroadcastSection />}
    </div>
  );
}

// ── Участники ─────────────────────────────────────────────
function MembersSection() {
  const [filter, setFilter] = useState("all");
  const [month, setMonth] = useState("2026-02");
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [confirmPid, setConfirmPid] = useState(null);

  useEffect(() => { load(); }, [filter, month]);

  async function load() {
    setLoading(true);
    try {
      const res = await api.get(`/admin/members?filter=${filter}&month=${month}`);
      setMembers(res.data);
    } catch {}
    setLoading(false);
  }

  async function deleteMember(pid) {
    try {
      await api.delete(`/admin/members/${pid}`);
      setConfirmPid(null);
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Ошибка удаления");
    }
  }

  return (
    <div>
      <div className="card">
        <div className="admin-filters">
          <select className="input" value={filter} onChange={e => setFilter(e.target.value)}>
            <option value="all">Все участники</option>
            <option value="has_report">Сдали отчёт</option>
            <option value="no_report">Не сдали отчёт</option>
            <option value="no_telegram">Нет Telegram</option>
          </select>
          <select className="input" value={month} onChange={e => setMonth(e.target.value)}>
            {MONTHS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </div>
        <p className="hint-text" style={{ marginTop: 6 }}>{members.length} участников</p>
      </div>

      {loading && <div className="card center-text">Загрузка...</div>}

      {confirmPid && (
        <div className="card" style={{ background: "#fef2f2", border: "1px solid #fca5a5" }}>
          <p style={{ marginBottom: 10, fontWeight: 600 }}>Удалить {confirmPid}?</p>
          <p className="hint-text" style={{ marginBottom: 10 }}>
            Все данные участника (отчёты, вопросы) будут удалены безвозвратно.
          </p>
          <div className="row-gap">
            <button className="btn btn-danger" onClick={() => deleteMember(confirmPid)}>
              Удалить
            </button>
            <button className="btn btn-secondary" onClick={() => setConfirmPid(null)}>
              Отмена
            </button>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 0 }}>
        {members.map(m => (
          <div key={m.pid} className="member-admin-row">
            <div className="member-admin-info">
              <span className="member-admin-pid">{m.pid}</span>
              <span className="member-admin-name">{m.first_name}</span>
              {m.telegram_username && (
                <span className="member-admin-tg">@{m.telegram_username}</span>
              )}
              {m.profession && (
                <span className="member-admin-prof">{m.profession}</span>
              )}
            </div>
            <div className="member-admin-meta">
              {m.has_report
                ? <span className="badge green">{m.savings_pct?.toFixed(1)}%</span>
                : <span className="badge grey">Нет</span>
              }
              <button
                className="btn-icon-delete"
                onClick={() => setConfirmPid(m.pid)}
                title="Удалить"
              >
                🗑
              </button>
            </div>
          </div>
        ))}
        {!loading && members.length === 0 && (
          <p className="center-text" style={{ padding: 16 }}>Нет участников</p>
        )}
      </div>
    </div>
  );
}

// ── Вопросы ───────────────────────────────────────────────
function QuestionsSection() {
  const [questions, setQuestions] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [sending, setSending] = useState({});
  const [tagFilter, setTagFilter] = useState("");

  useEffect(() => { load(); }, [tagFilter]);

  async function load() {
    try {
      const params = tagFilter.trim() ? { tag: tagFilter.trim() } : {};
      const res = await api.get("/admin/questions", { params });
      setQuestions(res.data);
    } catch {}
  }

  async function sendAnswer(qid) {
    const text = drafts[qid]?.trim();
    if (!text) return;
    setSending(s => ({ ...s, [qid]: true }));
    try {
      await api.post(`/admin/questions/${qid}/answer`, { answer: text });
      setDrafts(d => ({ ...d, [qid]: "" }));
      load();
    } catch {}
    setSending(s => ({ ...s, [qid]: false }));
  }

  return (
    <div>
      <div className="card">
        <input
          className="input"
          placeholder="Фильтр по тегу (напр: python, smm)..."
          value={tagFilter}
          onChange={e => setTagFilter(e.target.value)}
        />
        <p className="hint-text" style={{ marginTop: 4 }}>
          {questions.length} вопросов{tagFilter ? ` по тегу «${tagFilter}»` : ""}
        </p>
      </div>

      {questions.length === 0 && (
        <div className="card center-text">Вопросов пока нет</div>
      )}

      {questions.map(q => (
        <div key={q.id} className="card">
          <div className="q-header">
            <span className="q-author">{q.first_name}</span>
            <span className="q-pid">{q.pid}</span>
            <span className="q-time">{q.created_at}</span>
          </div>
          {q.tags?.length > 0 && (
            <div className="q-tags" style={{ marginBottom: 4 }}>
              {q.tags.map(t => (
                <span key={t} className="q-tag">#{t.replace(/_/g, " ")}</span>
              ))}
            </div>
          )}
          <p className="q-text">{q.question}</p>

          {q.answers.map(a => (
            <div key={a.id} className="admin-answer">
              <span className="admin-answer-label">
                {a.expert_username ? `@${a.expert_username}` : "Анар"}
                {a.is_useful === true && <span className="useful-badge" style={{ marginLeft: 4 }}>👍</span>}
              </span>
              <p className="admin-answer-text">{a.answer}</p>
              <span className="q-time">{a.created_at}</span>
            </div>
          ))}

          <textarea
            className="input textarea"
            rows={2}
            placeholder="Написать ответ..."
            value={drafts[q.id] || ""}
            onChange={e => setDrafts(d => ({ ...d, [q.id]: e.target.value }))}
            style={{ marginTop: 8 }}
          />
          <button
            className="btn btn-primary"
            style={{ marginTop: 6 }}
            disabled={!drafts[q.id]?.trim() || sending[q.id]}
            onClick={() => sendAnswer(q.id)}
          >
            {sending[q.id] ? "Отправляю..." : "Ответить →"}
          </button>
        </div>
      ))}
    </div>
  );
}

// ── Дубликаты (статистика) ────────────────────────────────
function DuplicatesSection() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    try {
      const res = await api.get("/admin/duplicates/stats");
      setStats(res.data);
    } catch {}
    setLoading(false);
  }

  return (
    <div>
      <div className="card">
        <p className="field-label">🤖 AI-анти-дубликаты</p>
        <p className="hint-text" style={{ marginTop: 4 }}>
          sentence-transformers автоматически находит похожие вопросы
          и отвечает из базы знаний, не беспокоя экспертов.
        </p>
      </div>

      {loading && <div className="card center-text">Загрузка...</div>}

      {stats && (
        <>
          <div className="stats-row">
            <div className="stat-card">
              <p className="stat-label">Всего вопросов</p>
              <p className="stat-value">{stats.total_questions}</p>
            </div>
            <div className="stat-card">
              <p className="stat-label">Дубликатов</p>
              <p className="stat-value primary">{stats.duplicate_questions}</p>
            </div>
            <div className="stat-card">
              <p className="stat-label">Сэкономлено</p>
              <p className="stat-value" style={{ color: "#10b981" }}>
                {stats.saved_notifications}
              </p>
              <p className="stat-sub">рассылок</p>
            </div>
          </div>

          <div className="card">
            <p className="field-label" style={{ marginBottom: 4 }}>
              Эффективность кэша: <b style={{ color: "#f59e0b" }}>{stats.cache_rate_pct}%</b>
            </p>
            <p className="hint-text">
              Из {stats.duplicate_questions} найденных дубликатов {stats.force_new_count} всё равно отправлены экспертам
            </p>
          </div>

          {stats.top_sources.length > 0 && (
            <div className="card">
              <p className="field-label" style={{ marginBottom: 8 }}>🔁 Часто копируемые вопросы</p>
              {stats.top_sources.map((item, i) => (
                <div key={item.question_id} style={{
                  borderBottom: i < stats.top_sources.length - 1 ? "1px solid #f3f4f6" : "none",
                  padding: "8px 0",
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 8,
                  alignItems: "flex-start",
                }}>
                  <p style={{ margin: 0, fontSize: 13, flex: 1, color: "#374151" }}>
                    {item.question}...
                  </p>
                  <span style={{
                    flexShrink: 0, background: "#eff6ff", color: "#2563eb",
                    fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 10,
                  }}>
                    ×{item.duplicate_count}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Топ экспертов ─────────────────────────────────────────
function ExpertsSection() {
  const [experts, setExperts] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    try {
      const res = await api.get("/admin/experts/top");
      setExperts(res.data);
    } catch {}
    setLoading(false);
  }

  return (
    <div>
      <div className="card">
        <p className="field-label">🏅 Топ-10 экспертов по рейтингу</p>
        <p className="hint-text" style={{ marginTop: 4 }}>
          Участники, чьи ответы чаще всего отмечают полезными
        </p>
      </div>

      {loading && <div className="card center-text">Загрузка...</div>}

      {!loading && experts.length === 0 && (
        <div className="card center-text">Ответов ещё нет</div>
      )}

      {experts.map((e, i) => (
        <div key={e.pid} className="card" style={{ padding: "10px 14px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 20, minWidth: 28 }}>
              {i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : `${i + 1}.`}
            </span>
            <div style={{ flex: 1 }}>
              <p style={{ fontWeight: 600, margin: 0 }}>
                {e.pid}{e.first_name ? ` · ${e.first_name}` : ""}
                {e.telegram_username && (
                  <span style={{ color: "#888", fontWeight: 400, marginLeft: 6 }}>
                    @{e.telegram_username}
                  </span>
                )}
              </p>
              {e.skills.length > 0 && (
                <p style={{ margin: "2px 0 0", fontSize: 12, color: "#666" }}>
                  {e.skills.slice(0, 5).map(s => s.replace(/_/g, " ")).join(", ")}
                </p>
              )}
            </div>
            <div style={{ textAlign: "right" }}>
              <p style={{ margin: 0, fontWeight: 700, color: "#f59e0b" }}>⭐ {e.answer_score}</p>
              <p style={{ margin: 0, fontSize: 11, color: "#888" }}>
                из {e.total_answers} отв.
              </p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Рекомендации ──────────────────────────────────────────
function RecommendationsSection() {
  const [members, setMembers] = useState([]);
  const [selectedPid, setSelectedPid] = useState("");
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.get("/admin/members").then(r => setMembers(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedPid) { setText(""); return; }
    api.get(`/admin/recommendations/${selectedPid}`)
      .then(r => setText(r.data.text || ""))
      .catch(() => setText(""));
  }, [selectedPid]);

  async function save() {
    if (!selectedPid || !text.trim()) return;
    setSaving(true);
    setMsg("");
    try {
      await api.post("/admin/recommendations", { pid: selectedPid, text: text.trim() });
      setMsg("Сохранено и отправлено участнику ✅");
      setTimeout(() => setMsg(""), 4000);
    } catch (e) {
      setMsg("Ошибка: " + (e.response?.data?.detail || e.message));
    }
    setSaving(false);
  }

  return (
    <div className="card">
      <label className="field-label">Участник</label>
      <select
        className="input"
        value={selectedPid}
        onChange={e => setSelectedPid(e.target.value)}
      >
        <option value="">— выбрать участника —</option>
        {members.map(m => (
          <option key={m.pid} value={m.pid}>
            {m.pid}{m.first_name ? ` — ${m.first_name}` : ""}
          </option>
        ))}
      </select>

      {selectedPid && (
        <>
          <label className="field-label" style={{ marginTop: 14 }}>Рекомендация</label>
          <textarea
            className="input textarea"
            rows={5}
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="Персональная рекомендация по финансам, целям, действиям..."
          />
          <button
            className="btn btn-primary btn-full"
            style={{ marginTop: 10 }}
            disabled={!text.trim() || saving}
            onClick={save}
          >
            {saving ? "Сохраняю..." : "💾 Сохранить и уведомить"}
          </button>
          {msg && (
            <p className={msg.startsWith("Ошибка") ? "error-text" : "success-text"}
               style={{ marginTop: 8 }}>
              {msg}
            </p>
          )}
        </>
      )}
    </div>
  );
}

// ── Аналитика ─────────────────────────────────────────────
function AnalyticsSection() {
  const [month, setMonth] = useState("2026-02");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { load(); }, [month]);

  async function load() {
    setLoading(true);
    try {
      const res = await api.get(`/admin/analytics/${month}`);
      setData(res.data);
    } catch {}
    setLoading(false);
  }

  return (
    <div>
      <div className="card">
        <select className="input" value={month} onChange={e => setMonth(e.target.value)}>
          {MONTHS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>
      </div>

      {loading && <div className="card center-text">Загрузка...</div>}

      {data && (
        <>
          <div className="stats-row">
            <div className="stat-card">
              <p className="stat-label">Сдали</p>
              <p className="stat-value">{data.submitted_count}</p>
              <p className="stat-sub">из {data.total_count}</p>
            </div>
            <div className="stat-card">
              <p className="stat-label">Сред. сбереж.</p>
              <p className="stat-value primary">{data.avg_savings_pct}%</p>
            </div>
            <div className="stat-card">
              <p className="stat-label">Сред. инвест.</p>
              <p className="stat-value primary">{data.avg_invest_pct}%</p>
            </div>
          </div>

          <div className="card" style={{ padding: "10px 14px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 22 }}>💬</span>
              <div>
                <p style={{ margin: 0, fontWeight: 600 }}>
                  Ответов сегодня: {data.answers_today}
                </p>
                <p className="hint-text" style={{ margin: 0 }}>
                  экспертные ответы за последние 24 ч
                </p>
              </div>
            </div>
          </div>

          <div className="card">
            <p className="field-label" style={{ marginBottom: 8 }}>🏆 Топ-5</p>
            {data.top5.map((u, i) => (
              <div key={u.pid} className="rating-row">
                <span className="rank">{["🥇", "🥈", "🥉", "4.", "5."][i]}</span>
                <span className="rating-pid">{u.pid}</span>
                <span style={{ flex: 1, color: "#555" }}>{u.first_name}</span>
                <span className="rating-pct">{u.savings_pct.toFixed(1)}%</span>
              </div>
            ))}
            {data.top5.length === 0 && <p className="hint-text">Нет данных</p>}
          </div>

          <div className="card">
            <p className="field-label" style={{ marginBottom: 8 }}>
              ❌ Не сдали отчёт ({data.not_submitted.length})
            </p>
            <div style={{ maxHeight: 280, overflowY: "auto" }}>
              {data.not_submitted.map(u => (
                <div key={u.pid} className="rating-row">
                  <span className="rating-pid" style={{ minWidth: 60 }}>{u.pid}</span>
                  <span style={{ flex: 1, color: "#555", fontSize: 13 }}>{u.first_name}</span>
                  {u.telegram_username && (
                    <span style={{ color: "#888", fontSize: 12 }}>@{u.telegram_username}</span>
                  )}
                </div>
              ))}
              {data.not_submitted.length === 0 && (
                <p className="hint-text">Все сдали — отлично! 🎉</p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ── Рассылка ──────────────────────────────────────────────
function BroadcastSection() {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);

  async function send() {
    if (!text.trim()) return;
    setSending(true);
    setResult(null);
    try {
      const res = await api.post("/admin/broadcast", { message: text.trim() });
      setResult(res.data);
      setText("");
    } catch (e) {
      setResult({ error: e.response?.data?.detail || "Ошибка рассылки" });
    }
    setSending(false);
  }

  return (
    <div className="card">
      <p className="field-label">Сообщение всем участникам</p>
      <p className="hint-text" style={{ marginBottom: 8 }}>
        HTML-теги: &lt;b&gt;жирный&lt;/b&gt;, &lt;i&gt;курсив&lt;/i&gt;
      </p>
      <textarea
        className="input textarea"
        rows={6}
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder="Привет, участники! ..."
      />
      <button
        className="btn btn-primary btn-full"
        style={{ marginTop: 10 }}
        disabled={!text.trim() || sending}
        onClick={send}
      >
        {sending ? "Отправляю..." : "📢 Отправить всем"}
      </button>
      {result && !result.error && (
        <p className="success-text" style={{ marginTop: 10 }}>
          ✅ Отправлено: {result.sent} &nbsp;|&nbsp; Ошибок: {result.failed}
        </p>
      )}
      {result?.error && (
        <p className="error-text" style={{ marginTop: 10 }}>{result.error}</p>
      )}
    </div>
  );
}
