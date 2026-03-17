import { useState, useEffect, useRef, useCallback } from "react";
import api from "../api";
import RecoPage from "./RecoPage";
import SmartAvatar from "../components/SmartAvatar";

const AVATAR_COLORS = [
  "#FF6B6B","#4ECDC4","#45B7D1","#FFA07A",
  "#98D8C8","#7B68EE","#FFB347","#87CEEB",
  "#DDA0DD","#90EE90","#F0A500","#20B2AA",
];
function pidColor(pid) {
  const n = parseInt((pid || "P-0").replace(/\D/g,""), 10) || 0;
  return AVATAR_COLORS[n % AVATAR_COLORS.length];
}

// ── Компонент чата встроенный (без шапки с кнопкой назад) ──
function InlineChat({ pid, myPid }) {
  const [data, setData]       = useState(null);
  const [text, setText]       = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);
  const pollRef   = useRef(null);

  const load = useCallback(async (silent = false) => {
    try {
      const res = await api.get(`/chats/${pid}`);
      setData(res.data);
    } catch {}
  }, [pid]);

  useEffect(() => {
    setData(null);
    setText("");
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
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMsg(); }
  }

  const messages = data?.messages || [];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Сообщения */}
      <div style={{ flex: 1, overflowY: "auto", padding: "8px 8px 4px" }}>
        {!data && (
          <div style={{ textAlign: "center", color: "#aaa", marginTop: 24, fontSize: 13 }}>
            Загрузка...
          </div>
        )}
        {data && messages.length === 0 && (
          <div style={{ textAlign: "center", color: "#bbb", marginTop: 24, fontSize: 12 }}>
            Напишите первое сообщение
          </div>
        )}
        {messages.map((m, i) => {
          const prevDate = i > 0 ? messages[i-1].date : null;
          return (
            <div key={m.id}>
              {m.date !== prevDate && (
                <div style={{ textAlign: "center", margin: "6px 0 4px", fontSize: 10, color: "#aaa" }}>
                  {m.date}
                </div>
              )}
              <div style={{ display: "flex", justifyContent: m.mine ? "flex-end" : "flex-start", marginBottom: 3 }}>
                <div style={{
                  maxWidth: "85%",
                  background: m.mine ? "#2a9d8f" : "#fff",
                  color: m.mine ? "#fff" : "#222",
                  borderRadius: m.mine ? "14px 14px 3px 14px" : "14px 14px 14px 3px",
                  padding: "6px 10px",
                  fontSize: 13, lineHeight: 1.4,
                  boxShadow: "0 1px 2px rgba(0,0,0,0.07)",
                  wordBreak: "break-word", whiteSpace: "pre-wrap",
                }}>
                  {m.content}
                  <div style={{
                    fontSize: 9, marginTop: 2, textAlign: "right",
                    color: m.mine ? "rgba(255,255,255,0.65)" : "#bbb",
                    display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 2,
                  }}>
                    {m.time}
                    {m.mine && (
                      <span style={{ color: m.read ? "#a8e6cf" : "rgba(255,255,255,0.45)", letterSpacing: -1 }}>
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

      {/* Ввод */}
      <div style={{
        display: "flex", gap: 6, padding: "6px 8px",
        background: "#fff", borderTop: "1px solid #eee", flexShrink: 0,
      }}>
        <textarea
          className="input"
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Сообщение..."
          rows={1}
          style={{
            flex: 1, resize: "none", fontFamily: "inherit",
            fontSize: 13, margin: 0, padding: "6px 10px",
            maxHeight: 80, overflowY: "auto",
          }}
          disabled={sending}
        />
        <button
          onClick={sendMsg}
          disabled={sending || !text.trim()}
          style={{
            background: "#2a9d8f", border: "none", color: "#fff",
            borderRadius: "50%", width: 34, height: 34,
            cursor: "pointer", fontSize: 15, flexShrink: 0,
            alignSelf: "flex-end",
            opacity: (!text.trim() || sending) ? 0.5 : 1,
          }}
        >➤</button>
      </div>
    </div>
  );
}

// ── Главный компонент: split-layout ──
export default function ChatsPage({ user, onOpenDetail }) {
  const [chats, setChats]       = useState([]);
  const [loading, setLoading]   = useState(true);
  const [selected, setSelected] = useState(null);
  const [showReco, setShowReco] = useState(false);
  const [ctxMenu, setCtxMenu]   = useState(null); // { pid, x, y }
  const pollRef = useRef(null);

  useEffect(() => {
    loadChats();
    pollRef.current = setInterval(loadChats, 10_000);
    return () => clearInterval(pollRef.current);
  }, []);

  // Закрывать меню при клике вне
  useEffect(() => {
    if (!ctxMenu) return;
    const close = () => setCtxMenu(null);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [ctxMenu]);

  async function loadChats() {
    try {
      const res = await api.get("/chats");
      setChats(res.data);
      if (!selected) {
        const first = res.data.find(c => c.last_message);
        if (first) setSelected(first.pid);
      }
    } catch {}
    setLoading(false);
  }

  async function removeContact(pid) {
    try {
      await api.delete(`/contact/${pid}`);
      setChats(cs => cs.filter(c => c.pid !== pid));
      if (selected === pid) setSelected(null);
    } catch {}
    setCtxMenu(null);
  }

  const selectedChat = chats.find(c => c.pid === selected);

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }} onClick={() => setCtxMenu(null)}>

      {/* ── Контекстное меню ── */}
      {ctxMenu && (
        <div
          onClick={e => e.stopPropagation()}
          style={{
            position: "fixed", zIndex: 1000,
            top: ctxMenu.y, left: ctxMenu.x,
            background: "#fff", borderRadius: 10,
            boxShadow: "0 4px 20px rgba(0,0,0,0.18)",
            padding: "4px 0", minWidth: 160,
          }}
        >
          <div
            onClick={() => removeContact(ctxMenu.pid)}
            style={{
              padding: "10px 16px", cursor: "pointer",
              fontSize: 13, color: "#e76f51",
              display: "flex", alignItems: "center", gap: 8,
            }}
          >
            🗑 Удалить из знакомых
          </div>
        </div>
      )}

      {/* ── Левая колонка: список друзей ── */}
      <div style={{
        flex: "0 0 40%",
        borderRight: "1px solid #eee",
        display: "flex", flexDirection: "column",
        overflow: "hidden",
      }}>
        {/* Кнопка рекомендаций */}
        <button
          onClick={() => { setShowReco(v => !v); setSelected(null); }}
          style={{
            margin: "8px 8px 4px",
            padding: "7px 10px",
            background: showReco ? "#e8f5e9" : "#f8f8f8",
            border: showReco ? "1.5px solid #2a9d8f" : "1.5px solid #eee",
            borderRadius: 10, cursor: "pointer",
            fontSize: 12, fontWeight: 600,
            color: showReco ? "#2a9d8f" : "#888",
            textAlign: "left",
          }}
        >
          🤝 Знакомства
        </button>

        {/* Список друзей */}
        <div style={{ flex: 1, overflowY: "auto" }}>
          {loading && (
            <div style={{ textAlign: "center", padding: 20, color: "#aaa", fontSize: 12 }}>
              Загрузка...
            </div>
          )}
          {!loading && chats.length === 0 && (
            <div style={{ padding: "16px 10px", textAlign: "center", color: "#bbb", fontSize: 12 }}>
              Нет друзей.<br />Нажми «Знакомства» ↑
            </div>
          )}
          {chats.map(c => (
            <FriendRow
              key={c.pid}
              chat={c}
              active={selected === c.pid && !showReco}
              onClick={() => { setSelected(c.pid); setShowReco(false); }}
              onContextMenu={(e) => {
                e.preventDefault();
                e.stopPropagation();
                const x = Math.min(e.clientX, window.innerWidth - 170);
                const y = Math.min(e.clientY, window.innerHeight - 60);
                setCtxMenu({ pid: c.pid, x, y });
              }}
            />
          ))}
        </div>
      </div>

      {/* ── Правая колонка: чат или знакомства ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {showReco && (
          <div style={{ flex: 1, overflowY: "auto" }}>
            <RecoPage
              user={user}
              onOpenDetail={onOpenDetail}
              onChat={(pid) => { setSelected(pid); setShowReco(false); }}
            />
          </div>
        )}

        {!showReco && selected && (
          <>
            {/* Мини-шапка с именем */}
            <div style={{
              padding: "8px 12px",
              borderBottom: "1px solid #eee",
              display: "flex", alignItems: "center", gap: 8,
              background: "#fff", flexShrink: 0,
            }}>
              <SmartAvatar pid={selected} name={selectedChat?.first_name} size={30} online={selectedChat?.is_online} />
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, lineHeight: 1.2 }}>
                  {selectedChat?.first_name} {selectedChat?.last_name}
                </div>
                {selectedChat?.skills?.length > 0 && (
                  <div style={{ fontSize: 10, color: "#aaa" }}>
                    {selectedChat.skills.join(" · ")}
                  </div>
                )}
              </div>
            </div>
            <InlineChat pid={selected} myPid={user?.pid} />
          </>
        )}

        {!showReco && !selected && (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "#ccc" }}>
            <div style={{ fontSize: 36, marginBottom: 8 }}>💬</div>
            <div style={{ fontSize: 13 }}>Выберите собеседника</div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Строка друга в левой колонке ──
