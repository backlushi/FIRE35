import { useState, useEffect, useCallback } from "react";
import api from "../api";

const AVATAR_COLORS = [
  "#FF6B6B","#4ECDC4","#45B7D1","#FFA07A",
  "#98D8C8","#7B68EE","#FFB347","#87CEEB",
  "#DDA0DD","#90EE90","#F0A500","#20B2AA",
];
function pidColor(pid) {
  const n = parseInt((pid || "P-0").replace(/\D/g, ""), 10) || 0;
  return AVATAR_COLORS[n % AVATAR_COLORS.length];
}

export default function RecoPage({ user, onOpenDetail }) {
  const [intros, setIntros]       = useState(null);
  const [friends, setFriends]     = useState([]);
  const [privacy, setPrivacy]     = useState(null);
  const [loading, setLoading]     = useState(true);
  const [consentSaving, setConsentSaving] = useState(false);
  const [done, setDone]           = useState({});

  const load = useCallback(async () => {
    try {
      const [pr, ir, fr] = await Promise.all([
        api.get("/me/privacy"),
        api.get("/me/introductions"),
        api.get("/me/friends"),
      ]);
      setPrivacy(pr.data);
      setIntros(ir.data);
      setFriends(fr.data);
    } catch {
      setIntros([]);
      setFriends([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function enableConsent() {
    setConsentSaving(true);
    try {
      await api.patch("/me/privacy", { intro_consent_given: true, intro_receive: true });
      await load();
    } catch {/* ignore */}
    setConsentSaving(false);
  }

  async function feedback(introId, action) {
    setDone(d => ({ ...d, [introId]: action }));
    try {
      await api.post(`/introductions/${introId}/feedback?action=${action}`);
    } catch {
      setDone(d => { const n = { ...d }; delete n[introId]; return n; });
    }
  }

  if (loading) {
    return (
      <div className="reco-inner">
        <div className="spinner" style={{ margin: "60px auto" }} />
      </div>
    );
  }

  const activeIntros = (intros || []).filter(i => !done[i.id]);
  const doneIntros   = (intros || []).filter(i =>  done[i.id]);

  return (
    <div className="reco-inner">

      {/* ── Мои знакомства ── */}
      {friends.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#555", marginBottom: 10 }}>
            🤝 Мои знакомства ({friends.length})
          </div>
          <div className="members-list">
            {friends.map(f => (
              <FriendRow key={f.pid} friend={f} onOpenDetail={onOpenDetail} />
            ))}
          </div>
        </div>
      )}

      {/* ── Рекомендации ── */}
      {privacy && !privacy.intro_consent_given ? (
        <div className="reco-empty">
          <div className="reco-empty-icon">🤝</div>
          <h3 className="reco-empty-title">Рекомендации знакомств</h3>
          <p className="reco-empty-text">
            Система подберёт участников клуба с похожими интересами и навыками.
            Раз в две недели мы будем предлагать 2–3 человека для знакомства.
          </p>
          <p className="reco-empty-hint">
            Для этого нужно разрешить показывать ваш профиль другим участникам.
          </p>
          <button
            className="btn btn-primary"
            onClick={enableConsent}
            disabled={consentSaving}
          >
            {consentSaving ? "Сохраняю..." : "✅ Включить рекомендации"}
          </button>
        </div>
      ) : (!intros || intros.length === 0) ? (
        <div className="reco-empty">
          <div className="reco-empty-icon">🌟</div>
          <h3 className="reco-empty-title">Пока нет рекомендаций</h3>
          <p className="reco-empty-text">
            Рекомендации обновляются раз в две недели.
            Убедитесь, что ваш профиль заполнен — профессия и навыки помогают
            точнее подбирать знакомства.
          </p>
        </div>
      ) : (
        <>
          <div className="reco-header">
            <h2 className="reco-title">💡 Рекомендации</h2>
            <p className="reco-subtitle">Участники с похожими интересами</p>
          </div>

          {activeIntros.length === 0 && doneIntros.length > 0 && (
            <div className="reco-all-done">
              <span>✅</span> Вы рассмотрели все рекомендации
            </div>
          )}

          {activeIntros.map(intro => (
            <IntroCard key={intro.id} intro={intro} onFeedback={feedback} />
          ))}

          {doneIntros.length > 0 && (
            <div className="reco-done-section">
              <p className="reco-done-label">Рассмотрено</p>
              {doneIntros.map(intro => (
                <IntroCardDone key={intro.id} intro={intro} action={done[intro.id]} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ── Карточка знакомого (стиль как участники) ── */
function FriendRow({ friend, onOpenDetail }) {
  const initial = (friend.first_name || "?")[0].toUpperCase();
  const tg = friend.telegram_username;
  return (
    <div
      className="member-row"
      style={{ cursor: "pointer" }}
      onClick={() => onOpenDetail && onOpenDetail(friend.pid)}
    >
      <div style={{ position: "relative", flexShrink: 0 }}>
        <div
          className="member-avatar"
          style={{ background: pidColor(friend.pid), width: 44, height: 44, fontSize: 18 }}
        >
          {initial}
        </div>
      </div>
      <div className="member-row-info">
        <div className="member-row-top">
          <span className="member-row-name">
            {friend.first_name} {friend.last_name}
          </span>
          {friend.answer_score > 0 && (
            <span className="badge-score-sm">⭐{friend.answer_score}</span>
          )}
        </div>
        {friend.profession && (
          <div className="member-row-prof">{friend.profession}</div>
        )}
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 2, flexWrap: "wrap" }}>
          {friend.skills.map(s => (
            <span key={s} className="skill-chip-xs">{s}</span>
          ))}
          {tg && (
            <button
              onClick={e => { e.stopPropagation(); window.open(`https://t.me/${tg}`, "_blank"); }}
              style={{ background: "none", border: "none", padding: 0, cursor: "pointer", fontSize: 11, color: "#2a9d8f", fontWeight: 600 }}
            >
              @{tg}
            </button>
          )}
        </div>
      </div>
      <span style={{ fontSize: 18, color: "#ccc", flexShrink: 0 }}>›</span>
    </div>
  );
}

/* ── Карточка рекомендации ── */
function IntroCard({ intro, onFeedback }) {
  return (
    <div className="reco-card">
      <div className="reco-card-top">
        <div className="reco-avatar">{(intro.first_name || "?")[0].toUpperCase()}</div>
        <div className="reco-info">
          <div className="reco-name">{intro.first_name} {intro.last_name}</div>
          <div className="reco-profession">{intro.profession || "—"}</div>
          <div className="reco-pid">{intro.pid}</div>
        </div>
        <div className="reco-score-badge">{Math.round(intro.score * 100)}%</div>
      </div>
      {intro.skills.length > 0 && (
        <div className="reco-skills">
          {intro.skills.map(s => <span key={s} className="tag-chip reco-skill">{s}</span>)}
        </div>
      )}
      {intro.reason && <p className="reco-reason">💡 {intro.reason}</p>}
      <div className="reco-actions">
        <button className="btn reco-btn-accept" onClick={() => onFeedback(intro.id, "accept")}>
          ✅ Познакомиться
        </button>
        <button className="btn reco-btn-skip" onClick={() => onFeedback(intro.id, "skip")}>
          ✖ Пропустить
        </button>
      </div>
    </div>
  );
}

function IntroCardDone({ intro, action }) {
  return (
    <div className={"reco-card reco-card-done reco-card-" + action}>
      <div className="reco-card-top">
        <div className="reco-avatar reco-avatar-small">
          {(intro.first_name || "?")[0].toUpperCase()}
        </div>
        <div className="reco-info">
          <div className="reco-name">{intro.first_name} {intro.last_name}</div>
          <div className="reco-profession">{intro.profession || "—"}</div>
        </div>
        <div className={"reco-done-badge reco-done-" + action}>
          {action === "accept" ? "✅" : "✖"}
        </div>
      </div>
    </div>
  );
}