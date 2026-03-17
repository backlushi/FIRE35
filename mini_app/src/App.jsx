import { useState, useEffect, useRef } from "react";
import api from "./api";
import ProfilePage from "./pages/ProfilePage";
import MembersPage from "./pages/MembersPage";
import QuestionsPage from "./pages/QuestionsPage";
import ReportPage from "./pages/ReportPage";
import AdminPage from "./pages/AdminPage";
import AchievementsPage from "./pages/AchievementsPage";
import OnboardingScreen from "./pages/OnboardingScreen";

const TABS = [
  { id: "profile",      label: "Профиль",     icon: "👤" },
  { id: "members",      label: "Связи",       icon: "👥" },
  { id: "questions",    label: "Вопросы",     icon: "🤔" },
  { id: "achievements", label: "Достижения",  icon: "🏆" },
  { id: "report",       label: "Отчёт",       icon: "📝" },
];

export default function App() {
  const [tab, setTab]                 = useState("profile");
  const [user, setUser]               = useState(null);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState(null);
  const [toast, setToast]             = useState(null);
  const [needConsent, setNeedConsent] = useState(false);
  const [needOnboarding, setNeedOnboarding] = useState(false);
  const [consentSaving, setConsentSaving]   = useState(false);
  const [unreadChats, setUnreadChats]       = useState(0);
  const [membersSubTab, setMembersSubTab]   = useState(null);
  const [motivation, setMotivation]         = useState(null); // { icon, title, text, action, action_label }
  const pingRef = useRef(null);
  const unreadRef = useRef(null);

  useEffect(() => { initApp(); }, []);

  // Пинг онлайн-статуса каждые 60 секунд
  useEffect(() => {
    if (!user) return;
    api.post("/me/ping").catch(() => {});
    pingRef.current = setInterval(() => {
      api.post("/me/ping").catch(() => {});
    }, 60_000);
    return () => clearInterval(pingRef.current);
  }, [user]);

  useEffect(() => {
    if (!user) return;
    const fetchUnread = () => api.get("/chats/unread").then(r => setUnreadChats(r.data.unread)).catch(() => {});
    fetchUnread();
    unreadRef.current = setInterval(fetchUnread, 15_000);
    return () => clearInterval(unreadRef.current);
  }, [user]);

  // Мотивационный пинок — один раз при входе, через 2 сек
  useEffect(() => {
    if (!user) return;
    const timer = setTimeout(() => {
      api.get("/me/motivation").then(r => {
        const msgs = r.data.messages;
        if (msgs?.length > 0) setMotivation(msgs[0]);
      }).catch(() => {});
    }, 2000);
    return () => clearTimeout(timer);
  }, [user]);

  function showToast(msg, ms = 3000) {
    setToast(msg);
    setTimeout(() => setToast(null), ms);
  }

  async function initApp() {
    const tg = window.Telegram?.WebApp;
    if (tg?.initData) {
      tg.ready();
      tg.expand();
      if (tg.isFullscreen) tg.exitFullscreen?.();
      try {
        const res = await api.post("/auth/webapp", { init_data: tg.initData });
        localStorage.setItem("token", res.data.access_token);
        if (!res.data.consent_given) {
          setNeedConsent(true);
          setLoading(false);
          return;
        }
        const me = await api.get("/me");
        setUser(me.data);
        if (!me.data.onboarding_done) {
          setNeedOnboarding(true);
        } else if (!me.data.profession || !me.data.skills) {
          setTimeout(() => showToast("👤 Заполни профиль и навыки →"), 1200);
        }
      } catch (e) {
        setError(e.response?.data?.detail || "Ошибка авторизации через Telegram");
      }
    } else {
      const token = localStorage.getItem("token");
      if (token) {
        try {
          const me = await api.get("/me");
          setUser(me.data);
          if (!me.data.onboarding_done) {
            setNeedOnboarding(true);
          } else if (!me.data.profession || !me.data.skills) {
            setTimeout(() => showToast("👤 Заполни профиль и навыки →"), 1200);
          }
        } catch {
          localStorage.removeItem("token");
          setError("Сессия истекла. Откройте через Telegram.");
        }
      } else {
        setError("Откройте приложение через бот @fire35_bot");
      }
    }
    setLoading(false);
  }

  async function acceptConsent() {
    setConsentSaving(true);
    try {
      await api.post("/consent");
      const me = await api.get("/me");
      setUser(me.data);
      setNeedConsent(false);
      if (!me.data.onboarding_done) {
        setNeedOnboarding(true);
      }
    } catch {
      setError("Ошибка. Попробуйте ещё раз.");
    }
    setConsentSaving(false);
  }

  function handleOnboardingDone() {
    setNeedOnboarding(false);
    // Обновляем профиль пользователя
    api.get("/me").then(res => setUser(res.data)).catch(() => {});
  }

  if (needConsent) {
    return (
      <div className="splash consent-screen">
        <div className="consent-icon">🔐</div>
        <h2 className="consent-title">Соглашение об обработке данных</h2>
        <div className="consent-body">
          <p>Для участия в клубе <strong>FIRE35</strong> мы сохраняем:</p>
          <ul>
            <li>Ваш Telegram username и имя</li>
            <li>Финансовые показатели <em>(в обезличенном виде)</em></li>
            <li>Прогресс по темам клуба</li>
          </ul>
          <p>Данные используются только внутри клуба и <strong>не передаются</strong> третьим лицам.</p>
          <div className="consent-links">
            <a href="/fire35-app/terms.html" target="_blank" rel="noopener">
              📄 Пользовательское соглашение
            </a>
            <a href="/fire35-app/privacy.html" target="_blank" rel="noopener">
              🔐 Политика конфиденциальности
            </a>
          </div>
        </div>
        <button
          className="btn btn-primary btn-full"
          onClick={acceptConsent}
          disabled={consentSaving}
        >
          {consentSaving ? "Сохраняю..." : "✅ Согласен(а)"}
        </button>
        <p className="consent-note">
          Нажимая «Согласен(а)», вы принимаете условия соглашения и политику обработки данных
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="splash">
        <div className="spinner" />
        <p>Загрузка...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="splash">
        <div style={{ fontSize: 48 }}>⚠️</div>
        <p className="error-text">{error}</p>
      </div>
    );
  }

  // ── Онбординг-экран (показывается один раз) ──
  if (needOnboarding) {
    return <OnboardingScreen onDone={handleOnboardingDone} />;
  }

  const isAdmin = user?.pid === "P-001";
  const tabs = isAdmin ? [...TABS, { id: "admin", label: "Админ", icon: "⚙️" }] : TABS;

  return (
    <div className="app">
      <div className="content">
        {tab === "profile"      && <ProfilePage user={user} setUser={setUser} unreadChats={unreadChats} onGoToChats={() => { setMembersSubTab("chats"); setTab("members"); }} />}
        {tab === "members"      && <MembersPage user={user} initialSubTab={membersSubTab} onSubTabChange={() => setMembersSubTab(null)} />}
        {tab === "questions"    && <QuestionsPage user={user} />}
        {tab === "achievements" && <AchievementsPage user={user} />}
        {tab === "report"       && <ReportPage user={user} />}
        {tab === "admin"        && <AdminPage user={user} />}
      </div>

      <nav className="tabbar">
        {tabs.map(t => (
          <button
            key={t.id}
            className={"tab-btn" + (tab === t.id ? " active" : "")}
            onClick={() => { setTab(t.id); if (t.id === "members") setUnreadChats(0); }}
          >
            <span className="tab-icon" style={{ position: "relative" }}>
              {t.icon}
              {t.id === "members" && unreadChats > 0 && (
                <span style={{
                  position: "absolute", top: -4, right: -6,
                  background: "#e76f51", color: "#fff",
                  borderRadius: "50%", fontSize: 9, fontWeight: 700,
                  minWidth: 14, height: 14, display: "flex",
                  alignItems: "center", justifyContent: "center",
                  padding: "0 2px",
                }}>
                  {unreadChats > 9 ? "9+" : unreadChats}
                </span>
              )}
            </span>
            <span className="tab-label">{t.label}</span>
          </button>
        ))}
      </nav>

      {/* ── Toast-уведомление ── */}
      {toast && (
        <div
          className="toast"
          onClick={() => { setToast(null); setTab("profile"); }}
        >
          {toast}
        </div>
      )}

      {/* ── Мотивационный попап ── */}
      {motivation && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)",
          zIndex: 2000, display: "flex", alignItems: "flex-end",
        }} onClick={() => setMotivation(null)}>
          <div
            onClick={e => e.stopPropagation()}
            style={{
              width: "100%", background: "#fff",
              borderRadius: "18px 18px 0 0",
              padding: "20px 20px 28px",
              boxShadow: "0 -4px 24px rgba(0,0,0,0.12)",
              animation: "slideUp .25s ease",
            }}
          >
            <div style={{ fontSize: 36, marginBottom: 8, textAlign: "center" }}>{motivation.icon}</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: "#1a1a2e", textAlign: "center", marginBottom: 8 }}>
              {motivation.title}
            </div>
            <div style={{ fontSize: 13, color: "#555", lineHeight: 1.5, textAlign: "center", marginBottom: 18 }}>
              {motivation.text}
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {motivation.action_label && (
                <button
                  className="btn btn-primary"
                  style={{ flex: 1, fontSize: 13 }}
                  onClick={() => {
                    setMotivation(null);
                    const actionMap = { report: "report", profile: "profile", chats: "members", questions: "questions", achievements: "profile", games: "profile" };
                    const t = actionMap[motivation.action] || "profile";
                    setTab(t);
                    if (t === "members") setMembersSubTab("chats");
                  }}
                >
                  {motivation.action_label}
                </button>
              )}
              <button
                className="btn btn-secondary"
                style={{ flex: motivation.action_label ? "0 0 80px" : 1, fontSize: 13 }}
                onClick={() => setMotivation(null)}
              >
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
