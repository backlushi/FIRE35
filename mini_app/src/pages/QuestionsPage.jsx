import { useState, useEffect } from "react";
import api from "../api";

const STATUS_FILTERS = [
  { id: null,       label: "Все" },
  { id: "unsolved", label: "⏳ Открытые" },
];

const AVATAR_COLORS = [
  "#FF6B6B","#4ECDC4","#45B7D1","#FFA07A",
  "#98D8C8","#7B68EE","#FFB347","#87CEEB",
];
function pidColor(pid) {
  const n = parseInt((pid || "P-0").replace(/\D/g,""), 10) || 0;
  return AVATAR_COLORS[n % AVATAR_COLORS.length];
}
function MiniAvatar({ pid, name }) {
  const initial = (name || pid || "?")[0].toUpperCase();
  return (
    <div style={{
      width: 26, height: 26, borderRadius: "50%", flexShrink: 0,
      background: pidColor(pid), color: "#fff",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: 11, fontWeight: 700,
    }}>{initial}</div>
  );
}

export default function QuestionsPage({ user }) {
  const [questions, setQuestions]   = useState([]);
  const [loading, setLoading]       = useState(false);
  const [filter, setFilter]         = useState(null);
  const [myTopics, setMyTopics]     = useState(false);
  const [expanded, setExpanded]     = useState(null);
  const [answerText, setAnswerText] = useState({});
  const [sending, setSending]       = useState({});
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);

  useEffect(() => { loadQuestions(); }, [filter, myTopics]);

  async function loadQuestions() {
    setLoading(true);
    try {
      const res = await api.get("/questions", {
        params: {
          filter: filter || undefined,
          my_topics: myTopics || undefined,
        },
      });
      setQuestions(res.data);
    } catch {
      setQuestions([]);
    }
    setLoading(false);
  }

  function toggleExpand(id) {
    setExpanded(e => (e === id ? null : id));
  }

  async function submitAnswer(qid) {
    const text = (answerText[qid] || "").trim();
    if (text.length < 10) return;
    setSending(s => ({ ...s, [qid]: true }));
    try {
      const res = await api.post(`/questions/${qid}/answers`, { answer: text });
      setQuestions(qs => qs.map(q =>
        q.id !== qid ? q : { ...q, answers: [...q.answers, res.data] }
      ));
      setAnswerText(a => ({ ...a, [qid]: "" }));
    } catch (e) {
      alert(e.response?.data?.detail || "Ошибка отправки");
    }
    setSending(s => ({ ...s, [qid]: false }));
  }

  async function voteAnswer(answerId, qid, voteVal) {
    try {
      const res = await api.post(`/questions/answers/${answerId}/vote`, { vote: voteVal });
      setQuestions(qs => qs.map(q => {
        if (q.id !== qid) return q;
        return {
          ...q,
          answers: q.answers.map(a =>
            a.id === answerId
              ? { ...a, vote_score: res.data.vote_score, my_vote: res.data.my_vote }
              : a
          ),
        };
      }));
    } catch (e) {
      alert(e.response?.data?.detail || "Ошибка голосования");
    }
  }

  async function acceptAnswer(answerId, qid) {
    try {
      await api.post(`/questions/answers/${answerId}/rate`, { is_useful: true });
      setQuestions(qs => qs.map(q => {
        if (q.id !== qid) return q;
        return {
          ...q,
          answers: q.answers.map(a => ({
            ...a,
            is_useful: a.id === answerId ? true : a.is_useful,
          })),
        };
      }));
    } catch (e) {
      alert(e.response?.data?.detail || "Ошибка");
    }
  }

  async function flagQuestion(qid) {
    try {
      await api.post(`/questions/${qid}/flag`);
      setQuestions(qs => qs.map(q =>
        q.id !== qid ? q : { ...q, flag_count: (q.flag_count || 0) + 1 }
      ));
    } catch (e) {
      alert(e.response?.data?.detail || "Ошибка");
    }
  }

  async function deleteQuestion(qid) {
    try {
      await api.delete(`/questions/${qid}`);
      setQuestions(qs => qs.filter(q => q.id !== qid));
      setExpanded(null);
      setConfirmDeleteId(null);
    } catch (e) {
      setConfirmDeleteId(null);
    }
  }

  return (
    <div className="page">
      <h1 className="page-title">Вопросы клуба</h1>

      {/* Главные вкладки: Все / По моим навыкам */}
      <div className="q-filter-bar" style={{ marginBottom: 8 }}>
        <button
          className={"q-filter-btn" + (!myTopics ? " active" : "")}
          onClick={() => { setMyTopics(false); }}
        >
          🤔 Все
        </button>
        <button
          className={"q-filter-btn" + (myTopics ? " active" : "")}
          onClick={() => { setMyTopics(true); setFilter(null); }}
        >
          🎯 По моим навыкам
        </button>
      </div>

      {/* Подфильтр статуса */}
      <div className="q-filter-bar" style={{ marginBottom: 4 }}>
        {STATUS_FILTERS.map(f => (
          <button
            key={String(f.id)}
            className={"q-filter-btn" + (filter === f.id ? " active" : "")}
            style={{ fontSize: 12 }}
            onClick={() => { setFilter(f.id); }}
          >
            {f.label}
          </button>
        ))}
      </div>


      {loading && <div className="center-text">Загрузка...</div>}

      <div className="q-list">
        {questions.map(q => {
          const isOpen    = expanded === q.id;
          const isAuthor  = q.is_me;
          const hasUseful = q.answers.some(a => a.is_useful);
          const flagged   = (q.flag_count || 0) >= 3;

          return (
            <div
              key={q.id}
              className={"q-card" + (isOpen ? " q-card-open" : "") + (flagged ? " q-card-flagged" : "")}
            >
              {/* Заголовок */}
              <div className="q-card-header" onClick={() => toggleExpand(q.id)}>
                <div className="q-card-top">
                  <MiniAvatar pid={q.pid} name={q.first_name} />
                  <span className="q-author">{q.first_name}</span>
                  {q.answer_score > 0 && (
                    <span className="badge-score-sm">⭐{q.answer_score}</span>
                  )}
                  <span className="q-date">{q.created_at}</span>
                  {flagged && <span className="q-flag-badge" title="Отмечен участниками">⚠️</span>}
                  {isAuthor && confirmDeleteId !== q.id && (
                    <button
                      className="btn-delete-q"
                      title="Удалить вопрос"
                      onClick={e => { e.stopPropagation(); setConfirmDeleteId(q.id); }}
                    >🗑</button>
                  )}
                  {isAuthor && confirmDeleteId === q.id && (
                    <span onClick={e => e.stopPropagation()} style={{ display: "flex", gap: 4, alignItems: "center" }}>
                      <span style={{ fontSize: 11, color: "#e76f51" }}>Удалить?</span>
                      <button onClick={e => { e.stopPropagation(); deleteQuestion(q.id); }}
                        style={{ background: "#e76f51", border: "none", color: "#fff", borderRadius: 5, fontSize: 11, padding: "2px 6px", cursor: "pointer" }}>Да</button>
                      <button onClick={e => { e.stopPropagation(); setConfirmDeleteId(null); }}
                        style={{ background: "#eee", border: "none", color: "#555", borderRadius: 5, fontSize: 11, padding: "2px 6px", cursor: "pointer" }}>Нет</button>
                    </span>
                  )}
                </div>
                <div className="q-text">
                  {hasUseful && <span className="q-solved-badge">✅</span>}
                  {q.question}
                </div>
                {q.tags && q.tags.length > 0 && (
                  <div className="q-tags">
                    {q.tags.map(t => (
                      <span key={t} className="q-tag">{t}</span>
                    ))}
                  </div>
                )}
              </div>

              {/* Ответы */}
              {isOpen && (
                <div className="q-answers">
                  {q.answers.length === 0 && (
                    <p className="q-no-answers">Пока нет ответов — будьте первым!</p>
                  )}
                  {q.answers.map(a => (
                    <div key={a.id} className={"q-answer" + (a.is_useful ? " q-answer-useful" : "")}>
                      <div className="q-answer-meta">
                        <MiniAvatar pid={a.expert_pid} name={a.expert_name} />
                        <span className="q-answer-author">
                          {a.expert_name || "Анар"}
                          {a.expert_score > 0 && (
                            <span className="badge-score-sm">⭐{a.expert_score}</span>
                          )}
                        </span>
                        <span className="q-answer-time">{a.created_at}</span>
                        {a.is_useful && <span className="q-useful-mark">✅ принят</span>}
                      </div>
                      <div className="q-answer-text">{a.answer}</div>
                      <div className="q-answer-actions">
                        <button
                          className={"q-vote-btn" + (a.my_vote === 1 ? " active" : "")}
                          onClick={() => voteAnswer(a.id, q.id, 1)}
                        >👍 {a.vote_score > 0 ? a.vote_score : ""}</button>
                        <button
                          className={"q-vote-btn" + (a.my_vote === -1 ? " active" : "")}
                          onClick={() => voteAnswer(a.id, q.id, -1)}
                        >👎</button>
                        {isAuthor && !a.is_useful && (
                          <button
                            className="q-vote-btn q-accept-btn"
                            onClick={() => acceptAnswer(a.id, q.id)}
                          >✅ принять</button>
                        )}
                      </div>
                    </div>
                  ))}

                  {/* Форма ответа */}
                  {!isAuthor && (
                    <div className="q-reply-form">
                      <textarea
                        className="input q-reply-input"
                        value={answerText[q.id] || ""}
                        onChange={e => setAnswerText(a => ({ ...a, [q.id]: e.target.value }))}
                        placeholder="Напишите ответ..."
                        rows={3}
                      />
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={() => submitAnswer(q.id)}
                        disabled={sending[q.id] || (answerText[q.id] || "").trim().length < 10}
                      >
                        {sending[q.id] ? "..." : "Ответить"}
                      </button>
                    </div>
                  )}

                  {/* Пожаловаться */}
                  {!isAuthor && (
                    <button
                      className="q-flag-btn"
                      onClick={() => flagQuestion(q.id)}
                    >
                      ⚑ пожаловаться
                    </button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Форма нового вопроса */}
      <NewQuestionForm onAdded={q => setQuestions(qs => [q, ...qs])} />
    </div>
  );
}

function NewQuestionForm({ onAdded }) {
  const [open, setOpen]     = useState(false);
  const [text, setText]     = useState("");
  const [tags, setTags]     = useState("");
  const [sending, setSending] = useState(false);

  async function submit() {
    if (text.trim().length < 10) return;
    setSending(true);
    try {
      const res = await api.post("/questions", {
        question: text.trim(),
        tags: tags.trim() || undefined,
      });
      onAdded(res.data);
      setText(""); setTags(""); setOpen(false);
    } catch (e) {
      alert(e.response?.data?.detail || "Ошибка");
    }
    setSending(false);
  }

  return (
    <div className="new-q-wrap">
      {!open ? (
        <button className="btn btn-primary btn-full" onClick={() => setOpen(true)}>
          + Задать вопрос
        </button>
      ) : (
        <div className="card new-q-form">
          <textarea
            className="input"
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="Ваш вопрос..."
            rows={4}
          />
          <input
            className="input"
            value={tags}
            onChange={e => setTags(e.target.value)}
            placeholder="Теги через запятую (необязательно)"
            style={{ marginTop: 8 }}
          />
          <div style={{ display:"flex", gap:8, marginTop:8 }}>
            <button
              className="btn btn-primary"
              style={{ flex:1 }}
              onClick={submit}
              disabled={sending || text.trim().length < 10}
            >
              {sending ? "..." : "Отправить"}
            </button>
            <button className="btn" onClick={() => setOpen(false)}>Отмена</button>
          </div>
        </div>
      )}
    </div>
  );
}
