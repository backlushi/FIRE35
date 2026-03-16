import { useState, useEffect, useRef, useCallback } from "react";
import api from "../api";

const AVATAR_COLORS = [
  "#FF6B6B","#4ECDC4","#45B7D1","#FFA07A",
  "#98D8C8","#7B68EE","#FFB347","#87CEEB",
];
function pidColor(pid) {
  const n = parseInt((pid || "P-0").replace(/\D/g, ""), 10) || 0;
  return AVATAR_COLORS[n % AVATAR_COLORS.length];
}

export default function ChatPage({ pid, onBack }) {
  const [data, setData]       = useState(null);
  const [text, setText]       = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const bottomRef = useRef(null);
  const pollRef   = useRef(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const res = await api.get(`/chats/${pid}`);
      setData(res.data);
    } catch {}
    if (!silent) setLoading(false);
  }, [pid]);

  useEffect(() => {
    load();
    pollRef.current = setInterval(() => load(true), 5000);
    return () => clearInterval(pollRef.current);
  }, [load]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [data?.messages?.length]);

  async function sendMsg() {
    if (!text.trim() || sending) return;
    const content = text.trim();
    setText("");
    setSending(true);
    try {
      const res = await api.post(`/chats/${pid}`, { content });
      setData(d => d ? { ...d, messages: [...d.messages, res.data] } : d);
    } catch {}
    setSending(false);
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMsg();
    }
  }

  const partner = data?.partner;
  const messages = data?.messages || [];
  const initial = (partner?.first_name || "?")[0].toUpperCase();

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "#f5f5f5" }}>

      {/* ── Шапка ── */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "12px 16px", background: "#fff",
        borderBottom: "1px solid #eee", flexShrink: 0,
      }}>
        <button onClick={onBack} className="back-btn" style={{ marginRight: 4 }}>← Назад</button>
        {partner && (
          <>
            <div style={{
              width: 36, height: 36, borderRadius: "50%",
              background: pidColor(partner.pid), color: "#fff",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 15, fontWeight: 700, flexShrink: 0,
            }}>
              {initial}
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, lineHeight: 1.2 }}>
                {partner.first_name} {partner.last_name}
              </div>
              {partner.telegram_username && (
                <div style={{ fontSize: 11, color: "#2a9d8f" }}>@{partner.telegram_username}</div>
              )}
            </div>
          </>
        )}
      </div>

      {/* ── Сообщения ── */}
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 12px 4px" }}>
        {loading && (
          <div style={{ textAlign: "center", color: "#aaa", marginTop: 40, fontSize: 14 }}>Загрузка...</div>
        )}
        {!loading && messages.length === 0 && (
          <div style={{ textAlign: "center", color: "#bbb", marginTop: 40, fontSize: 13 }}>
            Начните диалог — напишите первое сообщение
          </div>
        )}

        {messages.map((m, i) => {
          const prevDate = i > 0 ? messages[i - 1].date : null;
          const showDate = m.date !== prevDate;
          return (
            <div key={m.id}>
              {showDate && (
                <div style={{ textAlign: "center", margin: "10px 0 6px", fontSize: 11, color: "#aaa" }}>
                  {m.date}
                </div>
              )}
              <div style={{
                display: "flex",
                justifyContent: m.mine ? "flex-end" : "flex-start",
                marginBottom: 4,
              }}>
                <div style={{
                  maxWidth: "75%",
                  background: m.mine ? "#2a9d8f" : "#fff",
                  color: m.mine ? "#fff" : "#222",
                  borderRadius: m.mine ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
                  padding: "8px 12px",
                  fontSize: 14, lineHeight: 1.5,
                  boxShadow: "0 1px 2px rgba(0,0,0,0.08)",
                  wordBreak: "break-word",
                  whiteSpace: "pre-wrap",
                }}>
                  {m.content}
                  <div style={{
                    fontSize: 10, marginTop: 2, textAlign: "right",
                    color: m.mine ? "rgba(255,255,255,0.7)" : "#bbb",
                    display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 2,
                  }}>
                    {m.time}
                    {m.mine && (
                      <span style={{ color: m.read ? "#a8e6cf" : "rgba(255,255,255,0.5)", fontSize: 10, letterSpacing: -1 }}>
                        {m.read ? "✓✓" : "✓"}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      {/* ── Ввод ── */}
      <div style={{
        display: "flex", gap: 8, padding: "10px 12px",
        background: "#fff", borderTop: "1px solid #eee", flexShrink: 0,
      }}>
        <textarea
          className="input"
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Написать сообщение..."
          rows={1}
          style={{
            flex: 1, resize: "none", fontFamily: "inherit",
            fontSize: 14, margin: 0, padding: "8px 12px",
            maxHeight: 100, overflowY: "auto",
          }}
          disabled={sending}
        />
        <button
          onClick={sendMsg}
          disabled={sending || !text.trim()}
          style={{
            background: "#2a9d8f", border: "none", color: "#fff",
            borderRadius: 20, width: 40, height: 40, cursor: "pointer",
            fontSize: 18, flexShrink: 0, alignSelf: "flex-end",
            opacity: (!text.trim() || sending) ? 0.5 : 1,
          }}
        >
          ➤
        </button>
      </div>
    </div>
  );
}