function FriendRow({ chat, active, onClick, onContextMenu }) {
  const initial = (chat.first_name || "?")[0].toUpperCase();
  const hasUnread = chat.unread > 0;
  const longPressRef = useRef(null);

  function handleTouchStart(e) {
    longPressRef.current = setTimeout(() => {
      const touch = e.touches[0];
      onContextMenu({ preventDefault: () => {}, stopPropagation: () => {}, clientX: touch.clientX, clientY: touch.clientY });
    }, 500);
  }
  function handleTouchEnd() {
    clearTimeout(longPressRef.current);
  }

  return (
    <div
      onClick={onClick}
      onContextMenu={onContextMenu}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
      onTouchMove={handleTouchEnd}
      style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "8px 8px",
        cursor: "pointer",
        background: active ? "#e8f5e9" : "transparent",
        borderLeft: active ? "3px solid #2a9d8f" : "3px solid transparent",
        transition: "background .1s",
      }}
    >
      {/* Аватар */}
      <SmartAvatar pid={chat.pid} name={chat.first_name} size={38} online={chat.is_online} unread={chat.unread || 0} />

      {/* Имя + навыки */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 12, fontWeight: hasUnread ? 700 : 600,
          color: "#1a1a2e",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {chat.first_name}
        </div>
        {chat.skills?.length > 0 ? (
          <div style={{ display: "flex", gap: 3, marginTop: 2, flexWrap: "wrap" }}>
            {chat.skills.slice(0, 2).map(s => (
              <span key={s} style={{
                fontSize: 9, background: "#f0f0f0", color: "#666",
                borderRadius: 4, padding: "1px 4px",
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                maxWidth: 60,
              }}>
                {s}
              </span>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 10, color: "#bbb", marginTop: 1 }}>
            {chat.last_message
              ? chat.last_message.slice(0, 18) + (chat.last_message.length > 18 ? "…" : "")
              : "нет сообщений"}
          </div>
        )}
      </div>

      {/* Время */}
      {chat.last_time && (
        <div style={{ fontSize: 9, color: "#bbb", flexShrink: 0, alignSelf: "flex-start", marginTop: 2 }}>
          {chat.last_time}
        </div>
      )}
    </div>
  );
}