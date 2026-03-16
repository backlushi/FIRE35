import { useState, useEffect, useRef } from "react";
import api from "../api";

export default function DirectoryPage({ user }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [sending, setSending] = useState({});
  const [sentMsg, setSentMsg] = useState({});
  const timer = useRef(null);

  useEffect(() => {
    load("");
  }, []);

  function onSearch(val) {
    setSearch(val);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => load(val), 400);
  }

  async function load(q) {
    setLoading(true);
    try {
      const res = await api.get("/directory", {
        params: { search: q || undefined, month: "2026-02" },
      });
      setItems(res.data);
    } catch {
      setItems([]);
    }
    setLoading(false);
  }

  async function sendContact(pid) {
    setSending(s => ({ ...s, [pid]: true }));
    try {
      const res = await api.post(`/contact-request/${pid}`);
      setSentMsg(m => ({ ...m, [pid]: res.data.status === "already_sent" ? "Уже отправлено" : "Запрос отправлен!" }));
    } catch (e) {
      setSentMsg(m => ({ ...m, [pid]: e.response?.data?.detail || "Ошибка" }));
    }
    setSending(s => ({ ...s, [pid]: false }));
  }

  const allMembers = items.flatMap(g => g.members);

  return (
    <div className="page">
      <h1 className="page-title">Участники</h1>

      <div className="card">
        <input
          className="input"
          placeholder="Поиск по профессии..."
          value={search}
          onChange={e => onSearch(e.target.value)}
        />
      </div>

      {loading && <div className="center-text">Загрузка...</div>}

      {!loading && allMembers.map(m => (
        <div key={m.pid} className="card member-card">
          <div className="member-top">
            <div className="avatar sm">{(m.first_name || m.pid || "?")[0].toUpperCase()}</div>
            <div>
              <p className="member-pid">
                {m.pid} {m.first_name ? `· ${m.first_name}` : ""}
                {m.answer_score > 0 && (
                  <span className="member-score">⭐ {m.answer_score}</span>
                )}
              </p>
              <p className="member-prof">{m.profession}</p>
              <p className="tg-hidden">🔒 Username скрыт — по запросу</p>
            </div>
            {m.savings_pct != null && (
              <span className="member-pct">{m.savings_pct.toFixed(0)}%</span>
            )}
          </div>
          {m.skills && m.skills !== "—" && (
            <p className="member-skills">{m.skills}</p>
          )}
          {m.pid !== user?.pid && (
            <div style={{ marginTop: 8 }}>
              {sentMsg[m.pid] ? (
                <span className="msg">{sentMsg[m.pid]}</span>
              ) : (
                <button
                  className="btn btn-sm"
                  onClick={() => sendContact(m.pid)}
                  disabled={sending[m.pid]}
                >
                  {sending[m.pid] ? "..." : "Познакомиться"}
                </button>
              )}
            </div>
          )}
        </div>
      ))}

      {!loading && allMembers.length === 0 && (
        <div className="card center-text">Никого не найдено</div>
      )}
    </div>
  );
}
