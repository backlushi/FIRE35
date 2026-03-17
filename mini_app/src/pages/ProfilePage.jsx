import { useState, useEffect, useRef } from "react";
import api from "../api";
import MonopolyGame from "./MonopolyGame";
import AiBattlePage from "./AiBattlePage";
import AchievementsPage from "./AchievementsPage";

// ── helpers ─────────────────────────────────────────────────
function getDisplayMonth() {
  const now = new Date(), y = now.getFullYear(), mo = now.getMonth() + 1;
  const last = new Date(y, mo, 0).getDate();
  if (now.getDate() >= last) return `${y}-${String(mo).padStart(2,"0")}`;
  return mo === 1 ? `${y-1}-12` : `${y}-${String(mo-1).padStart(2,"0")}`;
}

const FIRE_LEVELS = [
  [0,"Рекрут"],[20,"Наблюдатель"],[40,"Накопитель"],[60,"Инвестор"],
  [80,"Гуру"],[100,"FIRE-рекрут"],[125,"FIRE-наблюдатель"],[150,"FIRE-накопитель"],
  [175,"FIRE-инвестор"],[200,"FIRE-гуру"],[300,"Бабайкин"],
];
function nextLevel(s) {
  for (const [t] of FIRE_LEVELS) if (s < t) { const p = Math.ceil(t-s); return `${p} балл${p===1?"":p<5?"а":"ов"}`; }
  return "максимальный уровень";
}

function FireBar({ label, value, cap, color }) {
  const pct = Math.min((value/cap)*100, 100), exceeded = value > cap;
  return (
    <div className="fire-bar-row">
      <div className="fire-bar-label">{label}</div>
      <div className="fire-bar-track">
        <div className="fire-bar-fill" style={{ width:`${pct}%`, background:color }} />
      </div>
      <div className="fire-bar-val" style={{ color: exceeded ? color : undefined }}>
        {value}{exceeded ? "★" : `/${cap}`}
      </div>
    </div>
  );
}

const TOPICS = [
  { id:1,  title:"Зачем вам соц. сети?" },
  { id:2,  title:"Одного миллиона долларов мало" },
  { id:3,  title:"Первые шаги к финансовой свободе: Зачем, что и как?" },
  { id:4,  title:"Ничего не грядёт, или нас всех пугают?" },
  { id:5,  title:"Одни богатеют, другие нет" },
  { id:6,  title:"Зачем вам миллион, если вы не счастны?" },
  { id:7,  title:"Промпты и нейронки для инвесторов" },
  { id:8,  title:"Интервью: Золотые наручники или дырка от бублика" },
  { id:9,  title:"Бабайкин — Денис Валикарамов" },
  { id:10, title:"Продвижение в Telegram" },
  { id:11, title:"Продвижение на YouTube" },
];

