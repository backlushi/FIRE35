import { useState, useEffect, useRef } from "react";
import api from "../api";
import ChatPage from "./ChatPage";

const AVATAR_COLORS = [
  "#FF6B6B","#4ECDC4","#45B7D1","#FFA07A",
  "#98D8C8","#7B68EE","#FFB347","#87CEEB",
  "#DDA0DD","#90EE90","#F0A500","#20B2AA",
];
function pidColor(pid) {
  const n = parseInt((pid || "P-0").replace(/\D/g,""), 10) || 0;
  return AVATAR_COLORS[n % AVATAR_COLORS.length];
}

export default function ChatsPage({ user }) {
  const [chats, setChats]       = useState([]);
  const [loading, setLoading]   = useState(true);
  const [openPid, setOpenPid]   = useState(null);
  const pollRef = useRef(null);

  useEffect(() => {
    loadChats();
    pollRef.current = setInterval(loadChats, 10_000);
    return () => clearInterval(pollRef.current);
  }, []);

  async function loadChats() {
    try {
      const res = await api.get("/chats");
      setChats(res.data);
    } catch {}
    setLoading(false);
  }

  // Открыт чат — показываем ChatPage
  if (openPid) {
    return (
      <ChatPage
        pid={openPid}
        onBack={() => { setOpenPid(null); loadChats(); }}
      />
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Шапка */}
      <div style={{
        padding: "12px 16px 8px",
        borderBottom: "1px solid #f0f0f0",
        flexShrink: 0,
      }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: "#1a1a2e" }}>
          💬 Сообщения
        </div>
        <div style={{ fontSize: 12, color: "#aaa", marginTop: 2 }}>
          {chats.length > 0 ? `${chats.length} контакт${chats.length === 1 ? "" : chats.length < 5 ? "а" : "ов"}` : ""}
        </div>
      </div>

      {/* Список */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {loading && (
          <div style={{ textAlign: "center", padding: 32, color: "#aaa", fontSize: 14 }}>
            Загрузка...
          </div>
        )}

        {!loading && chats.length === 0 && (
          <div style={{ textAlign: "center", padding: "40px 24px", color: "#bbb" }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>💬</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#888", marginBottom: 6 }}>
              Нет контактов
            </div>
            <div style={{ fontSize: 13 }}>
              Познакомься с участниками во вкладке «Знакомства»
            </div>
          </div>
        )}

        {chats.map(c => (
          <ChatRow
            key={c.pid}
            chat={c}
            onClick={() => setOpenPid(c.pid)}
          />
        ))}
      </div>
    </div>
  );
}

function ChatRow({ chat, onClick }) {
  const initial = (chat.first_name || "?")[0].toUpperCase();
  const hasUnread = chat.unread > 0;

  return (
    <div
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center", gap: 12,
        padding: "10px 16px",
        borderBottom: "1px solid #f7f7f7",
        cursor: "pointer",
        background: hasUnread ? "#f0fdf4" : "#fff",
        transition: "background .1s",
      }}
    >
      {/* Аватар */}
      <div style={{ position: "relative", flexShrink: 0 }}>
        <div style={{
          width: 46, height: 46, borderRadius: "50%",
          background: pidColor(chat.pid), color: "#fff",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 18, fontWeight: 700,
        }}>
          {initial}
        </div>
        {chat.is_online && (
          <span style={{
            position: "absolute", bottom: 1, right: 1,
            width: 11, height: 11, borderRadius: "50%",
            background: "#2a9d8f", border: "2px solid #fff",
          }} />
        )}
      </div>

      {/* Контент */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span style={{
            fontSize: 14, fontWeight: hasUnread ? 700 : 600,
            color: "#1a1a2e", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            maxWidth: "65%",
          }}>
            {chat.first_name} {chat.last_name}
          </span>
          <span style={{ fontSize: 11, color: "#bbb", flexShrink: 0 }}>
            {chat.last_time || ""}
          </span>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 2 }}>
          <span style={{
            fontSize: 13, color: hasUnread ? "#555" : "#aaa",
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            maxWidth: "80%",
            fontWeight: hasUnread ? 500 : 400,
          }}>
            {chat.last_message
              ? (chat.last_message_mine ? "Вы: " : "") + chat.last_message.slice(0, 45) + (chat.last_message.length > 45 ? "…" : "")
              : <span style={{ color: "#ccc", fontStyle: "italic" }}>Нет сообщений</span>
            }
          </span>
          {hasUnread && (
            <span style={{
              background: "#2a9d8f", color: "#fff",
              fontSize: 11, fontWeight: 700,
              borderRadius: "50%", minWidth: 20, height: 20,
              display: "flex", alignItems: "center", justifyContent: "center",
              padding: "0 4px", flexShrink: 0,
            }}>
              {chat.unread > 9 ? "9+" : chat.unread}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
