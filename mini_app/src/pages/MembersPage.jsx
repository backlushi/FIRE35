import { useState, useEffect, useMemo, useCallback } from "react";
import Fuse from "fuse.js";
import api from "../api";
import ChatPage from "./ChatPage";
import ChatsPage from "./ChatsPage";
import AchievementsPage from "./AchievementsPage";
import SmartAvatar from "../components/SmartAvatar";

// ─── Helpers ──────────────────────────────────────────────
const AVATAR_COLORS = [
  "#FF6B6B","#4ECDC4","#45B7D1","#FFA07A",
  "#98D8C8","#7B68EE","#FFB347","#87CEEB",
  "#DDA0DD","#90EE90","#F0A500","#20B2AA",
];
function pidColor(pid) {
  const n = parseInt((pid || "P-0").replace(/\D/g, ""), 10) || 0;
  return AVATAR_COLORS[n % AVATAR_COLORS.length];
}

function Avatar({ pid, name, size = 38, online = false }) {
  return <SmartAvatar pid={pid} name={name} size={size} online={online} />;
}

// ─── Detail View ──────────────────────────────────────────
function DetailView({ pid, detail, loading, onBack, onContact, onChat }) {
  const [qSectionOpen, setQSectionOpen] = useState(false);
  const [qExpandedId, setQExpandedId]   = useState(null);

  const toggleQ = useCallback((id) => {
    setQExpandedId(cur => cur === id ? null : id);
  }, []);

  return (
    <div className="page detail-page">
      <div className="detail-topbar">
        <button className="back-btn" onClick={onBack}>← Назад</button>
      </div>

      {loading && <div className="center-text" style={{ marginTop: 48 }}>Загрузка...</div>}
      {!loading && (!detail || detail.error) && (
        <div className="card center-text" style={{ margin: 16 }}>Не удалось загрузить профиль</div>
      )}

      {!loading && detail && !detail.error && (
        <div className="detail-content">
          <div className="detail-hero">
            <Avatar pid={detail.pid} name={detail.first_name} size={56} online={detail.is_online} />
            <div className="detail-hero-info">
              <div className="detail-hero-name" style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span>{detail.first_name} {detail.last_name}</span>
                {detail.is_me && <span className="badge-me">Вы</span>}
                {!detail.is_me && detail.contact_status === "accepted" && (
                  <button
                    onClick={() => onChat(pid)}
                    title="Написать сообщение"
                    style={{
                      background: "#2a9d8f", border: "none", color: "#fff",
                      borderRadius: "50%", width: 28, height: 28,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 14, cursor: "pointer", flexShrink: 0,
                    }}
                  >💬</button>
                )}
              </div>
              <div className="detail-hero-pid">{detail.pid}</div>
              {detail.profession && (
                <div className="detail-hero-prof">{detail.profession}</div>
              )}
              <div className="detail-online-status">
                {detail.is_online
                  ? <><span className="online-dot-inline" />в сети</>
                  : detail.last_seen
                    ? <span className="offline-time">был(а) {detail.last_seen}</span>
                    : null
                }
              </div>
            </div>
          </div>

          {detail.answer_score > 0 && (
            <div className="detail-expert-bar">
              <span>🏅 Эксперт клуба</span>
              <span>{detail.answer_score} полезных / {detail.total_answers} ответов</span>
            </div>
          )}

          {detail.skills?.length > 0 && (
            <div className="detail-section">
              <div className="detail-section-title">Навыки</div>
              <div className="skills-wrap">
                {detail.skills.map(s => (
                  <span key={s} className="skill-chip">{s}</span>
                ))}
              </div>
            </div>
          )}

          {/* Достижения участника */}
          {(detail.contact_status === "accepted" || detail.is_me) && (
            <div className="detail-section">
              <div className="detail-section-title">🏆 Достижения</div>
              <AchievementsPage user={null} filterPid={detail.pid} />
            </div>
          )}

          {detail.questions?.length > 0 && (
            <div className="detail-section">
              <div
                className="detail-section-title detail-section-toggle"
                onClick={() => setQSectionOpen(v => !v)}
              >
                <span>Вопросы в клубе <span className="detail-q-count">({detail.questions.length})</span></span>
                <span className="detail-section-plus">{qSectionOpen ? "−" : "+"}</span>
              </div>

              {qSectionOpen && (
                <div className="detail-q-list">
                  {detail.questions.map(q => {
                    const isOpen   = qExpandedId === q.id;
                    const hasUseful = q.has_useful;
                    return (
                      <div key={q.id} className={"dq-card" + (isOpen ? " dq-card-open" : "")}>
                        {/* Заголовок-строка */}
                        <div className="dq-header" onClick={() => toggleQ(q.id)}>
                          <div className="dq-meta">
                            <span className="dq-date">{q.created_at}</span>
                            {q.tags?.map(t => (
                              <span key={t} className="tag-chip dq-tag">{t}</span>
                            ))}
                          </div>
                          <div className="dq-right">
                            <span className="dq-status">
                              {hasUseful ? "✅" : q.answer_count > 0 ? `💬 ${q.answer_count}` : "⏳"}
                            </span>
                            <span className="dq-chevron">{isOpen ? "▲" : "▼"}</span>
                          </div>
                        </div>
                        <div className="dq-preview">{q.question}</div>

                        {/* Раскрытый блок */}
                        {isOpen && (
                          <div className="dq-body">
                            {q.answers.length === 0 ? (
                              <div className="dq-no-answers">Пока нет ответов</div>
                            ) : q.answers.map(a => (
                              <div key={a.id} className={"dq-answer" + (a.is_useful ? " dq-answer-accepted" : "")}>
                                {a.is_useful && <div className="dq-accepted-label">✅ Принятый ответ</div>}
                                <div className="dq-answer-meta">
                                  <span className="dq-answer-author">{a.expert_name}</span>
                                  <span className="dq-answer-date">{a.created_at}</span>
                                  {a.vote_score !== 0 && (
                                    <span className={"dq-vote" + (a.vote_score > 0 ? " pos" : " neg")}>
                                      {a.vote_score > 0 ? "▲" : "▼"}{Math.abs(a.vote_score)}
                                    </span>
                                  )}
                                </div>
                                <div className="dq-answer-text">{a.answer}</div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {!detail.is_me && (
            <div className="detail-actions">
              {detail.contact_status === "accepted" ? (
                <div style={{ display: "flex", gap: 8 }}>
                  <div className="contact-badge accepted" style={{ flex: 1 }}>✅ Вы знакомы</div>
                  <button
                    className="btn btn-primary"
                    style={{ flexShrink: 0 }}
                    onClick={() => onChat(pid)}
                  >
                    💬 Написать
                  </button>
                </div>
              ) : detail.contact_status === "pending" ? (
                <div className="contact-badge pending">⏳ Запрос отправлен</div>
              ) : (
                <button
                  className="btn btn-primary btn-full"
                  onClick={() => onContact(pid)}
                >
                  👋 Познакомиться
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Filter Panel ─────────────────────────────────────────
function FilterPanel({ allProfessions, allSkills, filters, onChange, onClose }) {
  function toggle(key, val) {
    onChange(f => ({
      ...f,
      [key]: f[key].includes(val) ? f[key].filter(x => x !== val) : [...f[key], val],
    }));
  }
  return (
    <div className="filter-panel">
      {allProfessions.length > 0 && (
        <div className="filter-group">
          <div className="filter-group-title">Профессия</div>
          <div className="filter-options">
            {allProfessions.map(p => (
              <button
                key={p}
                className={"filter-option" + (filters.professions.includes(p) ? " selected" : "")}
                onClick={() => toggle("professions", p)}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
      )}
      {allSkills.length > 0 && (
        <div className="filter-group">
          <div className="filter-group-title">Навыки</div>
          <div className="filter-options">
            {allSkills.map(s => (
              <button
                key={s}
                className={"filter-option" + (filters.skills.includes(s) ? " selected" : "")}
                onClick={() => toggle("skills", s)}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="filter-group">
        <div className="filter-group-title">
          Мин. рейтинг эксперта: {filters.min_score > 0 ? filters.min_score : "любой"}
        </div>
        <input
          type="range" min={0} max={20} step={1}
          value={filters.min_score}
          onChange={e => onChange(f => ({ ...f, min_score: +e.target.value }))}
          className="filter-range"
        />
      </div>
      <button className="btn btn-sm" style={{ margin: "8px 0 4px" }} onClick={onClose}>
        Готово
      </button>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────
const EMPTY_FILTERS = { professions: [], skills: [], min_score: 0 };
const PAGE_SIZE = 80; // items shown initially; +80 on "show more"

export default function MembersPage({ user, initialSubTab, onSubTabChange }) {
  const [subTab, setSubTab] = useState(initialSubTab || "members");
  function changeSubTab(t) { setSubTab(t); onSubTabChange?.(); }
  const [members, setMembers]           = useState([]);
  const [loading, setLoading]           = useState(true);
  const [search, setSearch]             = useState("");
  const [sort, setSort]                 = useState("pid");
  const [showFilters, setShowFilters]   = useState(false);
  const [filters, setFilters]           = useState(EMPTY_FILTERS);
  const [visible, setVisible]           = useState(PAGE_SIZE);
  const [selected, setSelected]         = useState(null);
  const [detail, setDetail]             = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [chatPid, setChatPid]           = useState(null);

  useEffect(() => { loadMembers(); }, []);

  async function loadMembers() {
    setLoading(true);
    try {
      const res = await api.get("/members");
      setMembers(res.data);
    } catch {
      setMembers([]);
    }
    setLoading(false);
  }

  // Fuse.js instance — rebuilt only when members change
  const fuse = useMemo(() => new Fuse(members, {
    keys: ["first_name", "last_name", "profession", "skills"],
    threshold: 0.35,
    includeScore: true,
  }), [members]);

  const allProfessions = useMemo(() =>
    [...new Set(members.map(m => m.profession).filter(Boolean))].sort(), [members]);
  const allSkills = useMemo(() =>
    [...new Set(members.flatMap(m => m.skills))].sort(), [members]);

  // Filtered + sorted list
  const displayed = useMemo(() => {
    let list = search.trim()
      ? fuse.search(search.trim()).map(r => r.item)
      : [...members];

    if (filters.professions.length > 0)
      list = list.filter(m => filters.professions.includes(m.profession));
    if (filters.skills.length > 0)
      list = list.filter(m => filters.skills.some(s => m.skills.includes(s)));
    if (filters.min_score > 0)
      list = list.filter(m => (m.fire_total || m.answer_score) >= filters.min_score);

    // Sort only when not in fuzzy-search mode (fuse already ranks by relevance)
    if (!search.trim()) {
      if (sort === "score")
        list.sort((a, b) => (b.fire_total || 0) - (a.fire_total || 0));
      else
        list.sort((a, b) => a.pid.localeCompare(b.pid));
    }
    return list;
  }, [members, search, fuse, filters, sort]);

  // Active filter chips
  const activeChips = [
    ...filters.professions.map(p => ({
      label: p,
      remove: () => setFilters(f => ({ ...f, professions: f.professions.filter(x => x !== p) })),
    })),
    ...filters.skills.map(s => ({
      label: `#${s}`,
      remove: () => setFilters(f => ({ ...f, skills: f.skills.filter(x => x !== s) })),
    })),
    ...(filters.min_score > 0 ? [{
      label: `⭐≥${filters.min_score}`,
      remove: () => setFilters(f => ({ ...f, min_score: 0 })),
    }] : []),
  ];

  async function openDetail(pid) {
    setSelected(pid);
    setDetail(null);
    setDetailLoading(true);
    try {
      const res = await api.get(`/members/${pid}`);
      setDetail(res.data);
    } catch {
      setDetail({ error: true });
    }
    setDetailLoading(false);
  }

  async function sendContact(pid) {
    try {
      await api.post(`/contact-request/${pid}`);
      setDetail(d => d ? { ...d, contact_status: "pending" } : d);
    } catch (e) {
      alert(e.response?.data?.detail || "Ошибка");
    }
  }

  // Reset visible count when filters/search/sort change
  useMemo(() => { setVisible(PAGE_SIZE); }, [displayed]); // eslint-disable-line react-hooks/exhaustive-deps

  if (chatPid) {
    return <ChatPage pid={chatPid} onBack={() => setChatPid(null)} />;
  }

  if (selected) {
    return (
      <DetailView
        pid={selected}
        detail={detail}
        loading={detailLoading}
        onBack={() => { setSelected(null); setDetail(null); }}
        onContact={sendContact}
        onChat={(pid) => { setSelected(null); setDetail(null); setChatPid(pid); }}
      />
    );
  }

  if (subTab === "chats") {
    return (
      <div className="page members-page" style={{ padding: 0, display: "flex", flexDirection: "column" }}>
        <SubTabs active="chats" onChange={changeSubTab} />
        <div style={{ flex: 1, overflow: "hidden", minHeight: 0 }}>
          <ChatsPage user={user} onOpenDetail={openDetail} />
        </div>
      </div>
    );
  }

  return (
    <div className="page members-page">
      <SubTabs active="members" onChange={changeSubTab} />


      {/* Search + Filter button */}
      <div className="members-search-row">
        <input
          className="members-search-input"
          placeholder="🔍 Поиск по имени, профессии, навыкам..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <button
          className={"members-filter-btn" + (activeChips.length > 0 ? " has-filters" : "")}
          onClick={() => setShowFilters(v => !v)}
          title="Фильтры"
        >
          {activeChips.length > 0 ? `⚙️\u00A0${activeChips.length}` : "⚙️"}
        </button>
      </div>

      {/* Sort toggle + count */}
      <div className="members-sort-row">
        <span className="members-count">
          {loading ? "..." : `${displayed.length} уч.`}
        </span>
        <div className="sort-toggle">
          {[
            { id: "pid",   label: "А-Я" },
            { id: "score", label: "🔥 FIRE Score" },
          ].map(s => (
            <button
              key={s.id}
              className={"sort-btn" + (sort === s.id ? " active" : "")}
              onClick={() => setSort(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Active filter chips */}
      {activeChips.length > 0 && (
        <div className="filter-chips-row">
          {activeChips.map((c, i) => (
            <span key={i} className="filter-chip">
              {c.label}
              <button
                className="filter-chip-x"
                onClick={e => { e.stopPropagation(); c.remove(); }}
              >×</button>
            </span>
          ))}
          <button
            className="filter-chip-clear"
            onClick={() => setFilters(EMPTY_FILTERS)}
          >
            Сбросить
          </button>
        </div>
      )}

      {/* Filter panel */}
      {showFilters && (
        <FilterPanel
          allProfessions={allProfessions}
          allSkills={allSkills}
          filters={filters}
          onChange={setFilters}
          onClose={() => setShowFilters(false)}
        />
      )}

      {/* List */}
      {loading ? (
        <div className="center-text" style={{ paddingTop: 32 }}>Загрузка...</div>
      ) : displayed.length === 0 ? (
        <div className="card center-text" style={{ margin: 16 }}>
          {search ? "Никого не найдено — попробуйте другой запрос" : "Нет участников"}
        </div>
      ) : (
        <div className="members-list-wrap">
          {displayed.slice(0, visible).map(m => {
            const isFire = m.fire_level && (m.fire_level.startsWith("FIRE") || m.fire_level === "Бабайкин");
            return (
              <div
                key={m.pid}
                className={"member-row" + (m.is_me ? " member-row-me" : "")}
                onClick={() => openDetail(m.pid)}
              >
                <Avatar pid={m.pid} name={m.first_name || m.pid} size={44} online={m.is_online} />
                <div className="member-row-info">
                  <div className="member-row-top">
                    <span className="member-row-name">
                      {m.first_name} {m.last_name}
                      {m.is_me && <span className="badge-me-xs">Вы</span>}
                    </span>
                    {m.fire_level && (
                      <span className={"fire-level-badge" + (isFire ? " fire" : "")}>
                        {m.fire_level}
                      </span>
                    )}
                  </div>
                  {m.profession && (
                    <div className="member-row-prof">{m.profession}</div>
                  )}
                  {m.skills.length > 0 && (
                    <div className="member-row-skills">
                      {m.skills.slice(0, 2).map(s => (
                        <span key={s} className="skill-chip-xs">{s}</span>
                      ))}
                      {m.skills.length > 2 && (
                        <span className="skill-chip-xs skill-more">+{m.skills.length - 2}</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          {visible < displayed.length && (
            <button
              className="btn btn-sm show-more-btn"
              onClick={() => setVisible(v => v + PAGE_SIZE)}
            >
              Показать ещё ({displayed.length - visible})
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Подтабы Участники / Знакомства ──────────────────────
function SubTabs({ active, onChange }) {
  return (
    <div className="connections-subtabs">
      <button
        className={"conn-tab" + (active === "members" ? " conn-tab-active" : "")}
        onClick={() => onChange("members")}
      >👥 Участники</button>
      <button
        className={"conn-tab" + (active === "chats" ? " conn-tab-active" : "")}
        onClick={() => onChange("chats")}
      >💬 Знакомства</button>
    </div>
  );
}
