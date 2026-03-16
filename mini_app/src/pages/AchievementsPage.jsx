import { useState, useEffect, useRef } from "react";
import api from "../api";

const AI_TOOLS = ["ChatGPT", "Claude", "Gemini", "Midjourney", "Grok", "Другое"];
const BASE_URL = "https://fire35club.duckdns.org/fire35";

export default function AchievementsPage({ user }) {
  const [achievements, setAchievements] = useState([]);
  const [loading, setLoading]           = useState(true);
  const [posting, setPosting]           = useState(false);
  const [showForm, setShowForm]         = useState(false);
  const [form, setForm]                 = useState({ content: "", prompt_text: "", ai_tool: "" });
  const [mediaFile, setMediaFile]       = useState(null);   // { file, preview, type }
  const [uploading, setUploading]       = useState(false);
  const [error, setError]               = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => { loadFeed(); }, []);

  async function loadFeed() {
    setLoading(true);
    try {
      const res = await api.get("/achievements");
      setAchievements(res.data);
    } catch { setAchievements([]); }
    setLoading(false);
  }

  function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const isPhoto = file.type.startsWith("image/");
    const isAudio = file.type.startsWith("audio/");
    if (!isPhoto && !isAudio) {
      setError("Только фото (JPG, PNG) или аудио (MP3, OGG, WAV)");
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      setError("Файл слишком большой (максимум 15 МБ)");
      return;
    }
    setError(null);
    const preview = isPhoto ? URL.createObjectURL(file) : null;
    setMediaFile({ file, preview, type: isPhoto ? "photo" : "audio", name: file.name });
  }

  function removeMedia() {
    setMediaFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handlePost() {
    if (!form.content.trim() || form.content.trim().length < 5) {
      setError("Опиши достижение"); return;
    }
    setPosting(true); setError(null);
    try {
      let media_url = null;
      let media_type = null;

      if (mediaFile) {
        setUploading(true);
        const fd = new FormData();
        fd.append("file", mediaFile.file);
        const upRes = await api.post("/achievements/upload", fd);
        media_url = upRes.data.url;
        media_type = upRes.data.media_type;
        setUploading(false);
      }

      await api.post("/achievements", {
        content: form.content.trim(),
        prompt_text: form.prompt_text.trim() || null,
        ai_tool: form.ai_tool || null,
        media_url,
        media_type,
      });
      setForm({ content: "", prompt_text: "", ai_tool: "" });
      setMediaFile(null);
      setShowForm(false);
      await loadFeed();
    } catch (e) {
      setError(e.response?.data?.detail || "Ошибка публикации");
      setUploading(false);
    }
    setPosting(false);
  }

  async function handleLike(id) {
    try {
      const res = await api.post(`/achievements/${id}/like`);
      setAchievements(list => list.map(a =>
        a.id === id ? { ...a, likes: res.data.likes, liked_by_me: res.data.liked } : a
      ));
    } catch {}
  }

  async function handleDelete(id) {
    try {
      await api.delete(`/achievements/${id}`);
      setAchievements(list => list.filter(a => a.id !== id));
    } catch {}
  }

  return (
    <div className="page">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h1 className="page-title" style={{ margin: 0 }}>Достижения</h1>
        <button
          className="btn btn-primary"
          style={{ fontSize: 13, padding: "6px 14px" }}
          onClick={() => { setShowForm(f => !f); setError(null); }}
        >
          {showForm ? "✕ Отмена" : "+ Поделиться"}
        </button>
      </div>

      {/* ── Форма публикации ── */}
      {showForm && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="field-label" style={{ marginBottom: 8 }}>🏆 Твоё достижение с AI</div>

          <textarea
            className="input"
            value={form.content}
            onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
            rows={4}
            placeholder="Что ты сделал с помощью AI? Напиши результат..."
            style={{ resize: "none", fontFamily: "inherit", fontSize: 14, marginBottom: 8 }}
            disabled={posting}
          />

          <select
            className="input"
            value={form.ai_tool}
            onChange={e => setForm(f => ({ ...f, ai_tool: e.target.value }))}
            style={{ marginBottom: 8 }}
          >
            <option value="">Какой AI использовал?</option>
            {AI_TOOLS.map(t => <option key={t} value={t}>{t}</option>)}
          </select>

          <textarea
            className="input"
            value={form.prompt_text}
            onChange={e => setForm(f => ({ ...f, prompt_text: e.target.value }))}
            rows={3}
            placeholder="Промпт который ты использовал (необязательно)"
            style={{ resize: "none", fontFamily: "inherit", fontSize: 13, marginBottom: 8 }}
            disabled={posting}
          />

          {/* Загрузка медиа */}
          {!mediaFile ? (
            <div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp,audio/mpeg,audio/ogg,audio/wav,audio/mp4"
                onChange={handleFileChange}
                style={{ display: "none" }}
              />
              <button
                className="btn"
                style={{ width: "100%", fontSize: 13, marginBottom: 8 }}
                onClick={() => fileInputRef.current?.click()}
                type="button"
                disabled={posting}
              >
                📎 Прикрепить фото или аудио
              </button>
              <div style={{ fontSize: 11, color: "#bbb", textAlign: "center", marginBottom: 8 }}>
                JPG, PNG, WEBP · MP3, OGG, WAV · до 15 МБ
              </div>
            </div>
          ) : (
            <div style={{ marginBottom: 8, position: "relative" }}>
              {mediaFile.type === "photo" && (
                <img src={mediaFile.preview} alt="preview"
                  style={{ width: "100%", maxHeight: 200, objectFit: "cover", borderRadius: 8 }} />
              )}
              {mediaFile.type === "audio" && (
                <div style={{ background: "#f8f8f8", borderRadius: 8, padding: "10px 12px", display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 20 }}>🎵</span>
                  <span style={{ fontSize: 13, color: "#555", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {mediaFile.name}
                  </span>
                </div>
              )}
              <button
                onClick={removeMedia}
                style={{
                  position: "absolute", top: 6, right: 6,
                  background: "rgba(0,0,0,0.5)", border: "none", color: "#fff",
                  borderRadius: "50%", width: 24, height: 24, cursor: "pointer", fontSize: 12,
                }}
              >✕</button>
            </div>
          )}

          {error && <p className="error-text" style={{ fontSize: 13, marginBottom: 8 }}>{error}</p>}

          <button
            className="btn btn-primary btn-full"
            onClick={handlePost}
            disabled={posting || form.content.trim().length < 5}
          >
            {uploading ? "⬆️ Загружаю файл..." : posting ? "Публикую..." : "🚀 Опубликовать"}
          </button>
        </div>
      )}

      {/* ── Лента ── */}
      {loading && <div className="center-text">Загрузка...</div>}

      {!loading && achievements.length === 0 && (
        <div className="card center-text" style={{ color: "#999", fontSize: 14, padding: 24 }}>
          Пока нет достижений — будь первым!<br />
          <span style={{ fontSize: 13, color: "#bbb" }}>Поделись своим результатом работы с AI</span>
        </div>
      )}

      {achievements.map(a => (
        <AchievementCard
          key={a.id}
          item={a}
          onLike={() => handleLike(a.id)}
          onDelete={a.is_me ? () => handleDelete(a.id) : null}
        />
      ))}
    </div>
  );
}

function AchievementCard({ item, onLike, onDelete }) {
  const [expanded, setExpanded] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const mediaUrl = item.media_url
    ? (item.media_url.startsWith("/") ? BASE_URL + item.media_url : item.media_url)
    : null;

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      {/* Шапка */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{
            width: 32, height: 32, borderRadius: "50%",
            background: "#2a9d8f", color: "#fff",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 14, fontWeight: 700, flexShrink: 0,
          }}>
            {item.first_name[0]?.toUpperCase() || "?"}
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>
              {item.first_name}
              {item.ai_tool && (
                <span style={{ marginLeft: 6, fontSize: 11, background: "#f0f0f0", padding: "2px 6px", borderRadius: 8, color: "#666" }}>
                  {item.ai_tool}
                </span>
              )}
            </div>
            <div style={{ fontSize: 11, color: "#aaa" }}>{item.created_at}</div>
          </div>
        </div>
        {onDelete && !confirmDelete && (
          <button onClick={() => setConfirmDelete(true)}
            style={{ background: "none", border: "none", color: "#e76f51", cursor: "pointer", fontSize: 18, padding: "2px 4px" }}>🗑</button>
        )}
        {onDelete && confirmDelete && (
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "#e76f51" }}>Удалить?</span>
            <button onClick={() => { setConfirmDelete(false); onDelete(); }}
              style={{ background: "#e76f51", border: "none", color: "#fff", borderRadius: 6, fontSize: 12, padding: "3px 8px", cursor: "pointer" }}>Да</button>
            <button onClick={() => setConfirmDelete(false)}
              style={{ background: "#eee", border: "none", color: "#555", borderRadius: 6, fontSize: 12, padding: "3px 8px", cursor: "pointer" }}>Нет</button>
          </div>
        )}
      </div>

      {/* Медиа */}
      {mediaUrl && item.media_type === "photo" && (
        <div style={{ marginBottom: 10, borderRadius: 8, overflow: "hidden" }}>
          <img src={mediaUrl} alt="медиа"
            style={{ width: "100%", maxHeight: 300, objectFit: "cover" }}
            onError={e => { e.target.style.display = "none"; }} />
        </div>
      )}
      {mediaUrl && item.media_type === "audio" && (
        <div style={{ marginBottom: 10 }}>
          <audio controls src={mediaUrl} style={{ width: "100%", borderRadius: 8 }} />
        </div>
      )}

      {/* Контент */}
      <p style={{ fontSize: 14, lineHeight: 1.6, margin: "0 0 8px 0", whiteSpace: "pre-wrap" }}>
        {item.content}
      </p>

      {/* Промпт */}
      {item.prompt_text && (
        <div style={{ marginBottom: 8 }}>
          <button onClick={() => setExpanded(e => !e)}
            style={{ background: "none", border: "none", color: "#2a9d8f", fontSize: 12, cursor: "pointer", padding: 0, fontWeight: 600 }}>
            {expanded ? "▲ Скрыть промпт" : "▼ Показать промпт"}
          </button>
          {expanded && (
            <div style={{
              marginTop: 6, background: "#f8f8f8", borderRadius: 8,
              padding: "10px 12px", fontSize: 13, color: "#555",
              fontFamily: "monospace", lineHeight: 1.5, whiteSpace: "pre-wrap",
            }}>
              {item.prompt_text}
            </div>
          )}
        </div>
      )}

      {/* Лайк */}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <button onClick={onLike}
          style={{ background: "none", border: "none", cursor: "pointer", fontSize: 18, padding: "2px 6px", filter: item.liked_by_me ? "none" : "grayscale(1)" }}>
          ❤️
        </button>
        <span style={{ fontSize: 13, color: "#888" }}>{item.likes > 0 ? item.likes : ""}</span>
      </div>
    </div>
  );
}