// ── main ────────────────────────────────────────────────────
 export default function ProfilePage({ user, setUser, onGoToChats, unreadChats = 0 }) {
  const [fireScore, setFireScore]   = useState(null);
  const [doneTopic, setDoneTopic]   = useState(new Set());
  const [questions, setQuestions]   = useState([]);
  const [limits, setLimits]         = useState(null);
  const [mySkills, setMySkills]     = useState([]);
  const [catalog, setCatalog]       = useState({});
  const [privacy, setPrivacy]       = useState(null);
  const [recommendation, setRecommendation] = useState("");

  // вопрос-форма
  const [question, setQuestion]     = useState("");
  const [selectedTags, setSelectedTags] = useState([]);
  const [qSent, setQSent]           = useState(false);
  const [qExpandedId, setQExpandedId] = useState(null);
  const [showArchive, setShowArchive] = useState(false);
  const [duplicateData, setDuplicateData] = useState(null);
  const [forcingNew, setForcingNew] = useState(false);
  const [formMsg, setFormMsg]       = useState(null);

  // редактирование
  const [editing, setEditing]       = useState(false);
  const [firstName, setFirstName]   = useState(user?.first_name || "");
  const [profession, setProfession] = useState(user?.profession || "");
  const [customSkill, setCustomSkill] = useState("");
  const [saving, setSaving]         = useState(false);
  const [saveMsg, setSaveMsg]       = useState(null);

  // вкладки
  const [activeTab, setActiveTab]   = useState(() => {
    // Auto-switch to games tab if opened via game invite link
    return new URLSearchParams(window.location.search).get('game') ? 'games' : null;
  });
  const [seenAnswers, setSeenAnswers] = useState(false);

  useEffect(() => {
    api.get("/me/fire-score").then(r => setFireScore(r.data)).catch(()=>{});
    api.get("/progress").then(r => setDoneTopic(new Set(r.data.done))).catch(()=>{});
    api.get("/questions").then(r => setQuestions(r.data)).catch(()=>{});
    api.get("/daily_limits").then(r => setLimits(r.data)).catch(()=>{});
    api.get("/me/skills").then(r => setMySkills(r.data)).catch(()=>{});
    api.get("/skills/catalog").then(r => setCatalog(r.data)).catch(()=>{});
    api.get("/me/privacy").then(r => setPrivacy(r.data)).catch(()=>{});
    api.get("/my/recommendation").then(r => setRecommendation(r.data.text||"")).catch(()=>{});
  }, []);

  // ── actions ──
  async function addSkill(name) {
    if (mySkills.length >= 20) return;
    try {
      const r = await api.post("/me/skills", { skill_name: name });
      if (r.data.status !== "already_exists")
        setMySkills(p => [...p, { id: r.data.id, skill_name: r.data.skill_name }]);
    } catch {}
  }
  async function removeSkill(id) {
    try { await api.delete(`/me/skills/${id}`); setMySkills(p => p.filter(s => s.id !== id)); } catch {}
  }
  async function toggleSkill(skill) {
    const has = mySkills.find(s => s.skill_name === skill);
    has ? removeSkill(has.id) : addSkill(skill);
  }
  async function patchPrivacy(patch) {
    const updated = { ...privacy, ...patch };
    setPrivacy(updated);
    try { await api.patch("/me/privacy", patch); } catch {
      api.get("/me/privacy").then(r => setPrivacy(r.data)).catch(()=>{});
    }
  }
  async function save() {
    setSaving(true); setSaveMsg(null);
    try {
      await api.patch("/me", { first_name: firstName, profession });
      const me = await api.get("/me"); setUser(me.data);
      setSaveMsg("✅ Сохранено");
      setTimeout(() => { setSaveMsg(null); setEditing(false); }, 1500);
    } catch (e) { setSaveMsg("Ошибка: " + (e.response?.data?.detail || e.message)); }
    setSaving(false);
  }
  async function toggleTopic(id) {
    const nd = new Set(doneTopic), was = nd.has(id);
    was ? nd.delete(id) : nd.add(id); setDoneTopic(nd);
    try { await api.post("/progress", { topic_id: id, done: !was }); } catch {}
  }
  async function sendQuestion() {
    if (!question.trim()) return;
    try {
      const r = await api.post("/questions", { question: question.trim(), tags: selectedTags });
      setQuestion(""); setSelectedTags([]);
      if (r.data.duplicate && r.data.duplicate_data) {
        setDuplicateData(r.data.duplicate_data);
      } else { setQSent(true); setTimeout(() => setQSent(false), 4000); }
      api.get("/questions").then(r => setQuestions(r.data)).catch(()=>{});
      api.get("/daily_limits").then(r => setLimits(r.data)).catch(()=>{});
    } catch (e) {
      setFormMsg("Ошибка: " + (e.response?.data?.detail || e.message));
      setTimeout(() => setFormMsg(null), 5000);
    }
  }
  async function forceNewQuestion() {
    if (!duplicateData) return; setForcingNew(true);
    try {
      await api.post(`/questions/${duplicateData.question_id}/force-new`);
      setDuplicateData(null); setQSent(true); setTimeout(() => setQSent(false), 4000);
      api.get("/questions").then(r => setQuestions(r.data)).catch(()=>{});
    } catch (e) { setFormMsg("Ошибка: "+(e.response?.data?.detail||e.message)); }
    setForcingNew(false);
  }
  async function deleteQuestion(qid) {
    try { await api.delete(`/questions/${qid}`); api.get("/questions").then(r => setQuestions(r.data)).catch(()=>{}); }
    catch (e) { setFormMsg("Ошибка: "+(e.response?.data?.detail||e.message)); setTimeout(()=>setFormMsg(null),4000); }
  }
  function openTab(tab) {
    setActiveTab(cur => cur === tab ? null : tab);
    if (tab === "questions") setSeenAnswers(true);
  }
  function openEdit() {
    if (!editing) { setFirstName(user.first_name||""); setProfession(user.profession||""); setSaveMsg(null); }
    setEditing(v => !v);
    if (!editing) setActiveTab(null); // скрыть вкладки при редактировании
  }

  if (!user) return null;

  const mySkillNames   = mySkills.map(s => s.skill_name);
  const doneCount      = doneTopic.size;
  const progressPct    = Math.round((doneCount / TOPICS.length) * 100);
  const answerScore    = user.answer_score || 0;
  const totalAnswers   = user.total_answers || 0;
  const myQWithAnswers = questions.filter(q => q.is_me && q.answers?.length > 0);
  const answersBadge   = !seenAnswers && activeTab !== "questions" ? myQWithAnswers.length : 0;
  // вопросы с новыми ответами (is_useful=null — ещё не оценены)
  const freshAnswerQids = new Set(
    questions.filter(q => q.is_me && q.answers?.some(a => a.is_useful === null)).map(q => q.id)
  );

  return (
    <div className="page pf-page">

      {/* ══ ШАПКА ══ */}
      <div className="pf-header">
        <AvatarImg user={user} onUploaded={() => {}} />
        <div className="pf-header-info">
          <div className="pf-name">{user.first_name || user.pid}</div>
          {user.profession && <div className="pf-profession">{user.profession}</div>}
          {user.telegram_username && <div className="pf-username">@{user.telegram_username}</div>}
          {totalAnswers > 0 && (
            <div className="pf-rating">⭐ {answerScore} <span className="pf-rating-sub">из {totalAnswers}</span></div>
          )}
          <button
            onClick={onGoToChats}
            style={{
              marginTop: 6,
              background: "#2a9d8f", border: "none", color: "#fff",
              borderRadius: 20, padding: "5px 12px",
              fontSize: 12, fontWeight: 600, cursor: "pointer",
              display: "inline-flex", alignItems: "center", gap: 5,
              position: "relative",
            }}
          >
            💬 Знакомства
            {unreadChats > 0 && (
              <span style={{
                background: "#e76f51", color: "#fff",
                borderRadius: "50%", fontSize: 9, fontWeight: 700,
                minWidth: 16, height: 16,
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                padding: "0 3px", marginLeft: 2,
              }}>
                {unreadChats > 9 ? "9+" : unreadChats}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* ══ КНОПКА РЕДАКТИРОВАТЬ ══ */}
      <button className={"pf-edit-btn" + (editing ? " pf-edit-btn--active" : "")} onClick={openEdit}>
        {editing ? "✕ Закрыть редактирование" : "✏️ Редактировать профиль"}
      </button>

      {/* ══ ПАНЕЛЬ РЕДАКТИРОВАНИЯ ══ */}
      {editing && (
        <div className="pf-edit-panel">

          {/* Имя + профессия */}
          <div className="pf-edit-section">
            <p className="pf-edit-q">👤 Имя</p>
            <input className="input" value={firstName} onChange={e=>setFirstName(e.target.value)} placeholder="Как тебя зовут?" />
            <p className="pf-edit-q" style={{marginTop:10}}>💼 Профессия</p>
            <input className="input" value={profession} onChange={e=>setProfession(e.target.value)} placeholder="Врач, предприниматель, программист..." />
          </div>

          {/* Навыки */}
          <div className="pf-edit-section">
            <p className="pf-edit-q">🎯 Выбери свои темы <span className="hint-text">({mySkills.length}/20 выбрано)</span></p>
            <p className="hint-text" style={{marginBottom:10}}>Нажми — подсветится зелёным. Нажми снова — уберёт.</p>
            <div className="skills-catalog">
              {Object.entries(catalog).map(([cat, skills]) => (
                <div key={cat} className="skill-category">
                  <p className="skill-cat-title">{cat}</p>
                  <div className="skill-tags">
                    {skills.map(skill => (
                      <button key={skill}
                        className={"skill-tag" + (mySkillNames.includes(skill) ? " selected" : "")}
                        onClick={() => toggleSkill(skill)}
                        disabled={!mySkillNames.includes(skill) && mySkills.length >= 20}
                      >{skill.replace(/_/g," ")}</button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            {mySkills.length < 20 && (
              <div className="skill-custom-row" style={{marginTop:8}}>
                <input className="input" placeholder="Свой навык..." value={customSkill}
                  onChange={e=>setCustomSkill(e.target.value)}
                  onKeyDown={e=>e.key==="Enter"&&(addSkill(customSkill.trim()),setCustomSkill(""))}
                  style={{flex:1}} />
                <button className="btn btn-secondary"
                  onClick={()=>{addSkill(customSkill.trim());setCustomSkill("");}}
                  disabled={!customSkill.trim()}>+</button>
              </div>
            )}
          </div>

          {/* Рекомендации знакомств */}
          {privacy && (
            <div className="pf-edit-section">
              <p className="pf-edit-q">🤝 Хочешь получать рекомендации знакомств?</p>
              <p className="hint-text" style={{marginBottom:10}}>Раз в 2 недели — 2–3 участника с похожими интересами</p>
              <div className="edit-choice-row">
                <button
                  className={"edit-choice-btn"+(privacy.intro_consent_given&&privacy.intro_receive?" edit-choice-yes":"")}
                  onClick={()=>patchPrivacy({intro_consent_given:true,intro_receive:true})}
                >✅ Да, хочу</button>
                <button
                  className={"edit-choice-btn"+(!privacy.intro_consent_given||!privacy.intro_receive?" edit-choice-no":"")}
                  onClick={()=>patchPrivacy({intro_consent_given:false,intro_receive:false})}
                >✖ Нет</button>
              </div>
              {privacy.intro_consent_given && privacy.intro_receive && (
                <div style={{marginTop:10}}>
                  <p className="hint-text" style={{marginBottom:6}}>Частота:</p>
                  <div className="privacy-freq-btns">
                    {[{v:"weekly",l:"Раз в неделю"},{v:"biweekly",l:"Раз в 2 нед."},{v:"monthly",l:"Раз в месяц"}].map(({v,l})=>(
                      <button key={v}
                        className={"privacy-freq-btn"+(privacy.intro_frequency===v?" active":"")}
                        onClick={()=>patchPrivacy({intro_frequency:v})}
                      >{l}</button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Вопросы */}
          {privacy && (
            <div className="pf-edit-section">
              <p className="pf-edit-q">💬 Какие вопросы получать?</p>
              <div className="edit-choice-row">
                <button
                  className={"edit-choice-btn"+(privacy.question_visibility==="skills_only"?" edit-choice-yes":"")}
                  onClick={()=>patchPrivacy({question_visibility:"skills_only"})}
                >🎯 По моим темам</button>
                <button
                  className={"edit-choice-btn"+(privacy.question_visibility==="all"?" edit-choice-yes":"")}
                  onClick={()=>patchPrivacy({question_visibility:"all"})}
                >🌐 Все вопросы</button>
              </div>
            </div>
          )}

          {/* Сохранить */}
          <div className="pf-edit-actions">
            <button className="btn pf-save-btn" onClick={save} disabled={saving}>
              {saving ? "Сохраняю..." : "💾 Сохранить изменения"}
            </button>
            <button className="btn btn-secondary" onClick={()=>setEditing(false)}>Назад</button>
          </div>
          {saveMsg && <p className={"msg "+(saveMsg.startsWith("Ошибка")?"error-text":"success-text")}>{saveMsg}</p>}
        </div>
      )}

      {/* ══ ОСНОВНОЙ БЛОК: ВКЛАДКИ + ДАШБОРД ══ */}
      {!editing && (
        <div className="pf-main">

          {/* Левый столбец — кнопки вкладок */}
          <div className="pf-tab-col">
            <button className={"pf-tab-btn"+(activeTab==="skills"?" pf-tab-btn--active":"")} onClick={()=>openTab("skills")}>
              🎯 Мои навыки
            </button>
            <button className={"pf-tab-btn"+(activeTab==="questions"?" pf-tab-btn--active":"")} onClick={()=>openTab("questions")}>
              💬 Мои вопросы
              {answersBadge > 0 && <span className="pf-tab-badge">{answersBadge}</span>}
            </button>
            <button className={"pf-tab-btn"+(activeTab==="progress"?" pf-tab-btn--active":"")} onClick={()=>openTab("progress")}>
              📚 Прогресс
            </button>
            <button className={"pf-tab-btn"+(activeTab==="achievements"?" pf-tab-btn--active":"")} onClick={()=>openTab("achievements")}>
              🏆 Достижения
            </button>
            <button className={"pf-tab-btn"+(activeTab==="games"?" pf-tab-btn--active":"")} onClick={()=>openTab("games")}>
              🎲 Мои игры
            </button>
          </div>

          {/* Правый столбец — FIRE Score дашборд */}
          <div className="pf-dash-col">
            {fireScore ? (
              <div className="pf-dash">
                <div className="pf-dash-top">
                  <div className="pf-dash-level">{fireScore.level}</div>
                  <div className="pf-dash-total">{fireScore.total}</div>
                </div>
                {fireScore.percentile != null && (
                  <div style={{
                    fontSize: 11, color: "#2a9d8f", fontWeight: 600,
                    background: "#e8f5e9", borderRadius: 8, padding: "3px 8px",
                    marginBottom: 6, textAlign: "center",
                  }}>
                    🏅 Ты лучше {fireScore.percentile}% участников клуба
                  </div>
                )}
                <div className="fire-score-bars">
                  <FireBar label="Помощь"     value={fireScore.help}       cap={fireScore.help_cap}       color="#2a9d8f" />
                  <FireBar label="Обучение"   value={fireScore.learning}   cap={fireScore.learning_cap}   color="#e9c46a" />
                  <FireBar label="Дисциплина" value={fireScore.discipline} cap={fireScore.discipline_cap} color="#f4a261" />
                  <FireBar label="Финансы"    value={fireScore.finance}    cap={fireScore.finance_cap}    color="#e76f51" />
                </div>
                <div className="pf-dash-next">
                  {fireScore.total < 100 ? `До следующего: ${nextLevel(fireScore.total)}` : "🔥 FIRE-элита!"}
                </div>
              </div>
            ) : (
              <div className="pf-dash pf-dash-empty">
                <p className="hint-text" style={{textAlign:"center"}}>Заполни профиль и отчёт для FIRE Score</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ══ КОНТЕНТ ВКЛАДОК ══ */}

      {/* 🎯 Навыки */}
      {!editing && activeTab === "skills" && (
        <div className="card pf-tab-content">
          {mySkills.length === 0 ? (
            <p className="hint-text">Навыки не выбраны. Нажми «Редактировать профиль» чтобы добавить.</p>
          ) : (
            <div className="pf-skills-list">
              {mySkills.map(s => (
                <span key={s.id} className="pf-skill-chip">{s.skill_name.replace(/_/g," ")}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 💬 Вопросы */}
      {!editing && activeTab === "questions" && (
        <div className="card pf-tab-content">
          {/* Форма вопроса */}
          <p className="pf-edit-q" style={{marginBottom:6}}>Задать вопрос участникам</p>
          {limits && (
            <div className="limits-bar">
              <span className="limits-text">Осталось сегодня: <b>{limits.remaining}</b> из {limits.total_limit}</span>
              {limits.speed_bonus > 0 && <span className="limits-bonus">+{limits.speed_bonus} 🔥</span>}
            </div>
          )}
          <div className="skill-tags" style={{margin:"8px 0"}}>
            {mySkillNames.slice(0,8).map(skill => (
              <button key={skill}
                className={"skill-tag"+(selectedTags.includes(skill)?" selected":"")}
                onClick={()=>setSelectedTags(p=>p.includes(skill)?p.filter(t=>t!==skill):p.length<3?[...p,skill]:p)}
              >#{skill.replace(/_/g," ")}</button>
            ))}
          </div>
          <textarea className="input textarea" rows={3} maxLength={500}
            value={question} onChange={e=>setQuestion(e.target.value)}
            placeholder="Ваш вопрос о финансах, инвестициях, FIRE..." />
          <p className="hint-text" style={{textAlign:"right"}}>{question.length}/500</p>
          {formMsg && <p className="error-text">{formMsg}</p>}
          {qSent
            ? <p className="success-text">Вопрос отправлен!</p>
            : <button className="btn btn-primary btn-full" style={{marginTop:8}}
                onClick={sendQuestion} disabled={!question.trim()||(limits&&limits.remaining<=0)}>
                {limits&&limits.remaining<=0?"Лимит исчерпан":"Отправить вопрос"}
              </button>
          }

          {/* Дубликат */}
          {duplicateData && (
            <div className="dup-card" style={{marginTop:12}}>
              <div className="dup-header"><span>🤖</span><span className="dup-title">Похожий вопрос уже задавали!</span></div>
              <p className="dup-orig"><em>«{duplicateData.original_question.slice(0,120)}»</em></p>
              {duplicateData.expert_username && (
                <p className="dup-expert">@{duplicateData.expert_username}
                  {duplicateData.expert_score>0&&` ⭐ ${duplicateData.expert_score}`}
                </p>
              )}
              <p className="dup-answer">{duplicateData.answer}</p>
              <div className="dup-actions">
                <button className="btn btn-primary" onClick={()=>setDuplicateData(null)}>✅ Помогло</button>
                <button className="btn btn-secondary" onClick={forceNewQuestion} disabled={forcingNew}>
                  {forcingNew?"Отправляю...":"🔄 Задать всё равно"}
                </button>
              </div>
            </div>
          )}

          {/* Мои вопросы */}
          {questions.filter(q=>q.is_me).length > 0 && (
            <div style={{marginTop:16}}>
              <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:8}}>
                <p className="pf-edit-q" style={{margin:0}}>Мои вопросы</p>
                <button
                  title="Архив знаний"
                  onClick={()=>setShowArchive(v=>!v)}
                  style={{background:"none",border:"none",cursor:"pointer",fontSize:18,padding:"0 2px",opacity:showArchive?1:0.45}}
                >📚</button>
              </div>
              {showArchive && (
                <div style={{marginBottom:12}}>
                  {questions.filter(q=>q.is_me && q.answers?.some(a=>a.is_useful)).length === 0
                    ? <p style={{fontSize:13,color:"var(--text-secondary)",margin:0}}>Принятых ответов пока нет</p>
                    : questions.filter(q=>q.is_me && q.answers?.some(a=>a.is_useful)).map(q=>(
                      <div key={q.id} className="dq-card" style={{opacity:0.8}}>
                        <div className="dq-header">
                          <div className="dq-meta"><span className="dq-date">{q.created_at}</span></div>
                          <span className="dq-status">✅</span>
                        </div>
                        <div className="dq-preview">{q.question}</div>
                        <div className="dq-body" style={{display:"block"}}>
                          {q.answers.filter(a=>a.is_useful).map((a,i)=>(
                            <div key={i} className="dq-answer dq-answer-accepted">
                              <div className="dq-accepted-label">✅ Принятый ответ</div>
                              <div className="dq-answer-meta">
                                <span className="dq-answer-author">{a.expert_name||"Анар"}</span>
                              </div>
                              <div className="dq-answer-text">{a.answer}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))
                  }
                </div>
              )}
              {questions.filter(q=>q.is_me).map(q => {
                const isOpen    = qExpandedId === q.id;
                const hasFresh  = freshAnswerQids.has(q.id);
                const hasUseful = q.answers?.some(a=>a.is_useful);
                const ansCount  = q.answers?.length || 0;
                return (
                  <div key={q.id} className={"dq-card"+(isOpen?" dq-card-open":"")+(hasFresh?" dq-card-fresh":"")}>
                    <div className="dq-header" onClick={()=>setQExpandedId(id=>id===q.id?null:q.id)}>
                      <div className="dq-meta">
                        <span className="dq-date">{q.created_at}</span>
                        {hasFresh && <span className="dq-new-badge">новый ответ</span>}
                        {q.tags?.map(t=><span key={t} className="tag-chip dq-tag">{t}</span>)}
                      </div>
                      <div className="dq-right">
                        <button className="btn-delete-q" onClick={e=>{e.stopPropagation();deleteQuestion(q.id);}} title="Удалить">🗑</button>
                        <span className="dq-status">{hasUseful?"✅":ansCount>0?`💬 ${ansCount}`:"⏳"}</span>
                        <span className="dq-chevron">{isOpen?"▲":"▼"}</span>
                      </div>
                    </div>
                    <div className="dq-preview">{q.question}</div>
                    {isOpen && (
                      <div className="dq-body">
                        {ansCount===0 ? <div className="dq-no-answers">Пока нет ответов</div>
                          : q.answers.map((a,i)=>(
                            <div key={i} className={"dq-answer"+(a.is_useful?" dq-answer-accepted":"")}>
                              {a.is_useful && <div className="dq-accepted-label">✅ Принятый ответ</div>}
                              <div className="dq-answer-meta">
                                <span className="dq-answer-author">{a.expert_username?`@${a.expert_username}`:(a.expert_name||"Анар")}</span>
                                {a.expert_score>0&&<span className="badge-score-sm">⭐{a.expert_score}</span>}
                                <span className="dq-answer-date">{a.created_at}</span>
                              </div>
                              <div className="dq-answer-text">{a.answer}</div>
                            </div>
                          ))
                        }
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* 📚 Прогресс */}
      {!editing && activeTab === "progress" && (
        <div className="card pf-tab-content">
          <div className="progress-bar-wrap" style={{marginBottom:6}}>
            <div className="progress-bar-fill" style={{width:`${progressPct}%`}} />
          </div>
          <p className="progress-label">{progressPct}% · {doneCount}/{TOPICS.length} тем</p>
          <div className="topics-list">
            {TOPICS.map(t=>(
              <button key={t.id} className={"topic-row "+(doneTopic.has(t.id)?"done":"")} onClick={()=>toggleTopic(t.id)}>
                <span className="topic-check">{doneTopic.has(t.id)?"✅":"⬜"}</span>
                <span className="topic-title">{t.title}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 🏆 Достижения */}
      {!editing && activeTab === "achievements" && (
        <div className="pf-tab-content">
          <AchievementsPage user={user} filterPid={user.pid} />
        </div>
      )}

      {/* 🎲 Мои игры */}
      {!editing && activeTab === "games" && (
        <div className="pf-tab-content">
          <GamesSection user={user} />
        </div>
      )}

      {/* ── Рекомендация Анара (если есть) ── */}
      {!editing && recommendation && !activeTab && (
        <div className="card recommendation-card">
          <p className="field-label" style={{marginBottom:6}}>⭐ Рекомендация Анара</p>
          <p className="recommendation-text">{recommendation}</p>
        </div>
      )}

      <div className="docs-footer">
        <a href="/fire35-app/terms.html" target="_blank" rel="noopener">Соглашение</a>
        <span className="docs-sep">·</span>
        <a href="/fire35-app/privacy.html" target="_blank" rel="noopener">Конфиденциальность</a>
      </div>
    </div>
  );
}

function GamesSection({ user }) {
  const [game, setGame] = useState("monopoly"); // "monopoly" | "ai-battle"
  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button
          className={"btn" + (game === "monopoly" ? " btn-primary" : "")}
          style={{ flex: 1, fontSize: 13 }}
          onClick={() => setGame("monopoly")}
        >
          🎲 Монополия
        </button>
        <button
          className={"btn" + (game === "ai-battle" ? " btn-primary" : "")}
          style={{ flex: 1, fontSize: 13 }}
          onClick={() => setGame("ai-battle")}
        >
          🤖 AI-Тренажёр
        </button>
      </div>
      {game === "monopoly" && <MonopolyGame user={user} />}
      {game === "ai-battle" && <AiBattlePage user={user} />}
    </div>
  );
}

const API_BASE = "https://fire35club.duckdns.org/fire35";
function AvatarImg({ user, onUploaded }) {
  const [broken, setBroken] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [cacheBust, setCacheBust] = useState(Date.now());
  const inputRef = useRef(null);
  const name = user.first_name || user.pid;

  async function handleFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await api.post("/me/avatar", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setBroken(false);
      setCacheBust(Date.now());
      onUploaded?.();
    } catch {}
    setUploading(false);
  }

  return (
    <div style={{ position: "relative", flexShrink: 0 }}>
      {!broken
        ? <img className="avatar large avatar-photo"
            src={`${API_BASE}/avatar/${user.pid}?t=${cacheBust}`}
            alt={name} onError={() => setBroken(true)} />
        : <div className="avatar large">{name[0].toUpperCase()}</div>
      }
      <input ref={inputRef} type="file" accept="image/*" style={{ display: "none" }} onChange={handleFile} />
      <button
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
        title="Сменить фото"
        style={{
          position: "absolute", bottom: 0, right: 0,
          width: 22, height: 22, borderRadius: "50%",
          background: uploading ? "#aaa" : "#2a9d8f",
          border: "2px solid #fff", color: "#fff",
          fontSize: 11, cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}
      >{uploading ? "…" : "📷"}</button>
    </div>
  );
}
