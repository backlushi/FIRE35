"""
FIRE35 — FastAPI backend
Port 8001, контейнер fire35_backend
"""
import os
import hmac
import hashlib
import urllib.parse
import httpx
from datetime import datetime, timedelta
from typing import Optional, List

import jwt
from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, text

import uuid
import json
import shutil
import numpy as np
from pathlib import Path
# anthropic не используется — переключились на Groq
from database import (User, UserSkill, Report, ContactRequest, FcmToken,
                      ClubQuestion, QuestionAnswer, AnswerVote, Recommendation,
                      QuestionEmbedding, QuestionDuplicate,
                      Introduction, IntroFeedback, GameSession,
                      AiBattleChallenge, AiBattleSubmission,
                      TrainerAttempt,
                      Achievement, AchievementLike,
                      Message,
                      Season, Team, TeamMember,
                      Challenge, ChallengeSubmission,
                      UserTrust, ReportValidation, UserEmbedding,
                      get_db, init_db)

# ─── config ───────────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "fire35_jwt_secret_change_me")
JWT_EXPIRE_DAYS = 30
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "fire35_admin_secret")
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")
BOT_TOKEN = os.getenv("FIRE35_BOT_TOKEN", "8752856976:AAEIqm7ZLBQx5kV7hGcnsxOqnCHM-5WIw1I")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="FIRE35 API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

# ─── Uploads ──────────────────────────────────────────────
UPLOAD_DIR = Path("/root/fire35/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

ALLOWED_MEDIA = {
    "image/jpeg": ("photo", ".jpg"),
    "image/png":  ("photo", ".png"),
    "image/webp": ("photo", ".webp"),
    "audio/mpeg": ("audio", ".mp3"),
    "audio/ogg":  ("audio", ".ogg"),
    "audio/wav":  ("audio", ".wav"),
    "audio/mp4":  ("audio", ".m4a"),
}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB


# ─── Справочник навыков ────────────────────────────────────
SKILLS_CATALOG = {
    "💰 Финансы": [
        "инвестиции", "акции", "облигации", "etf", "крипто", "недвижимость",
        "дивиденды", "пассивный_доход", "бюджет", "налоги", "трейдинг", "ипотека",
        "страхование", "пфр",
    ],
    "🏢 Бизнес": [
        "предпринимательство", "стартап", "маркетинг", "продажи", "hr",
        "консалтинг", "бухгалтерия", "менеджмент", "франшиза", "бизнес_аналитика",
        "переговоры", "финансовый_анализ",
    ],
    "💻 Технологии": [
        "python", "javascript", "react", "ai", "нейросети", "data_science",
        "devops", "кибербезопасность", "веб_разработка", "мобильная_разработка",
        "автоматизация", "sql", "excel", "tableau",
    ],
    "📱 Контент": [
        "smm", "seo", "копирайтинг", "youtube", "telegram", "видеомонтаж",
        "дизайн", "фото", "подкасты", "reels",
    ],
    "🎯 Карьера": [
        "нетворкинг", "публичные_выступления", "коучинг", "тайм_менеджмент",
        "лидерство", "управление_командой",
    ],
    "🌱 Образ жизни": [
        "медицина", "психология", "фитнес", "питание", "английский",
        "иностранные_языки",
    ],
    "🔨 Профессии": [
        "строительство", "архитектура", "юриспруденция", "образование",
        "логистика", "производство",
    ],
    "🛒 E-commerce": [
        "e_commerce", "wildberries", "ozon", "dropshipping", "маркетплейсы",
    ],
}

# Плоский список всех навыков для валидации
ALL_SKILLS = [s for cat in SKILLS_CATALOG.values() for s in cat]


# ─── startup ──────────────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()


# ─── helpers ──────────────────────────────────────────────
async def send_push(token: str, title: str, body: str, data: dict = None):
    """Отправить FCM push через Legacy HTTP API."""
    if not FCM_SERVER_KEY or not token:
        return
    payload = {
        "to": token,
        "notification": {"title": title, "body": body, "sound": "default"},
        "data": data or {},
        "priority": "high",
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                "https://fcm.googleapis.com/fcm/send",
                headers={
                    "Authorization": f"key={FCM_SERVER_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except Exception as e:
        print(f"[FCM] Push error: {e}")


def make_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def current_month() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def normalize_skill(s: str) -> str:
    """Привести навык к нормализованному виду."""
    return s.strip().lower().replace(" ", "_").replace("-", "_")


# ─── FIRE Score ────────────────────────────────────────────────────────────────

FIRE_LEVELS = [
    (0,   "Рекрут"),
    (20,  "Наблюдатель"),
    (40,  "Накопитель"),
    (60,  "Инвестор"),
    (80,  "Гуру"),
    (100, "FIRE-рекрут"),
    (125, "FIRE-наблюдатель"),
    (150, "FIRE-накопитель"),
    (175, "FIRE-инвестор"),
    (200, "FIRE-гуру"),
    (300, "Бабайкин"),
]


def calc_fire_level(score: float) -> str:
    level = "Рекрут"
    for threshold, name in FIRE_LEVELS:
        if score >= threshold:
            level = name
        else:
            break
    return level


def calc_fire_score(user, db: Session) -> dict:
    """Считает FIRE Score из верифицируемых действий внутри продукта."""
    # 1. Помощь клубу: 0.25 за каждый принятый ответ, без потолка (растёт со временем)
    accepted_count = db.query(QuestionAnswer).filter(
        QuestionAnswer.expert_user_id == user.id,
        QuestionAnswer.is_useful == True,
    ).count()
    help_score = round(accepted_count * 0.25, 2)

    # 2. Обучение: 3 за каждую пройденную тему, потолок 30
    topics_done_count = len([t for t in (user.topics_done or "").split(",") if t.strip()])
    learning_score = min(topics_done_count * 3, 30)

    # 3. Дисциплина: 3 за каждый отчёт, +2 бонус за streak ≥4 месяцев, потолок 20
    reports_all = (
        db.query(Report)
        .filter(Report.user_id == user.id)
        .order_by(Report.month.asc())
        .all()
    )
    discipline_base = min(len(reports_all) * 3, 18)
    # Streak: ищем 4+ отчёта подряд по месяцам
    streak_bonus = 0
    if len(reports_all) >= 4:
        months = sorted(r.month for r in reports_all)
        max_streak = 1
        cur_streak = 1
        for i in range(1, len(months)):
            from datetime import date
            y1, m1 = map(int, months[i-1].split("-"))
            y2, m2 = map(int, months[i].split("-"))
            if (y2 * 12 + m2) - (y1 * 12 + m1) == 1:
                cur_streak += 1
                max_streak = max(max_streak, cur_streak)
            else:
                cur_streak = 1
        if max_streak >= 4:
            streak_bonus = 2
    discipline_score = min(discipline_base + streak_bonus, 20)

    # 4. Финансы: из последнего отчёта, потолок 10
    latest_report = (
        db.query(Report)
        .filter(Report.user_id == user.id)
        .order_by(Report.month.desc())
        .first()
    )
    finance_score = 0
    if latest_report:
        if latest_report.income_gt_expense:
            finance_score += 3   # доход > расходы
        if latest_report.budget_yes:
            finance_score += 3   # веду бюджет
        if (latest_report.invest_pct or 0) > 0:
            finance_score += 4   # инвестирую
    finance_score = min(finance_score, 10)

    total = round(help_score + learning_score + discipline_score + finance_score, 1)

    return {
        "total":      total,
        "level":      calc_fire_level(total),
        "help":       help_score,
        "learning":   learning_score,
        "discipline": discipline_score,
        "finance":    finance_score,
        # мета для UI
        "help_cap":       40,
        "learning_cap":   30,
        "discipline_cap": 20,
        "finance_cap":    10,
        "accepted_answers": accepted_count,
        "streak_bonus":     streak_bonus,
    }


def calc_daily_limits(user: User, db: Session) -> dict:
    """Рассчитать лимиты вопросов на сегодня."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    month_ago = datetime.utcnow() - timedelta(days=30)

    # Полезные ответы за 30 дней
    useful_30d = db.query(QuestionAnswer).filter(
        QuestionAnswer.expert_user_id == user.id,
        QuestionAnswer.is_useful == True,
        QuestionAnswer.created_at >= month_ago,
    ).count()

    # Базовый лимит по уровню
    if useful_30d >= 10:
        base = 10
    elif useful_30d >= 6:
        base = 7
    elif useful_30d >= 3:
        base = 5
    else:
        base = 3

    # Бонус за быстрые ответы сегодня (< 60 мин)
    speed_bonus = db.query(QuestionAnswer).filter(
        QuestionAnswer.expert_user_id == user.id,
        QuestionAnswer.response_time_minutes.isnot(None),
        QuestionAnswer.response_time_minutes <= 60,
        QuestionAnswer.created_at >= today_start,
    ).count()

    total_limit = base + speed_bonus

    # Вопросов задано сегодня
    asked_today = db.query(ClubQuestion).filter(
        ClubQuestion.user_id == user.id,
        ClubQuestion.created_at >= today_start,
    ).count()

    return {
        "base_limit": base,
        "useful_answers_30d": useful_30d,
        "speed_bonus": speed_bonus,
        "total_limit": total_limit,
        "asked_today": asked_today,
        "remaining": max(0, total_limit - asked_today),
    }


async def tg_send(tg_id: str, text: str, reply_markup: dict = None):
    """Отправить сообщение через бота."""
    payload = {"chat_id": tg_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json=payload,
            )
            if not r.is_success or not r.json().get("ok"):
                print(f"[TG] Send failed tg_id={tg_id}: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[TG] Send error tg_id={tg_id}: {e}")


# ─── Embedding model (lazy load) ────────────────────────
_embed_model = None

def get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _embed_model


def embed_text(text: str) -> bytes:
    model = get_embed_model()
    emb = model.encode(text, normalize_embeddings=True)
    return emb.astype(np.float32).tobytes()


def find_similar_questions(new_emb_bytes: bytes, db: Session,
                            threshold: float = 0.85,
                            exclude_question_id: int = None) -> list:
    """
    Ищет вопросы с cosine similarity >= threshold среди вопросов,
    у которых есть хотя бы один ответ с is_useful=True или is_useful не None.
    Возвращает список dict: {question_id, similarity, best_answer, question_text, expert_username, expert_score}
    """
    new_emb = np.frombuffer(new_emb_bytes, dtype=np.float32)

    # Берём вопросы у которых есть ответы (полезные или любые оцененные)
    answered_qids = {
        row[0] for row in
        db.query(QuestionAnswer.question_id)
        .filter(QuestionAnswer.is_useful.isnot(None))
        .distinct()
        .all()
    }
    if not answered_qids:
        return []

    embeddings = (
        db.query(QuestionEmbedding)
        .filter(QuestionEmbedding.question_id.in_(answered_qids))
        .all()
    )

    results = []
    for qe in embeddings:
        if exclude_question_id and qe.question_id == exclude_question_id:
            continue
        stored = np.frombuffer(qe.embedding, dtype=np.float32)
        sim = float(np.dot(new_emb, stored))   # embeddings normalized → cosine = dot
        if sim >= threshold:
            results.append({"question_id": qe.question_id, "similarity": round(sim, 4)})

    if not results:
        return []

    # Сортируем по убыванию схожести, берём топ-3
    results.sort(key=lambda x: x["similarity"], reverse=True)
    top3 = results[:3]

    # Обогащаем данными о лучшем ответе
    enriched = []
    for r in top3:
        q = db.query(ClubQuestion).filter(ClubQuestion.id == r["question_id"]).first()
        if not q:
            continue
        # Лучший ответ: сначала полезные (is_useful=True), потом по score эксперта, потом свежий
        useful = [a for a in q.answers if a.is_useful == True]
        any_ans = [a for a in q.answers if a.is_useful is not None]
        candidates = useful if useful else any_ans
        if not candidates:
            continue
        # Сортируем по answer_score эксперта desc, потом по дате desc
        def sort_key(a):
            score = (a.expert.answer_score or 0) if a.expert else 0
            return (score, a.created_at)
        best = sorted(candidates, key=sort_key, reverse=True)[0]
        enriched.append({
            "question_id": q.id,
            "question_text": q.question,
            "similarity": r["similarity"],
            "answer_id": best.id,
            "answer_text": best.answer,
            "expert_username": best.expert.telegram_username if best.expert else None,
            "expert_score": best.expert.answer_score if best.expert else 0,
            "answered_days_ago": (datetime.utcnow() - best.created_at).days,
        })

    return enriched


async def notify_experts(question: ClubQuestion, db: Session):
    """Найти экспертов с совпадающими навыками и разослать уведомления."""
    if not question.tags:
        return
    tags = [t.strip() for t in question.tags.split(",") if t.strip()]
    if not tags:
        return

    experts = (
        db.query(User)
        .join(UserSkill, UserSkill.user_id == User.id)
        .filter(
            UserSkill.skill_name.in_(tags),
            User.id != question.user_id,
            User.telegram_id.isnot(None),
        )
        .distinct()
        .all()
    )

    tags_display = ", ".join(f"#{t}" for t in tags)
    author_name = f"@{question.user.telegram_username}" if question.user.telegram_username else "участник"

    keyboard = {
        "inline_keyboard": [[
            {"text": "✍️ Ответить",      "callback_data": f"qa_reply_{question.id}"},
            {"text": "⏭ Пропустить",    "callback_data": f"qa_skip_{question.id}"},
            {"text": "🚫 Не моя тема",  "callback_data": f"qa_notmine_{question.id}"},
        ]]
    }

    msg = (
        f"❓ <b>Вопрос по твоей теме</b>\n\n"
        f"<i>{question.question}</i>\n\n"
        f"🏷 {tags_display}\n\n"
        f"Ответь в течение часа — получишь +1 вопрос сегодня 🔥"
    )

    for expert in experts:
        await tg_send(expert.telegram_id, msg, reply_markup=keyboard)


# ─── schemas ──────────────────────────────────────────────
class LoginRequest(BaseModel):
    pid: str
    password: Optional[str] = None


class ReportCreate(BaseModel):
    month: Optional[str] = None
    budget_yes: bool
    income_gt_expense: bool
    savings_pct: float
    invest_pct: float

    @field_validator("savings_pct", "invest_pct")
    @classmethod
    def pct_range(cls, v):
        if not (0 <= v <= 100):
            raise ValueError("Процент должен быть от 0 до 100")
        return v


class UserProfile(BaseModel):
    id: int
    pid: str
    first_name: Optional[str]
    last_name: Optional[str]
    username: Optional[str]
    telegram_username: Optional[str]
    profession: Optional[str]
    skills: Optional[str]
    answer_score: Optional[int] = 0
    total_answers: Optional[int] = 0
    onboarding_done: Optional[bool] = False

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    telegram_username: Optional[str] = None
    first_name: Optional[str] = None
    skills: Optional[str] = None
    profession: Optional[str] = None


class RatingEntry(BaseModel):
    rank: int
    pid: str
    savings_pct: float
    invest_pct: bool
    delta_pct: Optional[float]
    is_me: bool


class DirectoryProfession(BaseModel):
    profession: str
    count: int
    members: List[dict]


class TgLoginRequest(BaseModel):
    telegram_username: str  # без @


class AdminSetPassword(BaseModel):
    pid: str
    new_password: str
    admin_token: str


class FcmTokenRequest(BaseModel):
    token: str


class ContactRequestOut(BaseModel):
    id: int
    from_pid: str
    from_telegram: Optional[str]
    created_at: str


class QuestionCreate(BaseModel):
    question: str
    tags: Optional[List[str]] = []


class SkillAddRequest(BaseModel):
    skill_name: str


class RateAnswerRequest(BaseModel):
    is_useful: bool  # True = полезно, False = не очень / бесполезно


class AnswerCreate(BaseModel):
    answer: str


# ─── routes ───────────────────────────────────────────────

@app.get("/")
def root():
    return {"project": "FIRE35", "status": "ok", "version": "3.0"}


# ── Auth ──────────────────────────────────────────────────

@app.post("/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    pid = body.pid.strip().upper()
    user = db.query(User).filter(User.pid == pid).first()
    if not user:
        raise HTTPException(status_code=401, detail="Участник не найден")
    # Если пароль задан — проверяем; если нет — пускаем по PID без пароля
    if user.password_hash and body.password:
        if not pwd_ctx.verify(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Неверный пароль")
    token = make_token(user.id)
    return {"access_token": token, "token_type": "bearer", "pid": user.pid}


@app.post("/auth/webapp")
def login_webapp(request: dict, db: Session = Depends(get_db)):
    """
    Mini App auth: принимает { init_data: "..." } из window.Telegram.WebApp.initData,
    верифицирует HMAC-SHA256, находит пользователя по telegram_username, возвращает JWT.
    """
    import json
    init_data = request.get("init_data", "")
    if not init_data:
        raise HTTPException(status_code=400, detail="init_data required")

    params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = params.pop("hash", "")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(status_code=401, detail="Invalid initData signature")

    user_json = params.get("user", "{}")
    try:
        tg_user = json.loads(user_json)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user data")

    username = tg_user.get("username", "").lower()
    tg_id = tg_user.get("id")

    user = None
    if username:
        user = db.query(User).filter(User.telegram_username == username).first()
    if not user and tg_id:
        user = db.query(User).filter(User.telegram_id == str(tg_id)).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Telegram аккаунт не найден в клубе. Обратитесь к администратору."
        )

    changed = False
    if tg_id and not user.telegram_id:
        user.telegram_id = str(tg_id)
        changed = True
    if not user.first_name and tg_user.get("first_name"):
        user.first_name = tg_user.get("first_name", "")
        changed = True
    if changed:
        db.commit()

    token = make_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "pid": user.pid,
        "first_name": user.first_name or tg_user.get("first_name", ""),
        "consent_given": bool(user.consent_given),
    }


@app.post("/auth/login-tg")
def login_tg(body: TgLoginRequest, db: Session = Depends(get_db)):
    uname = body.telegram_username.strip().lstrip("@").lower()
    user = db.query(User).filter(User.telegram_username == uname).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Telegram username не найден. Обратитесь к администратору."
        )
    token = make_token(user.id)
    return {"access_token": token, "token_type": "bearer", "pid": user.pid}


@app.post("/admin/set-password")
def admin_set_password(body: AdminSetPassword, db: Session = Depends(get_db)):
    if body.admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    pid = body.pid.strip().upper()
    user = db.query(User).filter(User.pid == pid).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"{pid} не найден")
    user.password_hash = pwd_ctx.hash(body.new_password)
    db.commit()
    return {"status": "ok", "pid": pid}


@app.post("/admin/set-password-all")
def admin_set_password_all(
    new_password: str,
    admin_token: str,
    db: Session = Depends(get_db),
):
    if admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    hashed = pwd_ctx.hash(new_password)
    users = db.query(User).filter(User.password_hash.is_(None)).all()
    for u in users:
        u.password_hash = hashed
    db.commit()
    return {"status": "ok", "updated": len(users)}


# ── Profile ───────────────────────────────────────────────

AVATAR_DIR = "/root/fire35/avatars"
os.makedirs(AVATAR_DIR, exist_ok=True)

@app.get("/avatar/{pid}")
def get_avatar(pid: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.pid == pid.upper()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Сначала — загруженное пользователем фото
    local_path = os.path.join(AVATAR_DIR, f"{pid.upper()}.jpg")
    if os.path.exists(local_path):
        with open(local_path, "rb") as f:
            return Response(content=f.read(), media_type="image/jpeg")
    # Fallback — Telegram avatar_file_id
    if not user.avatar_file_id:
        raise HTTPException(status_code=404, detail="No avatar")
    try:
        r = httpx.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
            params={"file_id": user.avatar_file_id},
            timeout=10,
        )
        file_path = r.json()["result"]["file_path"]
        img = httpx.get(
            f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}",
            timeout=10,
        )
        return Response(content=img.content, media_type="image/jpeg")
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch avatar")


@app.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
):
    """Загрузить свой аватар (JPEG/PNG, макс 2 МБ)."""
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(400, "Только JPEG/PNG/WEBP")
    data = await file.read()
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(400, "Файл слишком большой (макс 2 МБ)")
    os.makedirs(AVATAR_DIR, exist_ok=True)
    path = os.path.join(AVATAR_DIR, f"{user.pid}.jpg")
    with open(path, "wb") as f:
        f.write(data)
    return {"status": "ok"}


@app.post("/consent")
def give_consent(user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.consent_given = True
    db.commit()
    return {"status": "ok"}


@app.get("/me", response_model=UserProfile)
def get_me(user: User = Depends(current_user)):
    return user


@app.get("/me/fire-score")
def get_fire_score(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Детальный FIRE Score + ранг текущего пользователя."""
    score_data = calc_fire_score(user, db)
    my_total = score_data["total"]

    # Быстрый ранг: сколько участников с FIRE score > моего (батч по accepted answers)
    accepted_rows = db.execute(text("""
        SELECT u.id,
               COALESCE(acc.cnt,0)*0.25 +
               COALESCE(rep.cnt,0)*3 AS approx_score
        FROM users u
        LEFT JOIN (
            SELECT expert_user_id, COUNT(*) cnt FROM question_answers
            WHERE is_useful=1 GROUP BY expert_user_id
        ) acc ON acc.expert_user_id = u.id
        LEFT JOIN (
            SELECT user_id, COUNT(*) cnt FROM reports GROUP BY user_id
        ) rep ON rep.user_id = u.id
        WHERE u.pid IS NOT NULL
    """)).fetchall()

    # Точный процентиль — только реально активные пользователи (заходили хотя бы раз)
    all_users = db.query(User).filter(
        User.pid.isnot(None),
        User.consent_given == True,
        User.last_seen.isnot(None),
    ).all()

    # Считаем в одном проходе — избегаем floating-point расхождений
    scores_map = {}
    for u in all_users:
        try:
            scores_map[u.id] = calc_fire_score(u, db)["total"]
        except Exception:
            scores_map[u.id] = 0

    # Если текущий юзер по какой-то причине не попал — добавляем
    if user.id not in scores_map:
        scores_map[user.id] = my_total

    my_score_actual = scores_map[user.id]
    others = [s for uid, s in scores_map.items() if uid != user.id]
    total_members = len(others) + 1

    below_count  = sum(1 for s in others if s < my_score_actual)
    better_count = sum(1 for s in others if s > my_score_actual)
    rank         = better_count + 1
    # Процентиль: доля людей НИЖЕ тебя, не включая себя; максимум 99
    percentile   = min(round(below_count / len(others) * 100), 99) if others else 0

    score_data["rank"]          = rank
    score_data["total_members"] = total_members
    score_data["percentile"]    = percentile
    return score_data


@app.get("/me/percentile")
def me_percentile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Точный процентиль пользователя по полному FIRE Score."""
    my_total = calc_fire_score(user, db)["total"]
    all_users = db.query(User).filter(User.pid.isnot(None), User.consent_given == True).all()
    all_scores = []
    for u in all_users:
        try:
            all_scores.append(calc_fire_score(u, db)["total"])
        except Exception:
            all_scores.append(0)
    total = len(all_scores)
    below = sum(1 for s in all_scores if s < my_total)
    percentile = round(below / total * 100) if total > 0 else 0
    return {"percentile": percentile, "total_members": total, "my_score": my_total}


def _build_static_motivation(
    has_report, has_skills, has_profession, contacts_count,
    total_answers, unanswered_q, trainer_count, has_achievement,
    percentile, my_total, total_members
):
    """Статические мотивационные пинки — фоллбэк если AI недоступен."""
    messages = []
    if not has_report:
        messages.append({"type": "report", "icon": "📊", "title": "Нет FIRE Score",
            "text": "Без ежемесячного отчёта ты невидим в рейтинге. 2 минуты — и ты в таблице лидеров.",
            "action": "report", "action_label": "Заполнить отчёт"})
    if not has_skills:
        messages.append({"type": "skills", "icon": "🎯", "title": "Заполни свои темы",
            "text": "Укажи темы — клуб будет знать, чем ты можешь помочь, и ты получишь +баллы.",
            "action": "profile", "action_label": "Добавить темы"})
    if not has_profession:
        messages.append({"type": "profession", "icon": "💼", "title": "Кто ты в клубе?",
            "text": "Расскажи профессию — это помогает находить нужных людей и получать релевантные вопросы.",
            "action": "profile", "action_label": "Редактировать профиль"})
    if contacts_count == 0:
        messages.append({"type": "contacts", "icon": "🤝", "title": f"В клубе {total_members} человек",
            "text": "Ты ещё ни с кем не познакомился. Знакомства — нетворкинг + баллы к FIRE Score.",
            "action": "chats", "action_label": "Найти знакомых"})
    if total_answers == 0 and unanswered_q > 0:
        messages.append({"type": "help", "icon": "💡", "title": "Ты знаешь то, чего не знают другие",
            "text": f"В клубе {unanswered_q} вопросов без ответа. Один ответ = +баллы + статус эксперта.",
            "action": "questions", "action_label": "Ответить на вопрос"})
    if trainer_count == 0:
        messages.append({"type": "trainer", "icon": "🤖", "title": "Проверь финансовое мышление",
            "text": "AI-тренажёр оценит, как ты формулируешь задачи ИИ. Первая попытка — бесплатно, 5 минут.",
            "action": "games", "action_label": "Открыть тренажёр"})
    if not has_achievement:
        messages.append({"type": "achievement", "icon": "🏆", "title": "Нет достижений",
            "text": "Поделись победой — первый миллион, погашенный кредит, новый доход. Клуб поддержит 🔥",
            "action": "achievements", "action_label": "Добавить достижение"})
    if not messages:
        messages.append({"type": "rank", "icon": "📈", "title": f"Ты лучше {percentile}% клуба",
            "text": f"FIRE Score: {my_total} баллов. Продолжай расти — рост неизбежен.",
            "action": None, "action_label": None})
    return messages


@app.get("/me/motivation")
async def me_motivation(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Персональный AI мотивационный «пинок» на основе профиля."""
    score_data = calc_fire_score(user, db)
    my_total = score_data["total"]

    # Рейтинг среди активных участников
    active_users = db.query(User).filter(
        User.pid.isnot(None),
        User.consent_given == True,
        User.last_seen.isnot(None),
    ).all()
    scores_map: dict[int, float] = {}
    for u in active_users:
        try:
            scores_map[u.id] = calc_fire_score(u, db)["total"]
        except Exception:
            scores_map[u.id] = 0
    if user.id not in scores_map:
        scores_map[user.id] = my_total
    my_score_actual = scores_map[user.id]
    total_members = len(active_users)

    sorted_scores = sorted(scores_map.values(), reverse=True)
    ranked = sorted(scores_map.items(), key=lambda x: -x[1])
    my_rank_pos = next((i + 1 for i, (uid, _) in enumerate(ranked) if uid == user.id), total_members)

    others = [s for uid, s in scores_map.items() if uid != user.id]
    below_count = sum(1 for s in others if s < my_score_actual)
    percentile = min(round(below_count / len(others) * 100), 99) if others else 0

    top10_score = sorted_scores[9] if len(sorted_scores) >= 10 else (sorted_scores[-1] if sorted_scores else 0)
    gap_to_top10 = max(0, round(top10_score - my_score_actual))

    # Профиль
    has_skills = db.query(UserSkill).filter(UserSkill.user_id == user.id).count() > 0
    has_profession = bool(user.profession)
    total_answers = db.query(QuestionAnswer).filter(QuestionAnswer.expert_user_id == user.id).count()
    unanswered_q = db.query(ClubQuestion).filter(
        ClubQuestion.user_id != user.id
    ).outerjoin(QuestionAnswer, QuestionAnswer.question_id == ClubQuestion.id).filter(
        QuestionAnswer.id == None
    ).count()
    contacts_count = db.query(ContactRequest).filter(
        ContactRequest.status == "accepted",
        (ContactRequest.from_user_id == user.id) | (ContactRequest.to_user_id == user.id)
    ).count()
    has_achievement = db.query(Achievement).filter(Achievement.user_id == user.id).count() > 0
    trainer_count = db.query(TrainerAttempt).filter(TrainerAttempt.user_id == user.id).count()

    # Отчёты
    all_reports = db.query(Report).filter(Report.user_id == user.id).order_by(Report.created_at.desc()).all()
    current_month = datetime.utcnow().strftime("%Y-%m")
    has_current_month_report = any(r.month == current_month for r in all_reports)
    days_since_report = None
    if all_reports:
        days_since_report = (datetime.utcnow() - all_reports[0].created_at).days

    name = user.first_name or user.telegram_username or "участник"

    static_fallback = _build_static_motivation(
        has_report=len(all_reports) > 0,
        has_skills=has_skills,
        has_profession=has_profession,
        contacts_count=contacts_count,
        total_answers=total_answers,
        unanswered_q=unanswered_q,
        trainer_count=trainer_count,
        has_achievement=has_achievement,
        percentile=percentile,
        my_total=round(my_score_actual),
        total_members=total_members,
    )

    user_state = {
        "name": name,
        "fire_score": round(my_score_actual),
        "rank_position": my_rank_pos,
        "total_members": total_members,
        "percentile": percentile,
        "gap_to_top10": gap_to_top10,
        "days_since_report": days_since_report,
        "has_current_month_report": has_current_month_report,
        "has_ever_report": len(all_reports) > 0,
        "has_skills": has_skills,
        "has_profession": has_profession,
        "contacts_count": contacts_count,
        "answers_given": total_answers,
        "unanswered_questions": unanswered_q,
        "trainer_attempts": trainer_count,
        "has_achievement": has_achievement,
    }

    prompt = f"""Ты — AI-тренер клуба личных финансов FIRE35. Создай персональный мотивационный пинок для участника.

Данные участника:
{json.dumps(user_state, ensure_ascii=False, indent=2)}

Контекст FIRE Score: баллы начисляются за ежемесячные отчёты (экономия, инвестиции), ответы на вопросы клуба, знакомства, заполнение профиля (навыки, профессия), достижения, AI-тренажёр.

Верни JSON-массив из 1-3 сообщений. Каждое:
{{"type":"report|skills|profession|contacts|help|trainer|achievement|rank|challenge","icon":"один эмодзи","title":"до 40 символов","text":"1-2 предложения, конкретно с цифрами","action":"report|profile|chats|questions|games|achievements|null","action_label":"текст кнопки или null"}}

Правила:
- Начни с самой критичной проблемы (нет отчёта > нет профиля > нет контактов)
- Если нет отчёта за текущий месяц (has_current_month_report=false) — это первый пинок
- Используй конкретные цифры: gap_to_top10, rank_position, unanswered_questions
- Тон: дружеский, прямой, без воды. Не "рекомендуем", а "сделай сейчас"
- Если участник в топ-20% — дай вызов на рост вместо базовых задач
- Верни ТОЛЬКО JSON-массив, без пояснений"""

    try:
        async with httpx.AsyncClient(timeout=15) as http_client:
            resp = await http_client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://fire35club.duckdns.org",
                    "X-Title": "FIRE35",
                },
                json={
                    "model": "google/gemini-2.5-flash",
                    "max_tokens": 600,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        start, end = raw.find("["), raw.rfind("]") + 1
        if start >= 0 and end > start:
            messages = json.loads(raw[start:end])
        else:
            messages = static_fallback
    except Exception as e:
        print(f"[MOTIVATION] AI error: {e}", flush=True)
        messages = static_fallback

    return {"messages": messages, "percentile": percentile}


@app.patch("/me")
def update_me(
    body: UpdateProfileRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if body.telegram_username is not None:
        tg = body.telegram_username.strip().lstrip('@')
        user.telegram_username = tg or None
    if body.first_name is not None:
        user.first_name = body.first_name.strip() or None
    if body.skills is not None:
        user.skills = body.skills.strip() or None
    if body.profession is not None:
        user.profession = body.profession.strip() or None
    db.commit()
    return {"status": "ok"}


# ── Навыки (UserSkill) ─────────────────────────────────────

@app.get("/skills/catalog")
def skills_catalog():
    """Справочник навыков по категориям."""
    return SKILLS_CATALOG


@app.get("/me/skills")
def get_my_skills(user: User = Depends(current_user), db: Session = Depends(get_db)):
    skills = db.query(UserSkill).filter(UserSkill.user_id == user.id).all()
    return [{"id": s.id, "skill_name": s.skill_name} for s in skills]


@app.post("/me/ping")
def ping_online(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Обновляет last_seen — вызывается фронтом каждые 60 сек."""
    user.last_seen = datetime.utcnow()
    db.commit()
    return {"ok": True}


@app.post("/me/skills")
def add_skill(
    body: SkillAddRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    # Проверяем лимит 20 навыков
    count = db.query(UserSkill).filter(UserSkill.user_id == user.id).count()
    if count >= 20:
        raise HTTPException(status_code=400, detail="Максимум 20 навыков")

    skill = normalize_skill(body.skill_name)
    if not skill:
        raise HTTPException(status_code=400, detail="Навык не может быть пустым")
    if len(skill) > 50:
        raise HTTPException(status_code=400, detail="Навык слишком длинный")

    existing = db.query(UserSkill).filter(
        UserSkill.user_id == user.id, UserSkill.skill_name == skill
    ).first()
    if existing:
        return {"status": "already_exists", "id": existing.id, "skill_name": skill}

    new_skill = UserSkill(user_id=user.id, skill_name=skill)
    db.add(new_skill)
    db.commit()
    db.refresh(new_skill)
    return {"status": "added", "id": new_skill.id, "skill_name": skill}


@app.delete("/me/skills/{skill_id}")
def remove_skill(
    skill_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    skill = db.query(UserSkill).filter(
        UserSkill.id == skill_id, UserSkill.user_id == user.id
    ).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Навык не найден")
    db.delete(skill)
    db.commit()
    return {"status": "removed"}


# ── Daily limits ──────────────────────────────────────────

@app.get("/daily_limits")
def get_daily_limits(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Лимиты вопросов на сегодня с учётом активности."""
    return calc_daily_limits(user, db)


# ── Reports ───────────────────────────────────────────────

@app.post("/reports")
def create_report(
    body: ReportCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    month = body.month or current_month()
    existing = (
        db.query(Report)
        .filter(Report.user_id == user.id, Report.month == month)
        .first()
    )
    if existing:
        existing.budget_yes = body.budget_yes
        existing.income_gt_expense = body.income_gt_expense
        existing.savings_pct = body.savings_pct
        existing.invest_pct = body.invest_pct
        existing.created_at = datetime.utcnow()
        db.commit()
        return {"status": "updated", "month": month}

    db.add(Report(
        user_id=user.id,
        month=month,
        budget_yes=body.budget_yes,
        income_gt_expense=body.income_gt_expense,
        savings_pct=body.savings_pct,
        invest_pct=body.invest_pct,
    ))
    db.commit()
    return {"status": "created", "month": month}


@app.get("/reports/my/{month}")
def get_my_report(
    month: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    report = (
        db.query(Report)
        .filter(Report.user_id == user.id, Report.month == month)
        .first()
    )
    if not report:
        return None
    return {
        "month": report.month,
        "budget_yes": report.budget_yes,
        "income_gt_expense": report.income_gt_expense,
        "savings_pct": report.savings_pct,
        "invest_pct": report.invest_pct,
    }


@app.get("/reports/rating/{month}", response_model=List[RatingEntry])
def get_rating(
    month: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    reports = (
        db.query(Report)
        .filter(Report.month == month)
        .order_by(Report.savings_pct.desc())
        .all()
    )
    y, m = map(int, month.split("-"))
    prev_month = f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"
    prev_map = {r.user_id: r.savings_pct
                for r in db.query(Report).filter(Report.month == prev_month).all()}

    result = []
    for rank, r in enumerate(reports, start=1):
        delta = round(r.savings_pct - prev_map[r.user_id], 1) if r.user_id in prev_map else None
        result.append(RatingEntry(
            rank=rank,
            pid=r.user.pid,
            savings_pct=r.savings_pct,
            invest_pct=r.invest_pct > 0,
            delta_pct=delta,
            is_me=(r.user_id == user.id),
        ))
    return result


# ── Directory ─────────────────────────────────────────────

@app.get("/directory", response_model=List[DirectoryProfession])
def get_directory(
    search: Optional[str] = None,
    month: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(User).filter(User.profession.isnot(None))
    if search:
        query = query.filter(User.profession.ilike(f"%{search}%"))
    users = query.all()

    ratings: dict[int, float] = {}
    if month:
        for r in db.query(Report).filter(Report.month == month).all():
            ratings[r.user_id] = r.savings_pct

    prof_map: dict[str, list] = {}
    for u in users:
        p = (u.profession or "Не указано").strip()
        prof_map.setdefault(p, []).append({
            "pid": u.pid,
            "first_name": u.first_name or "",
            "profession": p,
            "skills": u.skills or "—",
            "savings_pct": ratings.get(u.id),
            "answer_score": u.answer_score or 0,
        })

    return sorted(
        [DirectoryProfession(profession=p, count=len(m), members=m)
         for p, m in prof_map.items()],
        key=lambda x: x.count,
        reverse=True,
    )


# ── FCM Token ─────────────────────────────────────────────

@app.post("/fcm/token")
def save_fcm_token(
    body: FcmTokenRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    existing = db.query(FcmToken).filter(FcmToken.user_id == user.id).first()
    if existing:
        existing.token = body.token
        existing.updated_at = datetime.utcnow()
    else:
        db.add(FcmToken(user_id=user.id, token=body.token))
    db.commit()
    return {"status": "ok"}


# ── Contact Requests ──────────────────────────────────────

@app.post("/contact-request/{to_pid}")
async def send_contact_request(
    to_pid: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    to_pid = to_pid.strip().upper()
    target = db.query(User).filter(User.pid == to_pid).first()
    if not target:
        raise HTTPException(status_code=404, detail="Участник не найден")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Нельзя отправить запрос себе")

    existing = (
        db.query(ContactRequest)
        .filter(
            ContactRequest.from_user_id == user.id,
            ContactRequest.to_user_id == target.id,
            ContactRequest.status == "pending",
        )
        .first()
    )
    if existing:
        return {"status": "already_sent"}

    req = ContactRequest(from_user_id=user.id, to_user_id=target.id)
    db.add(req)
    db.commit()
    db.refresh(req)

    # Telegram bot notification
    print(f"[CONTACT] {user.pid} → {target.pid}, target.telegram_id={target.telegram_id!r}")
    if target.telegram_id:
        sender_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.pid
        msg = (
            f"👋 <b>Запрос на знакомство</b>\n\n"
            f"Добрый день! Участник <b>{sender_name}</b> ({user.pid}) хочет познакомиться — "
            f"постучаться в друзья или получить совет."
        )
        keyboard = {"inline_keyboard": [[
            {"text": "✅ Принять", "callback_data": f"contact_accept_{req.id}"},
            {"text": "❌ Отклонить", "callback_data": f"contact_decline_{req.id}"},
        ]]}
        await tg_send(target.telegram_id, msg, reply_markup=keyboard)

    fcm_row = db.query(FcmToken).filter(FcmToken.user_id == target.id).first()
    if fcm_row:
        await send_push(
            token=fcm_row.token,
            title="Запрос на знакомство",
            body=f"Участник {user.pid} хочет познакомиться. Открой FIRE35 → Участники",
            data={"type": "contact_request", "from_pid": user.pid},
        )

    return {"status": "sent"}


@app.get("/me/friends")
def get_my_friends(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Список принятых знакомств текущего пользователя."""
    accepted = db.query(ContactRequest).filter(
        ContactRequest.status == "accepted",
        (ContactRequest.from_user_id == user.id) | (ContactRequest.to_user_id == user.id),
    ).all()

    result = []
    for req in accepted:
        other = req.to_user if req.from_user_id == user.id else req.from_user
        skills = [s.skill_name for s in other.skills_list]
        result.append({
            "pid": other.pid,
            "first_name": other.first_name or other.pid,
            "last_name": other.last_name or "",
            "profession": other.profession or "",
            "telegram_username": other.telegram_username or "",
            "skills": skills[:4],
            "answer_score": other.answer_score or 0,
        })
    return result


@app.get("/contact-requests/pending", response_model=List[ContactRequestOut])
def get_pending_requests(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    reqs = (
        db.query(ContactRequest)
        .filter(
            ContactRequest.to_user_id == user.id,
            ContactRequest.status == "pending",
        )
        .order_by(ContactRequest.created_at.desc())
        .all()
    )
    return [
        ContactRequestOut(
            id=r.id,
            from_pid=r.from_user.pid,
            from_telegram=r.from_user.telegram_username,
            created_at=r.created_at.strftime("%d.%m.%Y %H:%M"),
        )
        for r in reqs
    ]


@app.post("/contact-requests/{req_id}/accept")
async def accept_request(
    req_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    req = db.query(ContactRequest).filter(
        ContactRequest.id == req_id,
        ContactRequest.to_user_id == user.id,
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    req.status = "accepted"
    db.commit()

    # Notify requester
    if req.from_user.telegram_id:
        acceptor_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.pid
        await tg_send(
            req.from_user.telegram_id,
            f"✅ <b>{acceptor_name}</b> принял(а) ваш запрос на знакомство!\n"
            f"Telegram: @{user.telegram_username or user.pid}",
        )

    return {
        "status": "accepted",
        "from_pid": req.from_user.pid,
        "telegram_username": req.from_user.telegram_username,
    }


@app.post("/contact-requests/{req_id}/decline")
def decline_request(
    req_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    req = db.query(ContactRequest).filter(
        ContactRequest.id == req_id,
        ContactRequest.to_user_id == user.id,
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    req.status = "declined"
    db.commit()
    return {"status": "declined"}


@app.delete("/contact/{pid}")
def remove_contact(
    pid: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.pid == pid).first()
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    req = db.query(ContactRequest).filter(
        ContactRequest.status == "accepted",
        (
            (ContactRequest.from_user_id == user.id) & (ContactRequest.to_user_id == target.id)
        ) | (
            (ContactRequest.from_user_id == target.id) & (ContactRequest.to_user_id == user.id)
        ),
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Знакомство не найдено")
    db.delete(req)
    db.commit()
    return {"status": "removed"}


# ── Privacy / Intro settings ──────────────────────────────

class PrivacySettings(BaseModel):
    intro_consent_given: Optional[bool] = None
    question_visibility: Optional[str] = None   # 'all' | 'skills_only'
    intro_receive: Optional[bool] = None
    intro_frequency: Optional[str] = None       # 'weekly'|'biweekly'|'monthly'|'never'


@app.get("/me/privacy")
def get_privacy(user: User = Depends(current_user)):
    return {
        "intro_consent_given": bool(user.intro_consent_given),
        "question_visibility": user.question_visibility or "skills_only",
        "intro_receive": bool(user.intro_receive) if user.intro_receive is not None else True,
        "intro_frequency": user.intro_frequency or "biweekly",
    }


@app.patch("/me/privacy")
def update_privacy(
    body: PrivacySettings,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if body.intro_consent_given is not None:
        user.intro_consent_given = body.intro_consent_given
        user.intro_consent_updated_at = datetime.utcnow()
    if body.question_visibility is not None:
        if body.question_visibility not in ("all", "skills_only"):
            raise HTTPException(status_code=400, detail="Неверное значение question_visibility")
        user.question_visibility = body.question_visibility
    if body.intro_receive is not None:
        user.intro_receive = body.intro_receive
    if body.intro_frequency is not None:
        if body.intro_frequency not in ("weekly", "biweekly", "monthly", "never"):
            raise HTTPException(status_code=400, detail="Неверное значение intro_frequency")
        user.intro_frequency = body.intro_frequency
    db.commit()
    return {"status": "ok"}


@app.get("/me/introductions")
def get_my_introductions(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Список рекомендованных знакомств для текущего пользователя."""
    intros = (
        db.query(Introduction)
        .filter(
            Introduction.to_user_id == user.id,
            Introduction.status.in_(["pending", "sent"]),
        )
        .order_by(Introduction.score.desc())
        .limit(10)
        .all()
    )
    result = []
    for intro in intros:
        fu = intro.from_user
        skills = [s.skill_name for s in fu.skills_list]
        result.append({
            "id": intro.id,
            "pid": fu.pid,
            "first_name": fu.first_name or fu.pid,
            "last_name": fu.last_name or "",
            "profession": fu.profession or "",
            "skills": skills[:5],
            "answer_score": fu.answer_score or 0,
            "score": round(intro.score, 2),
            "reason": intro.reason or "",
        })
    return result


@app.post("/introductions/{intro_id}/feedback")
def intro_feedback(
    intro_id: int,
    action: str,   # 'accept' | 'skip'
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    intro = db.query(Introduction).filter(
        Introduction.id == intro_id,
        Introduction.to_user_id == user.id,
    ).first()
    if not intro:
        raise HTTPException(status_code=404, detail="Рекомендация не найдена")
    if action not in ("accept", "skip"):
        raise HTTPException(status_code=400, detail="action должен быть accept или skip")

    existing = db.query(IntroFeedback).filter(
        IntroFeedback.intro_id == intro_id,
        IntroFeedback.user_id == user.id,
    ).first()
    if not existing:
        db.add(IntroFeedback(intro_id=intro_id, user_id=user.id, feedback=action))

    intro.status = "accepted" if action == "accept" else "skipped"
    db.commit()
    return {"status": action}


# ── Progress (темы клуба) ──────────────────────────────────

class ProgressUpdate(BaseModel):
    topic_id: int   # 1..11
    done: bool


@app.get("/progress")
def get_progress(user: User = Depends(current_user)):
    done_ids = set()
    if user.topics_done:
        done_ids = {int(x) for x in user.topics_done.split(",") if x.strip()}
    return {"done": sorted(done_ids)}


@app.post("/progress")
def update_progress(
    body: ProgressUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    done_ids = set()
    if user.topics_done:
        done_ids = {int(x) for x in user.topics_done.split(",") if x.strip()}
    if body.done:
        done_ids.add(body.topic_id)
    else:
        done_ids.discard(body.topic_id)
    user.topics_done = ",".join(str(x) for x in sorted(done_ids))
    db.commit()
    return {"done": sorted(done_ids)}


# ── Вопросы клубу (с тегами и экспертами) ─────────────────

@app.post("/questions")
async def submit_question(
    body: QuestionCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    q_text = body.question.strip()
    if not q_text:
        raise HTTPException(status_code=400, detail="Вопрос не может быть пустым")
    if len(q_text) > 500:
        raise HTTPException(status_code=400, detail="Вопрос не может быть длиннее 500 символов")

    # Проверяем дневной лимит
    limits = calc_daily_limits(user, db)
    if limits["remaining"] <= 0:
        raise HTTPException(
            status_code=429,
            detail=f"Лимит вопросов на сегодня исчерпан ({limits['total_limit']} шт.). "
                   f"Отвечай на вопросы других участников — получишь больше."
        )

    # Нормализуем теги
    tags = body.tags or []
    tags = [normalize_skill(t) for t in tags[:3] if t.strip()]
    tags_str = ",".join(tags) if tags else None

    # ── Генерируем embedding и ищем дубликаты ────────────
    try:
        new_emb = embed_text(q_text)
        similar = find_similar_questions(new_emb, db)
    except Exception as e:
        print(f"[Embed] Error: {e}")
        new_emb = None
        similar = []

    is_dup = len(similar) > 0
    best_match = similar[0] if is_dup else None

    # Сохраняем вопрос
    question = ClubQuestion(
        user_id=user.id,
        question=q_text,
        tags=tags_str,
        is_duplicate=is_dup,
        force_new=False,
    )
    db.add(question)
    db.commit()
    db.refresh(question)

    # Сохраняем embedding
    if new_emb is not None:
        qe = QuestionEmbedding(question_id=question.id, embedding=new_emb)
        db.add(qe)

    if is_dup and best_match:
        # Записываем дубликат
        dup_record = QuestionDuplicate(
            original_question_id=best_match["question_id"],
            duplicate_question_id=question.id,
            similarity_score=best_match["similarity"],
        )
        db.add(dup_record)

        # Авто-ответ: сохраняем как QuestionAnswer
        auto_ans = QuestionAnswer(
            question_id=question.id,
            answer=best_match["answer_text"],
            expert_user_id=None,
            response_time_minutes=0,
            is_useful=None,
        )
        db.add(auto_ans)
        db.commit()

        # Уведомление в бот с кнопками
        if user.telegram_id:
            days_ago = best_match["answered_days_ago"]
            days_str = f"{days_ago} д. назад" if days_ago > 0 else "сегодня"
            expert_str = f"@{best_match['expert_username']}" if best_match["expert_username"] else "эксперт клуба"
            score_str = f" (⭐ {best_match['expert_score']})" if best_match["expert_score"] else ""
            kb = {
                "inline_keyboard": [[
                    {"text": "✅ Полезно, спасибо",   "callback_data": f"dup_ok_{question.id}"},
                    {"text": "🔄 Всё равно спросить", "callback_data": f"dup_force_{question.id}"},
                ]]
            }
            await tg_send(
                user.telegram_id,
                f"🤖 <b>Похожий вопрос уже задавали ({days_str})!</b>\n\n"
                f"<i>Q: {best_match['question_text'][:150]}</i>\n\n"
                f"<b>Ответ от {expert_str}{score_str}:</b>\n"
                f"{best_match['answer_text'][:500]}\n\n"
                f"Этот ответ подходит?",
                reply_markup=kb,
            )

        return {
            "status": "ok",
            "remaining": limits["remaining"] - 1,
            "duplicate": True,
            "duplicate_data": {
                "question_id": question.id,
                "original_question": best_match["question_text"],
                "answer": best_match["answer_text"],
                "expert_username": best_match["expert_username"],
                "expert_score": best_match["expert_score"],
                "similarity": best_match["similarity"],
                "answered_days_ago": best_match["answered_days_ago"],
            },
        }

    # ── Обычный путь ─────────────────────────────────────
    db.commit()
    admin = db.query(User).filter(User.pid == "P-001").first()
    if admin and admin.telegram_id and not tags:
        await tg_send(admin.telegram_id,
                      f"❓ Новый вопрос от {user.first_name or user.pid} ({user.pid}):\n\n{q_text}")
    if tags:
        await notify_experts(question, db)

    return {"status": "ok", "remaining": limits["remaining"] - 1, "duplicate": False}


@app.get("/questions")
def get_questions(
    filter: Optional[str] = None,   # "solved" | "unsolved" | None = all
    tag: Optional[str] = None,
    my_topics: bool = False,         # только вопросы по моим навыкам
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Лента вопросов — видна всем участникам клуба."""
    query = db.query(ClubQuestion).order_by(ClubQuestion.created_at.desc()).limit(100)
    qs = query.all()

    # Голоса текущего пользователя (чтобы показать my_vote)
    my_votes = {
        v.answer_id: v.vote
        for v in db.query(AnswerVote).filter(AnswerVote.user_id == user.id).all()
    }

    result = []
    for q in qs:
        if not q.user:   # пропускаем вопросы без автора (осиротевшие записи)
            continue
        # Сортируем ответы: принятый первый, потом по vote_score desc, потом по дате
        sorted_answers = sorted(
            q.answers,
            key=lambda a: (
                -(1 if a.is_useful else 0),
                -(a.vote_score or 0),
                a.created_at,
            )
        )
        answers_data = [
            {
                "id": a.id,
                "answer": a.answer,
                "expert_pid": a.expert.pid if a.expert else None,
                "expert_name": (a.expert.first_name or a.expert.pid) if a.expert else "Анар",
                "expert_username": a.expert.telegram_username if a.expert else None,
                "expert_score": a.expert.answer_score if a.expert else None,
                "is_useful": a.is_useful,
                "vote_score": a.vote_score or 0,
                "my_vote": my_votes.get(a.id, 0),
                "created_at": a.created_at.strftime("%d.%m %H:%M"),
            }
            for a in sorted_answers
        ]

        has_useful = any(a.is_useful for a in q.answers)

        # Фильтрация
        if filter == "solved" and not has_useful:
            continue
        if filter == "unsolved" and has_useful:
            continue
        if tag and tag not in (q.tags or "").split(","):
            continue
        # my_topics=True — явный режим "по навыкам": свои не показываем,
        # только чужие с тегами совпадающими с навыками
        if my_topics:
            if q.user_id == user.id:
                continue  # свои вопросы не показываем
            my_skills = [s.skill_name for s in user.skills_list]
            q_tags = [t for t in (q.tags or "").split(",") if t]
            if not q_tags or not any(t in my_skills for t in q_tags):
                continue  # без тегов или теги не совпадают — скрываем

        result.append({
            "id": q.id,
            "pid": q.user.pid,
            "first_name": q.user.first_name or q.user.pid,
            "answer_score": q.user.answer_score or 0,
            "is_me": q.user_id == user.id,
            "question": q.question,
            "tags": q.tags.split(",") if q.tags else [],
            "created_at": q.created_at.strftime("%d.%m %H:%M"),
            "is_duplicate": bool(q.is_duplicate),
            "flag_count": q.flag_count or 0,
            "answers": answers_data,
        })

    return result


@app.post("/questions/answers/{answer_id}/rate")
def rate_answer(
    answer_id: int,
    body: RateAnswerRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Автор вопроса оценивает ответ эксперта."""
    answer = db.query(QuestionAnswer).filter(QuestionAnswer.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Ответ не найден")

    # Только автор вопроса может оценивать
    question = db.query(ClubQuestion).filter(ClubQuestion.id == answer.question_id).first()
    if not question or question.user_id != user.id:
        raise HTTPException(status_code=403, detail="Только автор вопроса может оценивать")

    # Только один раз
    if answer.is_useful is not None:
        raise HTTPException(status_code=400, detail="Оценка уже выставлена")

    answer.is_useful = body.is_useful

    # Обновляем счёт эксперта
    if answer.expert_user_id and body.is_useful:
        expert = db.query(User).filter(User.id == answer.expert_user_id).first()
        if expert:
            expert.answer_score = (expert.answer_score or 0) + 1
            expert.total_answers = (expert.total_answers or 0) + 1
    elif answer.expert_user_id:
        expert = db.query(User).filter(User.id == answer.expert_user_id).first()
        if expert:
            expert.total_answers = (expert.total_answers or 0) + 1

    db.commit()
    return {"status": "ok"}


@app.post("/questions/answers/{answer_id}/vote")
def vote_answer(
    answer_id: int,
    body: dict,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Upvote (+1) или downvote (-1) ответа. Нельзя голосовать за свой ответ."""
    vote_val = body.get("vote")
    if vote_val not in (1, -1):
        raise HTTPException(status_code=400, detail="vote должен быть 1 или -1")

    answer = db.query(QuestionAnswer).filter(QuestionAnswer.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Ответ не найден")

    if answer.expert_user_id == user.id:
        raise HTTPException(status_code=403, detail="Нельзя голосовать за свой ответ")

    existing = db.query(AnswerVote).filter(
        AnswerVote.answer_id == answer_id,
        AnswerVote.user_id == user.id,
    ).first()

    if existing:
        if existing.vote == vote_val:
            # Отменяем голос
            answer.vote_score = (answer.vote_score or 0) - vote_val
            db.delete(existing)
            new_vote = 0
        else:
            # Меняем голос
            answer.vote_score = (answer.vote_score or 0) - existing.vote + vote_val
            existing.vote = vote_val
            new_vote = vote_val
    else:
        db.add(AnswerVote(answer_id=answer_id, user_id=user.id, vote=vote_val))
        answer.vote_score = (answer.vote_score or 0) + vote_val
        new_vote = vote_val

    # Обновляем репутацию автора ответа
    if answer.expert_user_id:
        expert = db.query(User).filter(User.id == answer.expert_user_id).first()
        if expert:
            expert.answer_score = max(0, (expert.answer_score or 0) + vote_val)

    db.commit()
    return {"vote_score": answer.vote_score, "my_vote": new_vote}


@app.post("/questions/{qid}/flag")
def flag_question(
    qid: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Пометить вопрос как некачественный / слишком общий."""
    q = db.query(ClubQuestion).filter(ClubQuestion.id == qid).first()
    if not q:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    if q.user_id == user.id:
        raise HTTPException(status_code=403, detail="Нельзя жаловаться на свой вопрос")
    q.flag_count = (q.flag_count or 0) + 1
    db.commit()
    return {"flag_count": q.flag_count}


@app.post("/questions/{qid}/force-new")
async def force_new_question(
    qid: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Автор хочет всё равно разослать вопрос экспертам (несмотря на дубликат)."""
    q = db.query(ClubQuestion).filter(
        ClubQuestion.id == qid,
        ClubQuestion.user_id == user.id,
    ).first()
    if not q:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    if not q.is_duplicate:
        raise HTTPException(status_code=400, detail="Вопрос не является дубликатом")

    q.force_new = True
    q.is_duplicate = False
    db.commit()
    db.refresh(q)

    # Рассылаем экспертам
    tags = [t.strip() for t in q.tags.split(",") if t.strip()] if q.tags else []
    admin = db.query(User).filter(User.pid == "P-001").first()
    if admin and admin.telegram_id and not tags:
        await tg_send(admin.telegram_id,
                      f"❓ Вопрос (принудительно) от {user.first_name or user.pid}:\n\n{q.question}")
    if tags:
        await notify_experts(q, db)

    return {"status": "ok", "sent_to_experts": True}


@app.get("/questions/similar/{question_id}")
def get_similar_questions(
    question_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Топ-3 похожих вопроса из базы."""
    qe = db.query(QuestionEmbedding).filter(
        QuestionEmbedding.question_id == question_id
    ).first()
    if not qe:
        return []
    return find_similar_questions(qe.embedding, db, threshold=0.75, exclude_question_id=question_id)


@app.delete("/questions/{qid}")
def delete_question(
    qid: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Автор удаляет свой вопрос."""
    q = db.query(ClubQuestion).filter(
        ClubQuestion.id == qid,
        ClubQuestion.user_id == user.id,
    ).first()
    if not q:
        raise HTTPException(status_code=404, detail="Вопрос не найден или нет доступа")
    # Удаляем embedding и дубликаты
    db.query(QuestionEmbedding).filter(QuestionEmbedding.question_id == qid).delete()
    db.query(QuestionDuplicate).filter(
        (QuestionDuplicate.original_question_id == qid) |
        (QuestionDuplicate.duplicate_question_id == qid)
    ).delete(synchronize_session=False)
    db.query(QuestionAnswer).filter(QuestionAnswer.question_id == qid).delete()
    db.delete(q)
    db.commit()
    return {"status": "deleted"}


@app.post("/questions/{qid}/answers")
async def post_answer(
    qid: int,
    body: AnswerCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Любой участник клуба может ответить на вопрос."""
    if len(body.answer.strip()) < 10:
        raise HTTPException(status_code=400, detail="Ответ слишком короткий (мин. 10 символов)")

    q = db.query(ClubQuestion).filter(ClubQuestion.id == qid).first()
    if not q:
        raise HTTPException(status_code=404, detail="Вопрос не найден")

    now = datetime.utcnow()
    minutes = int((now - q.created_at).total_seconds() / 60)

    ans = QuestionAnswer(
        question_id=qid,
        answer=body.answer.strip(),
        expert_user_id=user.id,
        response_time_minutes=minutes,
        is_useful=None,
    )
    db.add(ans)
    user.total_answers = (user.total_answers or 0) + 1
    db.commit()
    db.refresh(ans)

    # Уведомляем автора вопроса (если это не он сам)
    if q.user.telegram_id and q.user_id != user.id:
        responder_name = user.first_name or user.pid
        await tg_send(
            q.user.telegram_id,
            f"💬 <b>{responder_name}</b> ответил на ваш вопрос:\n\n"
            f"❓ {q.question[:120]}\n\n"
            f"📝 {body.answer.strip()[:300]}\n\n"
            f"Откройте Mini App чтобы оценить ответ!",
        )

    return {
        "id": ans.id,
        "answer": ans.answer,
        "expert_pid": user.pid,
        "expert_name": user.first_name or user.pid,
        "expert_score": user.answer_score or 0,
        "is_useful": None,
        "created_at": ans.created_at.strftime("%d.%m %H:%M"),
    }


@app.get("/members")
def get_members(
    sort: str = "pid",
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Список всех участников — данные для клиентской фильтрации и поиска."""
    # Один запрос с joinedload навыков (убираем N+1)
    users = (
        db.query(User)
        .filter(User.pid.isnot(None))
        .options(joinedload(User.skills_list))
        .all()
    )

    # Один запрос для последних savings_pct (subquery вместо загрузки всех репортов)
    latest_savings_rows = db.execute(text("""
        SELECT r.user_id, r.savings_pct
        FROM reports r
        INNER JOIN (
            SELECT user_id, MAX(month) AS max_month
            FROM reports
            GROUP BY user_id
        ) latest ON r.user_id = latest.user_id AND r.month = latest.max_month
    """)).fetchall()
    latest_savings = {row[0]: row[1] for row in latest_savings_rows}

    # Батч-запрос: количество принятых ответов по каждому пользователю
    accepted_rows = db.execute(text("""
        SELECT expert_user_id, COUNT(*) as cnt
        FROM question_answers
        WHERE is_useful = 1 AND expert_user_id IS NOT NULL
        GROUP BY expert_user_id
    """)).fetchall()
    accepted_map = {row[0]: row[1] for row in accepted_rows}

    # Батч-запрос: количество отчётов по каждому пользователю
    reports_rows = db.execute(text("""
        SELECT user_id, COUNT(*) as cnt FROM reports GROUP BY user_id
    """)).fetchall()
    reports_map = {row[0]: row[1] for row in reports_rows}

    # Батч-запрос: topics_done хранится прямо в User (уже загружено)

    result = []
    for u in users:
        skills = [s.skill_name for s in u.skills_list]
        # Быстрый FIRE score (без streak — для списка участников)
        help_s   = round((accepted_map.get(u.id, 0)) * 0.25, 1)
        topics   = len([t for t in (u.topics_done or "").split(",") if t.strip()])
        learn_s  = min(topics * 3, 30)
        disc_s   = min((reports_map.get(u.id, 0)) * 3, 20)
        sav_pct  = latest_savings.get(u.id)
        fin_s    = min(3 if sav_pct and sav_pct > 0 else 0, 10)
        fire_total = round(help_s + learn_s + disc_s + fin_s, 1)
        is_online = (
            u.last_seen is not None and
            (datetime.utcnow() - u.last_seen).total_seconds() < 300  # 5 минут
        )
        result.append({
            "pid": u.pid,
            "first_name": u.first_name or "",
            "last_name": u.last_name or "",
            "profession": u.profession or "",
            "skills": skills,
            "answer_score": u.answer_score or 0,
            "total_answers": u.total_answers or 0,
            "savings_pct": sav_pct,
            "is_me": u.id == user.id,
            "fire_total": fire_total,
            "fire_level": calc_fire_level(fire_total),
            "is_online": is_online,
        })

    if sort == "score":
        result.sort(key=lambda x: x["fire_total"], reverse=True)
    elif sort == "savings":
        result.sort(key=lambda x: (x["savings_pct"] or -1), reverse=True)
    else:
        result.sort(key=lambda x: x["pid"])

    return result


@app.get("/members/{pid}")
def get_member_detail(
    pid: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Детальная карточка участника: профиль + скиллы + вопросы."""
    member = db.query(User).filter(User.pid == pid).first()
    if not member:
        raise HTTPException(status_code=404, detail="Участник не найден")

    skills = [s.skill_name for s in member.skills_list]

    questions = (
        db.query(ClubQuestion)
        .filter(ClubQuestion.user_id == member.id)
        .order_by(ClubQuestion.created_at.desc())
        .limit(20)
        .all()
    )
    q_data = []
    for q in questions:
        answers_sorted = sorted(q.answers, key=lambda a: a.created_at)
        q_data.append({
            "id": q.id,
            "question": q.question,
            "tags": q.tags.split(",") if q.tags else [],
            "answer_count": len(q.answers),
            "has_useful": any(a.is_useful for a in q.answers),
            "created_at": q.created_at.strftime("%d.%m %H:%M"),
            "answers": [
                {
                    "id": a.id,
                    "expert_name": (a.expert.first_name or a.expert.pid) if a.expert else "Анар",
                    "answer": a.answer,
                    "created_at": a.created_at.strftime("%d.%m %H:%M"),
                    "is_useful": bool(a.is_useful),
                    "vote_score": a.vote_score or 0,
                }
                for a in answers_sorted
            ],
        })

    existing = db.query(ContactRequest).filter(
        ContactRequest.from_user_id == user.id,
        ContactRequest.to_user_id == member.id,
    ).first()

    is_online = (
        member.last_seen is not None and
        (datetime.utcnow() - member.last_seen).total_seconds() < 300
    )
    last_seen_str = None
    if member.last_seen:
        delta = datetime.utcnow() - member.last_seen
        mins = int(delta.total_seconds() / 60)
        if mins < 1:
            last_seen_str = "только что"
        elif mins < 60:
            last_seen_str = f"{mins} мин назад"
        elif mins < 1440:
            last_seen_str = f"{mins // 60} ч назад"
        else:
            last_seen_str = f"{mins // 1440} д назад"

    return {
        "pid": member.pid,
        "first_name": member.first_name or member.pid,
        "last_name": member.last_name or "",
        "profession": member.profession or "",
        "skills": skills,
        "answer_score": member.answer_score or 0,
        "total_answers": member.total_answers or 0,
        "is_me": member.id == user.id,
        "contact_status": existing.status if existing else None,
        "questions": q_data,
        "is_online": is_online,
        "last_seen": last_seen_str,
    }


@app.get("/my/recommendation")
def get_my_recommendation(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rec = db.query(Recommendation).filter(Recommendation.user_id == user.id).first()
    return {"text": rec.text if rec else ""}


# ── Admin ──────────────────────────────────────────────────

def require_admin(user: User = Depends(current_user)) -> User:
    if user.pid != "P-001":
        raise HTTPException(status_code=403, detail="Только для администратора")
    return user


@app.get("/admin/members")
def admin_members(
    filter: str = "all",
    month: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    m = month or current_month()
    report_user_ids = {r.user_id for r in db.query(Report).filter(Report.month == m).all()}
    users = db.query(User).order_by(User.pid).all()
    result = []
    for u in users:
        has_rep = u.id in report_user_ids
        if filter == "has_report" and not has_rep:
            continue
        if filter == "no_report" and has_rep:
            continue
        if filter == "no_telegram" and u.telegram_id:
            continue
        rep = db.query(Report).filter(Report.user_id == u.id, Report.month == m).first()
        result.append({
            "pid": u.pid,
            "first_name": u.first_name or "",
            "telegram_username": u.telegram_username or "",
            "telegram_id": u.telegram_id or "",
            "profession": u.profession or "",
            "has_report": has_rep,
            "savings_pct": rep.savings_pct if rep else None,
            "consent_given": bool(u.consent_given),
            "answer_score": u.answer_score or 0,
        })
    return result


@app.delete("/admin/members/{pid}")
def admin_delete_member(
    pid: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.pid == pid.upper()).first()
    if not user:
        raise HTTPException(status_code=404, detail="Участник не найден")
    if user.pid == "P-001":
        raise HTTPException(status_code=400, detail="Нельзя удалить администратора")
    db.query(Report).filter(Report.user_id == user.id).delete()
    db.query(FcmToken).filter(FcmToken.user_id == user.id).delete()
    db.query(Recommendation).filter(Recommendation.user_id == user.id).delete()
    db.query(UserSkill).filter(UserSkill.user_id == user.id).delete()
    db.query(ContactRequest).filter(
        (ContactRequest.from_user_id == user.id) | (ContactRequest.to_user_id == user.id)
    ).delete(synchronize_session=False)
    q_ids = [q.id for q in db.query(ClubQuestion).filter(ClubQuestion.user_id == user.id).all()]
    if q_ids:
        db.query(QuestionAnswer).filter(QuestionAnswer.question_id.in_(q_ids)).delete(synchronize_session=False)
        db.query(QuestionEmbedding).filter(QuestionEmbedding.question_id.in_(q_ids)).delete(synchronize_session=False)
        db.query(QuestionDuplicate).filter(
            QuestionDuplicate.original_question_id.in_(q_ids) |
            QuestionDuplicate.duplicate_question_id.in_(q_ids)
        ).delete(synchronize_session=False)
    db.query(ClubQuestion).filter(ClubQuestion.user_id == user.id).delete()
    db.delete(user)
    db.commit()
    return {"status": "ok"}


@app.get("/admin/questions")
def admin_get_questions(
    tag: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(ClubQuestion).order_by(ClubQuestion.created_at.desc())
    if tag:
        query = query.filter(ClubQuestion.tags.contains(normalize_skill(tag)))
    qs = query.all()
    return [
        {
            "id": q.id,
            "pid": q.user.pid,
            "first_name": q.user.first_name or q.user.pid,
            "question": q.question,
            "tags": q.tags.split(",") if q.tags else [],
            "created_at": q.created_at.strftime("%d.%m %H:%M"),
            "answers": [
                {
                    "id": a.id,
                    "answer": a.answer,
                    "expert_username": a.expert.telegram_username if a.expert else None,
                    "is_useful": a.is_useful,
                    "created_at": a.created_at.strftime("%d.%m %H:%M"),
                }
                for a in q.answers
            ],
        }
        for q in qs
    ]


class AnswerCreate(BaseModel):
    answer: str


@app.post("/admin/questions/{qid}/answer")
async def admin_answer_question(
    qid: int,
    body: AnswerCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(ClubQuestion).filter(ClubQuestion.id == qid).first()
    if not q:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    db.add(QuestionAnswer(question_id=qid, answer=body.answer.strip()))
    db.commit()
    if q.user.telegram_id:
        await tg_send(q.user.telegram_id,
                      f"💬 Анар ответил на ваш вопрос:\n\n"
                      f"<b>Q:</b> {q.question}\n\n"
                      f"<b>A:</b> {body.answer.strip()}")
    return {"status": "ok"}


@app.get("/admin/duplicates/stats")
def admin_duplicates_stats(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from sqlalchemy import func
    total = db.query(ClubQuestion).count()
    dup_count = db.query(ClubQuestion).filter(ClubQuestion.is_duplicate == True).count()
    force_count = db.query(ClubQuestion).filter(ClubQuestion.force_new == True).count()
    saved = dup_count - force_count  # реально сэкономленных рассылок

    # Топ вопросов-источников (которые чаще всего копируют)
    top_src = (
        db.query(
            QuestionDuplicate.original_question_id,
            func.count(QuestionDuplicate.id).label("cnt"),
        )
        .group_by(QuestionDuplicate.original_question_id)
        .order_by(func.count(QuestionDuplicate.id).desc())
        .limit(5)
        .all()
    )
    top_list = []
    for orig_id, cnt in top_src:
        src = db.query(ClubQuestion).filter(ClubQuestion.id == orig_id).first()
        if src:
            top_list.append({
                "question_id": orig_id,
                "question": src.question[:120],
                "duplicate_count": cnt,
            })

    return {
        "total_questions": total,
        "duplicate_questions": dup_count,
        "force_new_count": force_count,
        "saved_notifications": saved,
        "cache_rate_pct": round(saved / total * 100, 1) if total else 0,
        "top_sources": top_list,
    }


@app.get("/admin/experts/top")
def admin_experts_top(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Топ-10 экспертов по answer_score."""
    experts = (
        db.query(User)
        .filter(User.answer_score > 0)
        .order_by(User.answer_score.desc())
        .limit(10)
        .all()
    )
    return [
        {
            "pid": u.pid,
            "first_name": u.first_name or "",
            "telegram_username": u.telegram_username or "",
            "answer_score": u.answer_score or 0,
            "total_answers": u.total_answers or 0,
            "skills": [s.skill_name for s in u.skills_list],
        }
        for u in experts
    ]


@app.get("/admin/analytics/{month}")
def admin_analytics(
    month: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reports = db.query(Report).filter(Report.month == month).all()
    all_users = db.query(User).all()
    submitted_ids = {r.user_id for r in reports}
    not_submitted = [u for u in all_users if u.id not in submitted_ids]
    avg_savings = round(sum(r.savings_pct for r in reports) / len(reports), 1) if reports else 0
    avg_invest = round(sum(r.invest_pct for r in reports) / len(reports), 1) if reports else 0
    top5 = sorted(reports, key=lambda r: r.savings_pct, reverse=True)[:5]

    # Статистика ответов за сутки
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    answers_today = db.query(QuestionAnswer).filter(
        QuestionAnswer.created_at >= today_start
    ).count()

    return {
        "month": month,
        "submitted_count": len(reports),
        "total_count": len(all_users),
        "avg_savings_pct": avg_savings,
        "avg_invest_pct": avg_invest,
        "answers_today": answers_today,
        "top5": [
            {"pid": r.user.pid, "first_name": r.user.first_name or "", "savings_pct": r.savings_pct}
            for r in top5
        ],
        "not_submitted": [
            {"pid": u.pid, "first_name": u.first_name or "", "telegram_username": u.telegram_username or ""}
            for u in sorted(not_submitted, key=lambda u: u.pid)
        ],
    }


class RecommendationRequest(BaseModel):
    pid: str
    text: str


@app.post("/admin/recommendations")
async def admin_set_recommendation(
    body: RecommendationRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.pid == body.pid.upper()).first()
    if not user:
        raise HTTPException(status_code=404, detail="Участник не найден")
    rec = db.query(Recommendation).filter(Recommendation.user_id == user.id).first()
    if rec:
        rec.text = body.text.strip()
        rec.updated_at = datetime.utcnow()
    else:
        rec = Recommendation(user_id=user.id, text=body.text.strip())
        db.add(rec)
    db.commit()
    if user.telegram_id and body.text.strip():
        await tg_send(user.telegram_id,
                      f"⭐ Анар оставил вам рекомендацию:\n\n{body.text.strip()}")
    return {"status": "ok"}


@app.get("/admin/recommendations/{pid}")
def admin_get_recommendation(
    pid: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.pid == pid.upper()).first()
    if not user:
        raise HTTPException(status_code=404, detail="Участник не найден")
    rec = db.query(Recommendation).filter(Recommendation.user_id == user.id).first()
    return {"pid": pid.upper(), "text": rec.text if rec else ""}


class BroadcastRequest(BaseModel):
    message: str


@app.post("/admin/broadcast")
async def admin_broadcast(
    body: BroadcastRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    import asyncio
    users = db.query(User).filter(User.telegram_id.isnot(None)).all()

    async def send_one(tg_id: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": tg_id, "text": body.message, "parse_mode": "HTML"},
                )
                return r.json().get("ok", False)
        except Exception:
            return False

    results = []
    for i in range(0, len(users), 25):
        batch = users[i:i + 25]
        batch_results = await asyncio.gather(*[send_one(u.telegram_id) for u in batch])
        results.extend(batch_results)
        if i + 25 < len(users):
            await asyncio.sleep(1)

    sent = sum(1 for r in results if r)
    return {"status": "ok", "sent": sent, "failed": len(results) - sent}


# ─── Движок рекомендаций знакомств ────────────────────────────────────────────

def _get_user_profile_text(u: User) -> str:
    """Текст профиля для эмбеддинга: профессия + навыки."""
    skills = [s.skill_name for s in u.skills_list]
    parts = ([u.profession] if u.profession else []) + skills
    return " ".join(parts) if parts else (u.pid or "")


def generate_introductions(db: Session) -> int:
    """Генерация рекомендаций знакомств на основе эмбеддингов профилей.
    Запускается cron-джобой раз в 14 дней.
    Возвращает количество созданных записей.
    """
    eligible = (
        db.query(User)
        .filter(User.intro_consent_given == True, User.intro_receive == True)
        .all()
    )
    if len(eligible) < 2:
        return 0

    # Эмбеддинги профилей (вычисляем один раз для всех)
    model = get_embed_model()
    texts = [_get_user_profile_text(u) for u in eligible]
    embeddings = model.encode(texts, normalize_embeddings=True)

    # Активные пользователи за последние 30 дней
    cutoff_30 = datetime.utcnow() - timedelta(days=30)
    active_ids = {
        row[0] for row in
        db.query(ClubQuestion.user_id).filter(ClubQuestion.created_at >= cutoff_30).all()
    }

    # Уже знакомые пары
    accepted_pairs = {
        (r.from_user_id, r.to_user_id)
        for r in db.query(ContactRequest).filter(ContactRequest.status == "accepted").all()
    }
    accepted_pairs |= {(b, a) for a, b in accepted_pairs}

    # Уже предложенные/отклонённые за 60 дней
    cutoff_60 = datetime.utcnow() - timedelta(days=60)
    skip_pairs = {
        (r.from_user_id, r.to_user_id)
        for r in db.query(Introduction).filter(
            Introduction.created_at >= cutoff_60,
            Introduction.status.in_(["accepted", "skipped"]),
        ).all()
    }

    skill_map = {u.id: set(s.skill_name for s in u.skills_list) for u in eligible}

    count = 0
    for i, u in enumerate(eligible):
        candidates = []
        for j, v in enumerate(eligible):
            if i == j:
                continue
            if (u.id, v.id) in accepted_pairs or (u.id, v.id) in skip_pairs:
                continue

            sim = float(np.dot(embeddings[i], embeddings[j]))

            skills_u = skill_map.get(u.id, set())
            skills_v = skill_map.get(v.id, set())
            union = skills_u | skills_v
            need_match = len(skills_u & skills_v) / max(len(union), 1)

            trust = min((v.answer_score or 0) / 20.0, 1.0)
            activity = 1.0 if (u.id in active_ids and v.id in active_ids) else 0.0

            score = 0.45 * sim + 0.25 * need_match + 0.15 * trust + 0.15 * activity

            common = skills_u & skills_v
            if common:
                reason = f"Общие темы: {', '.join(list(common)[:3])}"
            elif v.profession:
                reason = f"Похожая сфера: {v.profession}"
            else:
                reason = "Схожие интересы в клубе"

            candidates.append((score, v.id, reason))

        candidates.sort(key=lambda x: -x[0])
        for score, vid, reason in candidates[:3]:
            if score < 0.1:
                continue
            db.add(Introduction(
                from_user_id=vid,
                to_user_id=u.id,
                score=score,
                reason=reason,
                status="pending",
            ))
            count += 1

    db.commit()
    print(f"[intros] Сгенерировано {count} рекомендаций для {len(eligible)} участников")
    return count


async def _cron_generate_introductions():
    """Cron-обёртка: создаёт сессию БД и запускает генерацию."""
    db = SessionLocal()
    try:
        count = generate_introductions(db)
        print(f"[cron/intros] {count} рекомендаций создано")
        # Отправляем уведомления в бот
        await _notify_introductions(db)
    finally:
        db.close()


async def _notify_introductions(db: Session):
    """Отправляем уведомления пользователям о новых рекомендациях."""
    pending = (
        db.query(Introduction)
        .filter(Introduction.status == "pending")
        .all()
    )
    # Группируем по получателю
    by_user: dict[int, list] = {}
    for intro in pending:
        by_user.setdefault(intro.to_user_id, []).append(intro)

    for to_user_id, intros in by_user.items():
        to_user = db.query(User).get(to_user_id)
        if not to_user or not to_user.telegram_id:
            continue

        lines = []
        keyboard_rows = []
        for intro in intros[:3]:
            fu = intro.from_user
            name = f"{fu.first_name or ''} {fu.last_name or ''}".strip() or fu.pid
            prof = fu.profession or "—"
            score_str = f"⭐ {fu.answer_score}" if fu.answer_score else ""
            lines.append(f"👤 <b>{name}</b> · {prof} {score_str}\n   {intro.reason}")
            keyboard_rows.append([
                {"text": "👋 Познакомиться", "callback_data": f"intro_accept_{intro.id}"},
                {"text": "Пропустить",       "callback_data": f"intro_skip_{intro.id}"},
            ])
            intro.status = "sent"

        db.commit()

        text = (
            f"🔥 Клуб подобрал тебе {len(intros[:3])} "
            f"{'человека' if len(intros[:3]) > 1 else 'человека'}, "
            f"с которыми может быть полезно познакомиться:\n\n" +
            "\n\n".join(lines)
        )
        await tg_send(to_user.telegram_id, text, reply_markup={"inline_keyboard": keyboard_rows})


# ─── Cron scheduler ───────────────────────────────────────────────────────────

_scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

@app.on_event("startup")
async def start_scheduler():
    _scheduler.add_job(
        _cron_generate_introductions,
        trigger="interval",
        days=14,
        id="generate_intros",
        replace_existing=True,
    )
    _scheduler.start()
    print("[scheduler] Запущен. Генерация интро каждые 14 дней.")


@app.on_event("shutdown")
async def stop_scheduler():
    _scheduler.shutdown(wait=False)


# ─── Game: Multiplayer Monopoly ───────────────────────────────────────────────

async def tg_send_game_invite(to_telegram_id: str, host_name: str, session_id: str):
    """Отправляет Telegram-уведомление с приглашением в игру."""
    app_url = f"http://45.131.186.158/fire35-app/?game={session_id}"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": to_telegram_id,
                    "text": f"🎲 {host_name} приглашает вас сыграть в Монополию FIRE35!",
                    "reply_markup": {
                        "inline_keyboard": [[{
                            "text": "🎲 Играть!",
                            "web_app": {"url": app_url}
                        }]]
                    }
                }
            )
    except Exception as e:
        print(f"[game invite] TG error: {e}")


@app.post("/game/new")
def create_game_session(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Хост создаёт новую игровую сессию."""
    # Удаляем старые сессии в статусе waiting от этого пользователя
    old = db.query(GameSession).filter(
        GameSession.host_user_id == user.id,
        GameSession.status == "waiting",
    ).first()
    if old:
        db.delete(old)
    session = GameSession(
        id=str(uuid.uuid4()),
        host_user_id=user.id,
        status="waiting",
    )
    db.add(session)
    db.commit()
    return {"session_id": session.id}


@app.post("/game/invite/{pid}")
async def invite_to_game(
    pid: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Хост приглашает участника (по pid). Создаёт/переиспользует сессию, шлёт TG."""
    target = db.query(User).filter(User.pid == pid).first()
    if not target:
        raise HTTPException(404, "User not found")

    # Получить или создать waiting-сессию хоста
    session = db.query(GameSession).filter(
        GameSession.host_user_id == user.id,
        GameSession.status == "waiting",
    ).first()
    if not session:
        session = GameSession(id=str(uuid.uuid4()), host_user_id=user.id, status="waiting")
        db.add(session)
        db.commit()
        db.refresh(session)

    host_name = user.first_name or user.username or "Участник"

    if target.telegram_id:
        await tg_send_game_invite(target.telegram_id, host_name, session.id)

    return {"session_id": session.id, "ok": True}


@app.post("/game/join/{session_id}")
def join_game_session(
    session_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Гость принимает приглашение и присоединяется к сессии."""
    session = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    if session.status != "waiting":
        raise HTTPException(400, "Session already started or finished")
    if session.host_user_id == user.id:
        raise HTTPException(400, "Cannot join your own session")

    session.guest_user_id = user.id
    session.status = "active"
    session.updated_at = datetime.utcnow()
    db.commit()

    host = db.query(User).filter(User.id == session.host_user_id).first()
    return {
        "session_id": session.id,
        "player_index": 1,
        "host_name": host.first_name or host.username or "Хост" if host else "Хост",
        "state": json.loads(session.state_json) if session.state_json else None,
    }


@app.get("/game/session/{session_id}")
def get_game_session(
    session_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Получить текущий статус и стейт сессии."""
    session = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")

    host = db.query(User).filter(User.id == session.host_user_id).first()
    guest = db.query(User).filter(User.id == session.guest_user_id).first() if session.guest_user_id else None

    return {
        "session_id": session.id,
        "status": session.status,
        "host_name": host.first_name or host.username or "Хост" if host else "Хост",
        "guest_name": guest.first_name or guest.username or "Гость" if guest else None,
        "state": json.loads(session.state_json) if session.state_json else None,
    }


class GameActionPayload(BaseModel):
    state: dict


@app.post("/game/action/{session_id}")
def post_game_action(
    session_id: str,
    payload: GameActionPayload,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Игрок отправляет обновлённый стейт игры."""
    session = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    if user.id not in (session.host_user_id, session.guest_user_id):
        raise HTTPException(403, "Not a participant")
    if session.status not in ("waiting", "active"):
        raise HTTPException(400, "Session is finished")

    session.state_json = json.dumps(payload.state)
    session.updated_at = datetime.utcnow()
    if session.status == "waiting":
        session.status = "active"
    if payload.state.get("phase") == "gameover":
        session.status = "finished"
    db.commit()
    return {"ok": True}


@app.get("/game/my")
def my_active_game(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Возвращает активную игровую сессию пользователя (если есть)."""
    from sqlalchemy import or_
    session = db.query(GameSession).filter(
        or_(GameSession.host_user_id == user.id, GameSession.guest_user_id == user.id),
        GameSession.status.in_(["waiting", "active"]),
    ).order_by(GameSession.created_at.desc()).first()

    if not session:
        return {"session": None}

    host = db.query(User).filter(User.id == session.host_user_id).first()
    guest = db.query(User).filter(User.id == session.guest_user_id).first() if session.guest_user_id else None
    is_host = session.host_user_id == user.id

    return {
        "session": {
            "session_id": session.id,
            "status": session.status,
            "player_index": 0 if is_host else 1,
            "host_name": host.first_name or "Хост" if host else "Хост",
            "guest_name": guest.first_name or "Гость" if guest else None,
            "state": json.loads(session.state_json) if session.state_json else None,
        }
    }


# ─── Admin: ручной запуск ─────────────────────────────────────────────────────

@app.post("/admin/generate-introductions")
async def admin_generate_introductions(
    token: str = Header(None, alias="X-Admin-Token"),
    db: Session = Depends(get_db),
):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    count = generate_introductions(db)
    await _notify_introductions(db)
    return {"generated": count}


# ─── AI Батл ──────────────────────────────────────────────────────────────────

# Начальные задания для недель (при первом запуске сидируются в БД)
_SEED_CHALLENGES = [
    {
        "week": "2026-W11",
        "theme": "Промпт-инжиниринг: базовый",
        "task": (
            "Напиши промпт для ChatGPT/Claude, чтобы он составил "
            "персональный план выхода на пассивный доход за 5 лет. "
            "Учти, что стартовый капитал — 500 000 ₽, ежемесячные "
            "накопления — 30 000 ₽, цель — 100 000 ₽/месяц пассивного дохода."
        ),
        "criteria_json": json.dumps([
            {"name": "Роль",        "max": 20, "hint": "Задана роль (финансовый советник, FIRE-ментор и т.п.)"},
            {"name": "Контекст",    "max": 25, "hint": "Указаны конкретные цифры: капитал, накопления, цель"},
            {"name": "Формат",      "max": 20, "hint": "Явно запрошен формат вывода (план по шагам, таблица, markdown)"},
            {"name": "Ограничения", "max": 15, "hint": "Указаны ограничения или допущения (страна, горизонт, риск)"},
            {"name": "Примеры",     "max": 20, "hint": "Добавлен пример или шаблон ожидаемого ответа"},
        ], ensure_ascii=False),
    },
    {
        "week": "2026-W12",
        "theme": "AI для анализа инвестиций",
        "task": (
            "Напиши промпт, который попросит AI проанализировать "
            "инвестиционный тезис: стоит ли купить ETF на S&P 500 "
            "прямо сейчас, если горизонт — 10 лет и риск — умеренный."
        ),
        "criteria_json": json.dumps([
            {"name": "Роль",         "max": 20, "hint": "Задана роль аналитика или инвест-советника"},
            {"name": "Тезис",        "max": 25, "hint": "Чётко сформулирован тезис для анализа"},
            {"name": "Параметры",    "max": 20, "hint": "Указаны горизонт и уровень риска"},
            {"name": "Формат",       "max": 20, "hint": "Запрошены аргументы «за» и «против» + итоговый вывод"},
            {"name": "Нейтральность","max": 15, "hint": "Промпт не подталкивает к заранее нужному ответу"},
        ], ensure_ascii=False),
    },
    {
        "week": "2026-W13",
        "theme": "Автоматизация личных финансов",
        "task": (
            "Напиши промпт, который заставит AI создать "
            "Excel/Google Sheets шаблон для трекинга личного бюджета "
            "в стиле FIRE: доходы, расходы, норма сбережений, "
            "инвестиционный портфель, прогресс к FIRE-цели."
        ),
        "criteria_json": json.dumps([
            {"name": "Роль",         "max": 15, "hint": "Задана роль (эксперт по личным финансам, FIRE-коуч)"},
            {"name": "Структура",    "max": 30, "hint": "Перечислены все нужные вкладки/секции шаблона"},
            {"name": "FIRE-метрики", "max": 25, "hint": "Упомянуты FIRE-специфичные метрики (норма сбережений, FI number)"},
            {"name": "Формат",       "max": 15, "hint": "Явно запрошен формат (таблица, формулы, инструкция)"},
            {"name": "Пример",       "max": 15, "hint": "Дан пример заполнения или тестовые данные"},
        ], ensure_ascii=False),
    },
]


def _get_current_week() -> str:
    """Возвращает текущую ISO неделю в формате '2026-W11'."""
    now = datetime.utcnow()
    iso = now.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _seed_challenges(db: Session) -> None:
    """Добавляет стартовые задания если их нет."""
    for ch in _SEED_CHALLENGES:
        exists = db.query(AiBattleChallenge).filter(
            AiBattleChallenge.week == ch["week"]
        ).first()
        if not exists:
            db.add(AiBattleChallenge(**ch))
    db.commit()


class AiBattleSubmitIn(BaseModel):
    prompt_text: str


@app.get("/ai-battle/current")
def ai_battle_current(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Возвращает задание текущей недели и попытку пользователя (если есть)."""
    _seed_challenges(db)
    week = _get_current_week()
    challenge = db.query(AiBattleChallenge).filter(
        AiBattleChallenge.week == week
    ).first()
    if not challenge:
        raise HTTPException(404, "Задание на эту неделю ещё не опубликовано")

    submission = db.query(AiBattleSubmission).filter(
        AiBattleSubmission.challenge_id == challenge.id,
        AiBattleSubmission.user_id == user.id,
    ).first()

    return {
        "challenge": {
            "id": challenge.id,
            "week": challenge.week,
            "theme": challenge.theme,
            "task": challenge.task,
            "criteria": json.loads(challenge.criteria_json),
        },
        "submission": {
            "score": submission.score,
            "prompt_text": submission.prompt_text,
            "feedback": json.loads(submission.feedback_json) if submission.feedback_json else None,
        } if submission else None,
    }


TRAINER_TOPICS = {
    "investments": {
        "title": "💰 Инвестиции",
        "scenario": "У тебя 300 000 руб. Ты хочешь составить диверсифицированный портфель на 3 года с умеренным риском. Напиши промпт для AI-советника по инвестициям.",
        "criteria": [
            {"name": "Роль", "max": 20, "hint": "задал ли роль AI (советник, эксперт, ментор)"},
            {"name": "Контекст", "max": 25, "hint": "сумма, срок, цель, риск-профиль"},
            {"name": "Формат", "max": 20, "hint": "таблица, список шагов, конкретный вывод"},
            {"name": "Ограничения", "max": 15, "hint": "страна, налоги, запреты на активы"},
            {"name": "Примеры", "max": 20, "hint": "пример желаемого ответа или инструменты"},
        ],
    },
    "budget": {
        "title": "📊 Бюджет",
        "scenario": "Твои расходы каждый месяц превышают доходы на 10-15%. Напиши промпт для AI-аналитика, который поможет найти утечки и оптимизировать бюджет.",
        "criteria": [
            {"name": "Роль", "max": 20, "hint": "финансовый аналитик, коуч по бюджету"},
            {"name": "Контекст", "max": 25, "hint": "доходы, статьи расходов, цель экономии"},
            {"name": "Формат", "max": 20, "hint": "таблица категорий, процент сокращения"},
            {"name": "Ограничения", "max": 15, "hint": "обязательные расходы, не трогать"},
            {"name": "Примеры", "max": 20, "hint": "пример анализа или конкретные цифры"},
        ],
    },
    "realestate": {
        "title": "🏠 Недвижимость",
        "scenario": "Рассматриваешь покупку квартиры для сдачи в аренду за 5 млн руб. Хочешь понять — выгодно ли это и как посчитать доходность. Напиши промпт для AI-эксперта.",
        "criteria": [
            {"name": "Роль", "max": 20, "hint": "эксперт по недвижимости, инвест-аналитик"},
            {"name": "Контекст", "max": 25, "hint": "цена, локация, ипотека или нет, аренда"},
            {"name": "Формат", "max": 20, "hint": "расчёт ROI, срок окупаемости, риски"},
            {"name": "Ограничения", "max": 15, "hint": "бюджет, регион, тип объекта"},
            {"name": "Примеры", "max": 20, "hint": "пример расчёта доходности"},
        ],
    },
    "career": {
        "title": "💼 Карьера",
        "scenario": "Ты работаешь 3 года на одном месте, зарплата не растёт. Хочешь либо повысить зарплату на 30%, либо сменить компанию. Напиши промпт для AI-карьерного консультанта.",
        "criteria": [
            {"name": "Роль", "max": 20, "hint": "HR-консультант, карьерный коуч"},
            {"name": "Контекст", "max": 25, "hint": "опыт, навыки, текущая зп, цель"},
            {"name": "Формат", "max": 20, "hint": "план действий, скрипт переговоров"},
            {"name": "Ограничения", "max": 15, "hint": "сфера, город, что нельзя менять"},
            {"name": "Примеры", "max": 20, "hint": "пример аргументов или письма"},
        ],
    },
    "mindset": {
        "title": "🧠 Психология денег",
        "scenario": "Ты зарабатываешь достаточно, но деньги «утекают» — импульсивные покупки, нет подушки. Хочешь изменить отношение к деньгам. Напиши промпт для AI-коуча.",
        "criteria": [
            {"name": "Роль", "max": 20, "hint": "психолог, финансовый коуч, ментор"},
            {"name": "Контекст", "max": 25, "hint": "паттерны поведения, триггеры, цели"},
            {"name": "Формат", "max": 20, "hint": "практики, упражнения, конкретные шаги"},
            {"name": "Ограничения", "max": 15, "hint": "что пробовал, что не работает"},
            {"name": "Примеры", "max": 20, "hint": "пример техники или вопроса для рефлексии"},
        ],
    },
}


class TrainerIn(BaseModel):
    topic_id: str
    prompt_text: str
    custom_scenario: Optional[str] = None  # если задан — используем его вместо дефолтного


@app.post("/ai-battle/trainer/generate-scenario")
async def generate_personal_scenario(
    body: dict,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """RAG-персонализация: находит вопросы клуба близкие к профилю,
    использует их как контекст для генерации уникального сценария."""
    topic_id = body.get("topic_id")  # опционально — если не передан, выбираем лучшую тему
    topic = TRAINER_TOPICS.get(topic_id) if topic_id else None

    # ── 1. Профиль пользователя ──────────────────────────────
    # Явный запрос навыков — не через lazy relationship
    user_skills = [s.skill_name for s in db.query(UserSkill).filter(UserSkill.user_id == user.id).all()]
    # Все отчёты, свежий первый
    all_reps = db.query(Report).filter(Report.user_id == user.id).order_by(Report.month.desc()).limit(6).all()
    latest_rep = all_reps[0] if all_reps else None
    reports_count = len(all_reps)
    past_attempts_all = db.query(TrainerAttempt).filter(TrainerAttempt.user_id == user.id).all()
    tried_topics = {a.topic_id for a in past_attempts_all}

    # Финансовая картина из отчётов
    fin_parts = []
    fin_rag_parts = []  # для RAG-поиска — более развёрнуто
    if latest_rep:
        if (latest_rep.savings_pct or 0) > 0:
            fin_parts.append(f"сбережения {latest_rep.savings_pct}% дохода")
            fin_rag_parts.append(f"откладывает {latest_rep.savings_pct}% сбережения накопления")
        if (latest_rep.invest_pct or 0) > 0:
            fin_parts.append(f"инвестирует {latest_rep.invest_pct}% дохода")
            fin_rag_parts.append(f"инвестирует {latest_rep.invest_pct}% портфель инвестиции")
        if latest_rep.budget_yes:
            fin_parts.append("ведёт бюджет")
            fin_rag_parts.append("ведёт бюджет планирование расходов")
        if not latest_rep.income_gt_expense:
            fin_parts.append("расходы превышают доходы")
            fin_rag_parts.append("расходы больше доходов дефицит бюджет")
        elif latest_rep.income_gt_expense:
            fin_rag_parts.append("доходы больше расходов профицит")
        # Динамика сбережений
        if len(all_reps) >= 2:
            avg_sav = sum(r.savings_pct or 0 for r in all_reps) / len(all_reps)
            fin_parts.append(f"средние сбережения {round(avg_sav, 1)}% за {len(all_reps)} мес.")

    profile_parts = []
    if user.profession:
        profile_parts.append(f"профессия: {user.profession}")
    if user_skills:
        profile_parts.append(f"навыки: {', '.join(user_skills[:10])}")
    if fin_parts:
        profile_parts.append("финансы: " + ", ".join(fin_parts))
    if reports_count:
        profile_parts.append(f"отчётов в клубе: {reports_count}")
    profile_str = "; ".join(profile_parts) if profile_parts else "новый участник"
    print(f"[RAG-SCENARIO] user={user.pid} profile_str={profile_str!r}", flush=True)

    # ── 2. Если тема не передана — выбираем ту, где меньше попыток или нет совсем ──
    if not topic:
        untried = [tid for tid in TRAINER_TOPICS if tid not in tried_topics]
        topic_id = untried[0] if untried else list(TRAINER_TOPICS.keys())[0]
        topic = TRAINER_TOPICS[topic_id]

    # ── 3. RAG: ищем релевантные вопросы клуба через эмбединги ──
    # Строим максимально богатый search_text: профессия + навыки + финансы + тема
    skill_text = " ".join(user_skills[:10]) if user_skills else ""
    fin_rag_text = " ".join(fin_rag_parts) if fin_rag_parts else ""
    profession_text = user.profession or ""
    search_text = f"{profession_text} {skill_text} {fin_rag_text} {topic['title']} {topic_id}".strip()
    print(f"[RAG-SCENARIO] search_text={search_text!r}", flush=True)

    rag_context = ""
    try:
        model = get_embed_model()
        query_emb = model.encode(search_text, normalize_embeddings=True).astype("float32")

        # Берём все эмбединги вопросов клуба
        all_qe = db.query(QuestionEmbedding).all()
        if all_qe:
            import numpy as np
            sims = []
            for qe in all_qe:
                stored = np.frombuffer(qe.embedding, dtype=np.float32)
                sim = float(np.dot(query_emb, stored))
                sims.append((sim, qe.question_id))
            sims.sort(reverse=True)
            top_qids = [qid for _, qid in sims[:5]]

            # Загружаем топ вопросы + лучшие ответы
            rag_lines = []
            for qid in top_qids:
                q = db.query(ClubQuestion).filter(ClubQuestion.id == qid).first()
                if not q:
                    continue
                best_ans = db.query(QuestionAnswer).filter(
                    QuestionAnswer.question_id == qid,
                    QuestionAnswer.is_useful == True,
                ).first()
                if not best_ans:
                    best_ans = db.query(QuestionAnswer).filter(
                        QuestionAnswer.question_id == qid,
                    ).order_by(QuestionAnswer.id.desc()).first()
                ans_text = best_ans.answer[:150] if best_ans else "без ответа"
                rag_lines.append(f"• Вопрос: {q.question[:120]} → {ans_text}")
            if rag_lines:
                rag_context = "РЕАЛЬНЫЕ ВОПРОСЫ УЧАСТНИКОВ КЛУБА (используй как вдохновение):\n" + "\n".join(rag_lines)
    except Exception:
        pass  # если модель не загружена — работаем без RAG

    # ── 4. История попыток по теме ────────────────────────────
    past = db.query(TrainerAttempt).filter(
        TrainerAttempt.user_id == user.id,
        TrainerAttempt.topic_id == topic_id,
    ).order_by(TrainerAttempt.created_at.desc()).limit(3).all()
    difficulty = "базовый"
    if len(past) >= 3:
        avg = sum(a.score for a in past) / len(past)
        difficulty = "продвинутый (усложни задачу)" if avg > 60 else "средний"
    elif len(past) >= 1:
        difficulty = "средний"

    # ── 5. Генерируем сценарий ────────────────────────────────
    gen_prompt = f"""Ты создаёшь персонализированное задание для финансового тренажёра промпт-инжиниринга.

ТЕМА: {topic['title']}
УРОВЕНЬ СЛОЖНОСТИ: {difficulty}
ПРОФИЛЬ УЧАСТНИКА: {profile_str}
ПОПЫТОК ПО ТЕМЕ: {len(past)}

{rag_context}

ТРЕБОВАНИЯ:
- Используй ТОЛЬКО данные из профиля выше — никаких выдуманных цифр, предположений или типичных шаблонов
- Если данных нет (пустые поля) — не упоминай их вообще
- Вставляй реальные цифры прямо в текст: "ты откладываешь X%", "инвестируешь Y%"
- Профессия и навыки должны быть в контексте задачи
- НЕ копируй и не перефразируй стандартный сценарий: "{topic['scenario']}"
- 2-3 предложения. Последнее: "Напиши промпт для AI-[роль]."
- Только текст, без markdown и пояснений

Сценарий:"""

    print(f"[RAG-SCENARIO] gen_prompt[:400]={gen_prompt[:400]!r}", flush=True)
    scenario = None
    try:
        async with httpx.AsyncClient(timeout=40) as http_client:
            resp = await http_client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}",
                         "HTTP-Referer": "https://fire35club.duckdns.org", "X-Title": "FIRE35"},
                json={"model": "google/gemini-2.5-flash", "max_tokens": 300,
                      "messages": [{"role": "user", "content": gen_prompt}]},
            )
        rj = resp.json()
        print(f"[RAG-SCENARIO] API status={resp.status_code} keys={list(rj.keys())} body={str(rj)[:200]}", flush=True)
        scenario = rj["choices"][0]["message"]["content"].strip()
        scenario = scenario.strip('"\'').replace("**", "").replace("##", "").replace("*", "")
        print(f"[RAG-SCENARIO] RESULT={scenario!r}", flush=True)
    except Exception as e:
        print(f"[RAG-SCENARIO] ERROR={e!r}", flush=True)
    if not scenario:
        # Финальный fallback с данными профиля
        fin_str = "; ".join(fin_parts) if fin_parts else ""
        skills_str = ", ".join(user_skills[:5]) if user_skills else ""
        scenario = topic["scenario"]
        if user.profession:
            scenario = f"Ты — {user.profession}"
            if skills_str:
                scenario += f" ({skills_str})"
            if fin_str:
                scenario += f". {fin_str}."
            scenario += " " + topic["scenario"]

    return {
        "scenario": scenario,
        "topic_id": topic_id,
        "title": topic["title"],
        "criteria": topic["criteria"],
        "is_personalized": True,
        "rag_used": bool(rag_context),
    }


@app.post("/ai-battle/trainer")
async def ai_battle_trainer(
    body: TrainerIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Тренажёр: оценивает промпт по выбранной теме без сохранения в БД."""
    topic = TRAINER_TOPICS.get(body.topic_id)
    if not topic:
        raise HTTPException(400, "Неизвестная тема")
    if not body.prompt_text or len(body.prompt_text.strip()) < 10:
        raise HTTPException(400, "Промпт слишком короткий")

    criteria_desc = "\n".join(
        f"- {c['name']} (макс {c['max']} баллов): {c['hint']}"
        for c in topic["criteria"]
    )
    total_max = sum(c["max"] for c in topic["criteria"])

    # Профиль пользователя для персонализации
    user_skills = [s.skill_name for s in user.skills_list] if user.skills_list else []
    latest_rep = db.query(Report).filter(Report.user_id == user.id).order_by(Report.month.desc()).first()
    profile_ctx = f"Профессия участника: {user.profession or 'не указана'}."
    if user_skills:
        profile_ctx += f" Темы/навыки: {', '.join(user_skills[:5])}."
    if latest_rep:
        invest_info = []
        if latest_rep.invest_pct: invest_info.append(f"инвестирует {latest_rep.invest_pct}% дохода")
        if latest_rep.budget_yes: invest_info.append("ведёт бюджет")
        if invest_info:
            profile_ctx += f" Финансовый профиль: {', '.join(invest_info)}."

    # Используем кастомный сценарий если передан, иначе стандартный
    scenario_text = body.custom_scenario.strip() if body.custom_scenario else topic["scenario"]

    eval_prompt = f"""Ты — строгий судья промпт-инжиниринга. Оцени промпт участника для темы "{topic['title']}".

ПРОФИЛЬ УЧАСТНИКА (учитывай при оценке релевантности):
{profile_ctx}

ЗАДАНИЕ ДЛЯ УЧАСТНИКА:
{scenario_text}

ПРОМПТ УЧАСТНИКА:
{body.prompt_text}

КРИТЕРИИ (оцени каждый строго):
{criteria_desc}

Верни ТОЛЬКО валидный JSON без пояснений:
{{
  "scores": {{{", ".join(f'"{c["name"]}": <0-{c["max"]}>' for c in topic["criteria"])}}},
  "total": <сумма баллов 0-{total_max}>,
  "verdict": "<одна фраза итого>",
  "strengths": "<что сделано хорошо>",
  "improvements": "<конкретно что добавить>"
}}"""

    try:
        async with httpx.AsyncClient(timeout=30) as http_client:
            resp = await http_client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "HTTP-Referer": "https://fire35club.duckdns.org", "X-Title": "FIRE35"},
                json={"model": "google/gemini-2.5-flash", "max_tokens": 600,
                      "messages": [{"role": "system", "content": "Отвечай без markdown-форматирования. Не используй звёздочки, решётки, курсив. В JSON-полях пиши чистый текст."}, {"role": "user", "content": eval_prompt}]},
            )
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        start, end = raw.find("{"), raw.rfind("}") + 1
        feedback = json.loads(raw[start:end])
        score = min(int(feedback.get("total", 0)), total_max)
    except Exception:
        raise HTTPException(502, "Ошибка AI-оценки. Попробуйте ещё раз.")

    # Сохраняем попытку
    attempt = TrainerAttempt(
        user_id=user.id,
        topic_id=body.topic_id,
        score=score,
        max_score=total_max,
        prompt_text=body.prompt_text,
        feedback_json=json.dumps(feedback, ensure_ascii=False),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return {
        "attempt_id": attempt.id,
        "score": score,
        "max": total_max,
        "feedback": feedback,
        "criteria": topic["criteria"],
    }


@app.get("/ai-battle/trainer/history")
def trainer_history(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """История попыток участника в тренажёре, сгруппированная по темам."""
    attempts = (
        db.query(TrainerAttempt)
        .filter(TrainerAttempt.user_id == user.id)
        .order_by(TrainerAttempt.created_at.desc())
        .limit(100)
        .all()
    )
    result = {}
    for a in attempts:
        if a.topic_id not in result:
            result[a.topic_id] = []
        result[a.topic_id].append({
            "id": a.id,
            "score": a.score,
            "max": a.max_score,
            "prompt_text": a.prompt_text,
            "feedback": json.loads(a.feedback_json) if a.feedback_json else None,
            "created_at": a.created_at.strftime("%d.%m %H:%M") if a.created_at else "",
        })
    return result


class IdealPromptIn(BaseModel):
    topic_id: str


@app.post("/ai-battle/trainer/ideal")
async def trainer_ideal(
    body: IdealPromptIn,
    user: User = Depends(current_user),
):
    """Генерирует эталонный промпт для выбранной темы."""
    topic = TRAINER_TOPICS.get(body.topic_id)
    if not topic:
        raise HTTPException(400, "Неизвестная тема")

    criteria_names = ", ".join(c["name"] for c in topic["criteria"])
    gen_prompt = f"""Ты — эксперт по промпт-инжинирингу. Напиши ЭТАЛОННЫЙ промпт для следующего сценария.

ТЕМА: {topic["title"]}
ЗАДАНИЕ: {topic["scenario"]}
КРИТЕРИИ ОЦЕНКИ: {criteria_names}

Требования к эталонному промпту:
- Чётко задана роль AI
- Конкретный контекст с цифрами
- Указан желаемый формат вывода
- Есть ограничения/условия
- Есть пример или образец ответа
- Написан на русском языке
- Длина 150-300 слов

Верни ТОЛЬКО сам промпт, без пояснений и без заголовков."""

    try:
        async with httpx.AsyncClient(timeout=30) as http_client:
            resp = await http_client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "HTTP-Referer": "https://fire35club.duckdns.org", "X-Title": "FIRE35"},
                json={"model": "google/gemini-2.5-flash", "max_tokens": 500,
                      "messages": [
                          {"role": "system", "content": "Отвечай только простым текстом. Не используй markdown, звёздочки, решётки, курсив и другие символы форматирования."},
                          {"role": "user", "content": gen_prompt},
                      ]},
            )
        ideal_text = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        raise HTTPException(502, "Ошибка генерации. Попробуйте ещё раз.")

    return {"ideal_prompt": ideal_text}


class RunPromptIn(BaseModel):
    topic_id: str
    prompt_text: str


@app.post("/ai-battle/trainer/run")
async def trainer_run_prompt(
    body: RunPromptIn,
    user: User = Depends(current_user),
):
    """Выполняет промпт участника и возвращает реальный ответ AI."""
    topic = TRAINER_TOPICS.get(body.topic_id)
    if not topic:
        raise HTTPException(400, "Неизвестная тема")
    if not body.prompt_text or len(body.prompt_text.strip()) < 10:
        raise HTTPException(400, "Промпт слишком короткий")

    try:
        async with httpx.AsyncClient(timeout=40) as http_client:
            resp = await http_client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "HTTP-Referer": "https://fire35club.duckdns.org", "X-Title": "FIRE35"},
                json={"model": "google/gemini-2.5-flash", "max_tokens": 800,
                      "messages": [
                          {"role": "system", "content": "Отвечай только простым текстом. Не используй markdown, звёздочки, решётки, курсив и другие символы форматирования."},
                          {"role": "user", "content": body.prompt_text},
                      ]},
            )
        ai_response = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        raise HTTPException(502, "Ошибка AI. Попробуйте ещё раз.")

    return {"response": ai_response}


@app.post("/ai-battle/submit")
async def ai_battle_submit(
    body: AiBattleSubmitIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Принимает промпт, оценивает через Groq, сохраняет результат."""
    if not body.prompt_text or len(body.prompt_text.strip()) < 10:
        raise HTTPException(400, "Промпт слишком короткий")
    if len(body.prompt_text) > 3000:
        raise HTTPException(400, "Промпт слишком длинный (макс. 3000 символов)")

    _seed_challenges(db)
    week = _get_current_week()
    challenge = db.query(AiBattleChallenge).filter(
        AiBattleChallenge.week == week
    ).first()
    if not challenge:
        raise HTTPException(404, "Задание на эту неделю не найдено")

    # Проверяем есть ли уже попытка
    existing = db.query(AiBattleSubmission).filter(
        AiBattleSubmission.challenge_id == challenge.id,
        AiBattleSubmission.user_id == user.id,
    ).first()

    criteria = json.loads(challenge.criteria_json)
    criteria_text = "\n".join(
        f"- {c['name']} (макс. {c['max']} баллов): {c['hint']}"
        for c in criteria
    )
    total_max = sum(c["max"] for c in criteria)

    eval_prompt = f"""Ты эксперт по промпт-инжинирингу. Оцени промпт участника по критериям.

ЗАДАНИЕ НЕДЕЛИ:
{challenge.task}

КРИТЕРИИ ОЦЕНКИ (итого максимум {total_max} баллов):
{criteria_text}

ПРОМПТ УЧАСТНИКА:
{body.prompt_text}

Верни ТОЛЬКО валидный JSON без лишнего текста в таком формате:
{{
  "scores": {{
    "Роль": <число>,
    "Контекст": <число>,
    ...
  }},
  "total": <сумма>,
  "strengths": "<1-2 предложения что сделано хорошо>",
  "improvements": "<1-2 конкретных совета что улучшить>",
  "verdict": "<одна фраза-оценка уровня участника>"
}}

Имена ключей в scores должны совпадать с именами критериев выше. Будь объективен и конструктивен."""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "HTTP-Referer": "https://fire35club.duckdns.org", "X-Title": "FIRE35"},
                json={"model": "google/gemini-2.5-flash", "max_tokens": 600,
                      "messages": [{"role": "system", "content": "Отвечай без markdown-форматирования. Не используй звёздочки, решётки, курсив. В JSON-полях пиши чистый текст."}, {"role": "user", "content": eval_prompt}]},
            )
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        start, end = raw.find("{"), raw.rfind("}") + 1
        feedback = json.loads(raw[start:end])
        score = min(int(feedback.get("total", 0)), total_max)
    except Exception:
        raise HTTPException(502, "Ошибка оценки AI. Попробуйте ещё раз.")

    feedback_str = json.dumps(feedback, ensure_ascii=False)

    if existing:
        existing.prompt_text = body.prompt_text
        existing.score = score
        existing.feedback_json = feedback_str
        existing.submitted_at = datetime.utcnow()
    else:
        db.add(AiBattleSubmission(
            challenge_id=challenge.id,
            user_id=user.id,
            prompt_text=body.prompt_text,
            score=score,
            feedback_json=feedback_str,
        ))
    db.commit()

    return {
        "score": score,
        "max": total_max,
        "feedback": feedback,
    }


@app.get("/ai-battle/leaderboard")
def ai_battle_leaderboard(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Топ-15 участников за текущую неделю."""
    _seed_challenges(db)
    week = _get_current_week()
    challenge = db.query(AiBattleChallenge).filter(
        AiBattleChallenge.week == week
    ).first()
    if not challenge:
        return {"week": week, "entries": []}

    rows = (
        db.query(AiBattleSubmission, User)
        .join(User, AiBattleSubmission.user_id == User.id)
        .filter(AiBattleSubmission.challenge_id == challenge.id)
        .order_by(AiBattleSubmission.score.desc())
        .limit(15)
        .all()
    )

    entries = []
    for rank, (sub, u) in enumerate(rows, 1):
        entries.append({
            "rank": rank,
            "pid": u.pid,
            "name": u.first_name or u.pid,
            "score": sub.score,
            "is_me": u.id == user.id,
        })

    return {"week": week, "theme": challenge.theme, "entries": entries}


# ─── Онбординг (AI-оценка первого промпта) ────────────────────────────────────

class OnboardingEvalIn(BaseModel):
    prompt_text: str


@app.post("/onboarding/evaluate")
async def onboarding_evaluate(
    body: OnboardingEvalIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Оценивает вводный промпт, извлекает данные профиля, возвращает скор."""
    if not body.prompt_text or len(body.prompt_text.strip()) < 10:
        raise HTTPException(400, "Сообщение слишком короткое")

    eval_prompt = f"""Ты — AI-аналитик клуба FIRE35. Участник написал о себе своими словами.
Твоя задача: оценить его как "промпт" (0-100) и извлечь данные профиля.

СООБЩЕНИЕ УЧАСТНИКА:
{body.prompt_text}

Оцени по критериям:
- Конкретность: указаны конкретные факты (имя, профессия, цифры, сроки)
- Структурированность: информация понятно организована
- Полнота: охвачены разные аспекты (кто он, что умеет, что хочет)
- Ясность: легко понять и использовать для AI

Верни ТОЛЬКО валидный JSON:
{{
  "score": <0-100>,
  "verdict": "<одна фраза про уровень участника>",
  "recommendation": "<1-2 конкретных совета как улучшить>",
  "extracted": {{
    "first_name": "<имя или null>",
    "profession": "<профессия/сфера или null>",
    "skills": ["<навык1>", "<навык2>"],
    "goal": "<цель/мотивация или null>"
  }}
}}"""

    try:
        async with httpx.AsyncClient(timeout=30) as http_client:
            resp = await http_client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "HTTP-Referer": "https://fire35club.duckdns.org", "X-Title": "FIRE35"},
                json={"model": "google/gemini-2.5-flash", "max_tokens": 600,
                      "messages": [{"role": "system", "content": "Отвечай без markdown-форматирования. Не используй звёздочки, решётки, курсив. В JSON-полях пиши чистый текст."}, {"role": "user", "content": eval_prompt}]},
            )
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        start, end = raw.find("{"), raw.rfind("}") + 1
        result = json.loads(raw[start:end])
        score = min(max(int(result.get("score", 0)), 0), 100)
    except Exception:
        raise HTTPException(502, "Ошибка AI-оценки. Попробуйте ещё раз.")

    # Обновляем профиль из извлечённых данных (только пустые поля)
    extracted = result.get("extracted", {})
    updated = False
    if extracted.get("first_name") and not user.first_name:
        user.first_name = extracted["first_name"]
        updated = True
    if extracted.get("profession") and not user.profession:
        user.profession = extracted["profession"]
        updated = True
    if extracted.get("skills"):
        existing_skills = {s.skill_name for s in user.skills_list}
        for sk in extracted["skills"][:6]:
            sk_norm = sk.strip().lower()[:50]
            if sk_norm and sk_norm not in existing_skills:
                db.add(UserSkill(user_id=user.id, skill_name=sk_norm))
                existing_skills.add(sk_norm)
                updated = True

    user.onboarding_done = True
    db.commit()
    if updated:
        db.refresh(user)

    return {
        "score": score,
        "verdict": result.get("verdict", ""),
        "recommendation": result.get("recommendation", ""),
        "extracted": extracted,
    }


@app.post("/onboarding/skip")
def onboarding_skip(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Пропустить онбординг."""
    user.onboarding_done = True
    db.commit()
    return {"ok": True}


# ─── Достижения ───────────────────────────────────────────────────────────────

@app.post("/achievements/upload")
async def upload_media(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
):
    """Загрузить фото или аудио для достижения."""
    content_type = file.content_type or ""
    if content_type not in ALLOWED_MEDIA:
        raise HTTPException(400, "Формат не поддерживается. Разрешены: JPG, PNG, WEBP, MP3, OGG, WAV, M4A")

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, f"Файл слишком большой. Максимум {MAX_UPLOAD_BYTES // (1024*1024)} МБ")

    media_type, ext = ALLOWED_MEDIA[content_type]
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / filename
    dest.write_bytes(data)

    return {"url": f"/uploads/{filename}", "media_type": media_type}


class AchievementIn(BaseModel):
    content: str
    prompt_text: Optional[str] = None
    ai_tool: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None


@app.get("/achievements")
def get_achievements(
    offset: int = 0,
    limit: int = 20,
    pid: Optional[str] = None,    # фильтр по участнику
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Лента достижений участников (опционально фильтр по pid)."""
    q = db.query(Achievement, User).join(User, Achievement.user_id == User.id)
    if pid:
        target = db.query(User).filter(User.pid == pid.upper()).first()
        if target:
            q = q.filter(Achievement.user_id == target.id)
    rows = q.order_by(Achievement.created_at.desc()).offset(offset).limit(limit).all()

    # Реакции текущего пользователя
    my_reactions = {
        l.achievement_id: l.reaction
        for l in db.query(AchievementLike).filter(AchievementLike.user_id == user.id).all()
    }
    # Счётчики реакций по всем достижениям
    all_likes = db.query(AchievementLike).filter(
        AchievementLike.achievement_id.in_([ach.id for ach, _ in rows])
    ).all()
    reaction_counts = {}
    for l in all_likes:
        rc = reaction_counts.setdefault(l.achievement_id, {"fire": 0, "idea": 0})
        rc[l.reaction or "fire"] = rc.get(l.reaction or "fire", 0) + 1

    result = []
    for ach, u in rows:
        rc = reaction_counts.get(ach.id, {"fire": 0, "idea": 0})
        result.append({
            "id": ach.id,
            "content": ach.content,
            "prompt_text": ach.prompt_text,
            "ai_tool": ach.ai_tool,
            "media_url": ach.media_url,
            "media_type": ach.media_type,
            "likes": ach.likes,
            "liked_by_me": my_reactions.get(ach.id),
            "reactions": rc,
            "is_me": u.id == user.id,
            "pid": u.pid,
            "first_name": u.first_name or u.pid,
            "created_at": ach.created_at.strftime("%d.%m.%Y") if ach.created_at else "",
        })
    return result


@app.post("/achievements")
def create_achievement(
    body: AchievementIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Опубликовать достижение."""
    if not body.content or len(body.content.strip()) < 5:
        raise HTTPException(400, "Слишком короткое описание")
    ach = Achievement(
        user_id=user.id,
        content=body.content.strip(),
        prompt_text=body.prompt_text,
        ai_tool=body.ai_tool,
        media_url=body.media_url,
        media_type=body.media_type,
    )
    db.add(ach)
    db.commit()
    db.refresh(ach)
    return {"id": ach.id, "ok": True}


@app.post("/achievements/{ach_id}/like")
def like_achievement(
    ach_id: int,
    body: dict = {},
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Поставить/сменить/убрать реакцию (fire | idea)."""
    reaction = (body.get("reaction") or "fire") if body else "fire"
    if reaction not in ("fire", "idea"):
        reaction = "fire"

    ach = db.query(Achievement).filter(Achievement.id == ach_id).first()
    if not ach:
        raise HTTPException(404, "Не найдено")

    existing = db.query(AchievementLike).filter(
        AchievementLike.achievement_id == ach_id,
        AchievementLike.user_id == user.id,
    ).first()

    if existing:
        if existing.reaction == reaction:
            # Повторный тап — убираем реакцию
            db.delete(existing)
            ach.likes = max(0, ach.likes - 1)
            liked = None
        else:
            # Меняем тип реакции
            existing.reaction = reaction
            liked = reaction
    else:
        db.add(AchievementLike(achievement_id=ach_id, user_id=user.id, reaction=reaction))
        ach.likes += 1
        liked = reaction

    db.commit()

    # Пересчитываем реакции
    all_likes = db.query(AchievementLike).filter(AchievementLike.achievement_id == ach_id).all()
    rc = {"fire": 0, "idea": 0}
    for l in all_likes:
        rc[l.reaction or "fire"] = rc.get(l.reaction or "fire", 0) + 1

    return {"likes": ach.likes, "liked": liked, "reactions": rc}


@app.delete("/achievements/{ach_id}")
def delete_achievement(
    ach_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Удалить своё достижение."""
    ach = db.query(Achievement).filter(
        Achievement.id == ach_id,
        Achievement.user_id == user.id,
    ).first()
    if not ach:
        raise HTTPException(404, "Не найдено")
    db.delete(ach)
    db.commit()
    return {"ok": True}


# ─── Чат (личные сообщения между друзьями) ────────────────────────────────────

def _are_friends(db: Session, user_a_id: int, user_b_id: int) -> bool:
    """Проверяет, что два пользователя — принятые контакты."""
    return db.query(ContactRequest).filter(
        ContactRequest.status == "accepted",
        (
            (ContactRequest.from_user_id == user_a_id) & (ContactRequest.to_user_id == user_b_id)
        ) | (
            (ContactRequest.from_user_id == user_b_id) & (ContactRequest.to_user_id == user_a_id)
        )
    ).first() is not None


class SendMessageIn(BaseModel):
    content: str


@app.get("/chats/unread")
def chats_unread_count(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Количество непрочитанных сообщений."""
    count = db.query(Message).filter(
        Message.receiver_id == user.id,
        Message.read_at.is_(None),
    ).count()
    return {"unread": count}


@app.get("/chats")
def chats_list(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Список всех друзей: последнее сообщение + непрочитанные."""
    # Все принятые контакты
    contacts = db.query(ContactRequest).filter(
        ContactRequest.status == "accepted",
        (ContactRequest.from_user_id == user.id) | (ContactRequest.to_user_id == user.id),
    ).all()

    friend_ids = []
    for c in contacts:
        fid = c.to_user_id if c.from_user_id == user.id else c.from_user_id
        friend_ids.append(fid)

    # Последнее сообщение с каждым другом
    all_msgs = db.query(Message).filter(
        (Message.sender_id == user.id) | (Message.receiver_id == user.id)
    ).order_by(Message.created_at.desc()).all()

    last_msgs = {}
    for m in all_msgs:
        pid = m.receiver_id if m.sender_id == user.id else m.sender_id
        if pid not in last_msgs:
            last_msgs[pid] = m

    result = []
    for fid in friend_ids:
        partner = db.query(User).filter(User.id == fid).first()
        if not partner:
            continue
        unread = db.query(Message).filter(
            Message.sender_id == fid,
            Message.receiver_id == user.id,
            Message.read_at.is_(None),
        ).count()
        last = last_msgs.get(fid)
        skills = [s.skill_name for s in partner.skills_list[:2]]
        result.append({
            "pid": partner.pid,
            "first_name": partner.first_name or partner.pid,
            "last_name": partner.last_name or "",
            "skills": skills,
            "last_message": last.content if last else None,
            "last_message_mine": (last.sender_id == user.id) if last else None,
            "last_time": last.created_at.strftime("%H:%M") if last else None,
            "unread": unread,
            "is_online": bool(partner.last_seen and
                (datetime.utcnow() - partner.last_seen).total_seconds() < 180),
        })

    # Сортируем: сначала с сообщениями (по времени), потом без
    result.sort(key=lambda x: (x["last_time"] is None, x["last_time"] or ""), reverse=False)
    result = sorted(result, key=lambda x: (x["last_time"] is None, x.get("last_time", "") or ""), reverse=True)
    return result


@app.get("/chats/{pid}")
def chats_get(
    pid: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """История переписки с участником + пометка как прочитанное."""
    partner = db.query(User).filter(User.pid == pid).first()
    if not partner:
        raise HTTPException(404, "Участник не найден")
    if not _are_friends(db, user.id, partner.id):
        raise HTTPException(403, "Можно писать только друзьям")

    msgs = db.query(Message).filter(
        ((Message.sender_id == user.id) & (Message.receiver_id == partner.id)) |
        ((Message.sender_id == partner.id) & (Message.receiver_id == user.id))
    ).order_by(Message.created_at.asc()).all()

    # Помечаем входящие как прочитанные
    for m in msgs:
        if m.receiver_id == user.id and m.read_at is None:
            m.read_at = datetime.utcnow()
    db.commit()

    return {
        "partner": {
            "pid": partner.pid,
            "first_name": partner.first_name or partner.pid,
            "last_name": partner.last_name or "",
            "telegram_username": partner.telegram_username or "",
        },
        "messages": [
            {
                "id": m.id,
                "content": m.content,
                "mine": m.sender_id == user.id,
                "time": m.created_at.strftime("%H:%M"),
                "date": m.created_at.strftime("%d.%m"),
                "read": m.read_at is not None,
            }
            for m in msgs
        ],
    }


@app.post("/chats/{pid}")
def chats_send(
    pid: str,
    body: SendMessageIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Отправить сообщение другу."""
    if not body.content or not body.content.strip():
        raise HTTPException(400, "Сообщение пустое")
    if len(body.content) > 2000:
        raise HTTPException(400, "Сообщение слишком длинное")

    partner = db.query(User).filter(User.pid == pid).first()
    if not partner:
        raise HTTPException(404, "Участник не найден")
    if not _are_friends(db, user.id, partner.id):
        raise HTTPException(403, "Можно писать только друзьям")

    msg = Message(
        sender_id=user.id,
        receiver_id=partner.id,
        content=body.content.strip(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {
        "id": msg.id,
        "content": msg.content,
        "mine": True,
        "time": msg.created_at.strftime("%H:%M"),
        "date": msg.created_at.strftime("%d.%m"),
        "read": False,
    }



# ══════════════════════════════════════════════════════════════
#  СЕЗОНЫ / КОМАНДЫ / ВЫЗОВЫ
# ══════════════════════════════════════════════════════════════

import random
import string

def _make_invite_code(length=6) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def _get_or_create_trust(db: Session, user_id: int) -> UserTrust:
    trust = db.query(UserTrust).filter(UserTrust.user_id == user_id).first()
    if not trust:
        trust = UserTrust(user_id=user_id, score=0.7)
        db.add(trust)
        db.commit()
        db.refresh(trust)
    return trust

def _calc_contribution_score(user: User, db: Session) -> float:
    answers = db.query(QuestionAnswer).filter(QuestionAnswer.expert_user_id == user.id).count()
    validations = db.query(ReportValidation).filter(
        ReportValidation.validator_id == user.id,
        ReportValidation.decision.isnot(None)
    ).count()
    approved = db.query(ChallengeSubmission).filter(
        ChallengeSubmission.user_id == user.id,
        ChallengeSubmission.status == "approved"
    ).count()
    raw = answers * 2 + validations * 1 + approved * 5
    return min(raw / 50.0, 1.0)

def _calc_team_scores(team: Team, db: Session) -> dict:
    members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
    capital = 0.0
    for m in members:
        u = db.query(User).filter(User.id == m.user_id).first()
        if not u:
            continue
        fire = calc_fire_score(u, db)["total"] if u else 0
        trust = _get_or_create_trust(db, u.id).score
        contrib = _calc_contribution_score(u, db)
        capital += fire * trust * contrib
    n = len(members) or 1
    efficiency = capital / n
    rating = 0.7 * capital + 0.3 * efficiency
    return {"capital": round(capital, 2), "efficiency": round(efficiency, 2),
            "rating": round(rating, 2), "members_count": n}


# ── Схемы ─────────────────────────────────────────────────────

class SeasonCreate(BaseModel):
    name: str
    start_date: datetime
    end_date: datetime

class TeamCreate(BaseModel):
    name: str

class TeamJoin(BaseModel):
    invite_code: str

class ChallengeCreate(BaseModel):
    title: str
    description: str
    category: str
    difficulty: str = "bronze"
    jury_name: Optional[str] = None
    jury_telegram_id: Optional[str] = None
    requirements: Optional[str] = None
    reward_fire_score: int = 10
    reward_trust_bonus: float = 0.05
    reward_achievement_title: Optional[str] = None
    season_id: Optional[int] = None
    is_team_challenge: bool = False

class SubmitChallenge(BaseModel):
    evidence_url: Optional[str] = None
    evidence_text: Optional[str] = None

class JuryReview(BaseModel):
    decision: str
    comment: Optional[str] = None

class ValidateReport(BaseModel):
    decision: str


# ── Сезоны ────────────────────────────────────────────────────

@app.get("/seasons/current")
def current_season(db: Session = Depends(get_db)):
    season = db.query(Season).filter(Season.status == "active").order_by(Season.start_date.desc()).first()
    if not season:
        raise HTTPException(404, "Активный сезон не найден")
    return {
        "id": season.id, "name": season.name,
        "start_date": season.start_date.isoformat(),
        "end_date": season.end_date.isoformat(),
        "days_left": max(0, (season.end_date - datetime.utcnow()).days),
    }

@app.get("/seasons")
def list_seasons(db: Session = Depends(get_db)):
    seasons = db.query(Season).order_by(Season.start_date.desc()).all()
    return [{"id": s.id, "name": s.name, "status": s.status,
             "start_date": s.start_date.isoformat(), "end_date": s.end_date.isoformat()}
            for s in seasons]

@app.post("/seasons")
def create_season(body: SeasonCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.pid != "P-001":
        raise HTTPException(403, "Только для администратора")
    season = Season(name=body.name, start_date=body.start_date, end_date=body.end_date)
    db.add(season)
    db.commit()
    db.refresh(season)
    return {"id": season.id, "name": season.name}


# ── Команды ───────────────────────────────────────────────────

@app.get("/teams")
def list_teams(db: Session = Depends(get_db)):
    season = db.query(Season).filter(Season.status == "active").first()
    if not season:
        return []
    teams = db.query(Team).filter(Team.season_id == season.id).all()
    result = []
    for t in teams:
        scores = _calc_team_scores(t, db)
        result.append({
            "id": t.id, "name": t.name,
            "captain_id": t.captain_id,
            "members_count": scores["members_count"],
            "team_capital": scores["capital"],
            "team_rating": scores["rating"],
        })
    result.sort(key=lambda x: -x["team_rating"])
    for i, r in enumerate(result):
        r["rank"] = i + 1
    return result

@app.post("/teams")
def create_team(body: TeamCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    season = db.query(Season).filter(Season.status == "active").first()
    if not season:
        raise HTTPException(400, "Нет активного сезона")
    existing = db.query(TeamMember).join(Team).filter(
        Team.season_id == season.id, TeamMember.user_id == user.id
    ).first()
    if existing:
        raise HTTPException(400, "Вы уже состоите в команде этого сезона")
    invite = _make_invite_code()
    team = Team(season_id=season.id, name=body.name.strip(),
                captain_id=user.id, invite_code=invite)
    db.add(team)
    db.flush()
    db.add(TeamMember(team_id=team.id, user_id=user.id, role="captain"))
    db.commit()
    db.refresh(team)
    return {"id": team.id, "name": team.name, "invite_code": team.invite_code}

@app.post("/teams/join")
def join_team(body: TeamJoin, user: User = Depends(current_user), db: Session = Depends(get_db)):
    season = db.query(Season).filter(Season.status == "active").first()
    if not season:
        raise HTTPException(400, "Нет активного сезона")
    existing = db.query(TeamMember).join(Team).filter(
        Team.season_id == season.id, TeamMember.user_id == user.id
    ).first()
    if existing:
        raise HTTPException(400, "Вы уже в команде")
    team = db.query(Team).filter(
        Team.season_id == season.id,
        Team.invite_code == body.invite_code.upper()
    ).first()
    if not team:
        raise HTTPException(404, "Команда не найдена — проверьте код")
    count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
    if count >= 7:
        raise HTTPException(400, "Команда заполнена (максимум 7 участников)")
    db.add(TeamMember(team_id=team.id, user_id=user.id, role="member"))
    db.commit()
    return {"ok": True, "team_name": team.name}

@app.get("/teams/my")
def my_team(user: User = Depends(current_user), db: Session = Depends(get_db)):
    season = db.query(Season).filter(Season.status == "active").first()
    if not season:
        return {"team": None}
    membership = db.query(TeamMember).join(Team).filter(
        Team.season_id == season.id, TeamMember.user_id == user.id
    ).first()
    if not membership:
        return {"team": None}
    team = db.query(Team).filter(Team.id == membership.team_id).first()
    members_raw = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
    members = []
    for m in members_raw:
        u = db.query(User).filter(User.id == m.user_id).first()
        if not u:
            continue
        fire = calc_fire_score(u, db)["total"]
        trust = _get_or_create_trust(db, u.id).score
        contrib = _calc_contribution_score(u, db)
        members.append({
            "pid": u.pid,
            "name": u.first_name or u.telegram_username or u.pid,
            "role": m.role,
            "fire_score": round(fire),
            "trust_score": round(trust, 2),
            "effective_score": round(fire * trust, 1),
            "contribution": round(contrib, 2),
        })
    scores = _calc_team_scores(team, db)
    return {
        "team": {
            "id": team.id, "name": team.name,
            "invite_code": team.invite_code if membership.role == "captain" else None,
            "my_role": membership.role,
        },
        "members": members,
        "scores": scores,
    }


# ── Вызовы (Challenges) ────────────────────────────────────────

DIFFICULTY_COLORS = {
    "bronze": "#CD7F32", "silver": "#C0C0C0",
    "gold": "#FFD700",   "legendary": "#9B59B6",
}

@app.get("/challenges")
def list_challenges(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    season = db.query(Season).filter(Season.status == "active").first()
    q = db.query(Challenge).filter(Challenge.is_active == True)
    if season:
        q = q.filter((Challenge.season_id == season.id) | (Challenge.season_id == None))
    if category:
        q = q.filter(Challenge.category == category)
    challenges = q.all()
    my_subs = {
        s.challenge_id: s for s in
        db.query(ChallengeSubmission).filter(ChallengeSubmission.user_id == user.id).all()
    }
    return [
        {
            "id": c.id, "title": c.title, "description": c.description,
            "category": c.category, "difficulty": c.difficulty,
            "difficulty_color": DIFFICULTY_COLORS.get(c.difficulty, "#888"),
            "jury_name": c.jury_name, "requirements": c.requirements,
            "reward_fire_score": c.reward_fire_score,
            "reward_achievement": c.reward_achievement_title,
            "is_team": c.is_team_challenge,
            "my_status": my_subs[c.id].status if c.id in my_subs else None,
        }
        for c in challenges
    ]

@app.post("/challenges")
def create_challenge(body: ChallengeCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.pid != "P-001":
        raise HTTPException(403, "Только для администратора")
    ch = Challenge(**body.model_dump())
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return {"id": ch.id, "title": ch.title}

@app.post("/challenges/{challenge_id}/submit")
async def submit_challenge(
    challenge_id: int,
    body: SubmitChallenge,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id, Challenge.is_active == True).first()
    if not ch:
        raise HTTPException(404, "Вызов не найден")
    existing = db.query(ChallengeSubmission).filter(
        ChallengeSubmission.challenge_id == challenge_id,
        ChallengeSubmission.user_id == user.id,
        ChallengeSubmission.status.in_(["pending", "approved"]),
    ).first()
    if existing:
        raise HTTPException(400, "Заявка уже подана")
    season = db.query(Season).filter(Season.status == "active").first()
    team_id = None
    if season:
        mem = db.query(TeamMember).join(Team).filter(
            Team.season_id == season.id, TeamMember.user_id == user.id
        ).first()
        if mem:
            team_id = mem.team_id
    sub = ChallengeSubmission(
        challenge_id=challenge_id, user_id=user.id, team_id=team_id,
        evidence_url=body.evidence_url, evidence_text=body.evidence_text, status="pending",
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    # Уведомляем жюри
    if ch.jury_telegram_id:
        name = user.first_name or user.telegram_username or user.pid
        txt = (f"📋 <b>Заявка на вызов</b>\n<b>{name}</b> ({user.pid})\n"
               f"<b>Вызов:</b> {ch.title}\n")
        if body.evidence_url:
            txt += f"🔗 {body.evidence_url}\n"
        if body.evidence_text:
            txt += f"📝 {body.evidence_text}\n"
        txt += f"\n/review_{sub.id}_approved — ✅\n/review_{sub.id}_rejected — ❌"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": ch.jury_telegram_id, "text": txt, "parse_mode": "HTML"},
                )
        except Exception as e:
            print(f"[CHALLENGE] jury notify: {e}", flush=True)
    return {"submission_id": sub.id, "status": "pending"}

@app.patch("/submissions/{sub_id}/review")
async def review_submission(
    sub_id: int,
    body: JuryReview,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    sub = db.query(ChallengeSubmission).filter(ChallengeSubmission.id == sub_id).first()
    if not sub:
        raise HTTPException(404, "Заявка не найдена")
    ch = db.query(Challenge).filter(Challenge.id == sub.challenge_id).first()
    is_admin = user.pid == "P-001"
    is_jury = ch and ch.jury_telegram_id and ch.jury_telegram_id == user.telegram_id
    if not (is_admin or is_jury):
        raise HTTPException(403, "Нет доступа")
    if body.decision not in ("approved", "rejected", "revision"):
        raise HTTPException(400, "decision: approved / rejected / revision")
    sub.status = body.decision
    sub.jury_comment = body.comment
    sub.reviewed_at = datetime.utcnow()
    if body.decision == "approved" and ch:
        if ch.reward_achievement_title:
            db.add(Achievement(
                user_id=sub.user_id,
                content=f"🏆 {ch.reward_achievement_title} — {ch.title}",
                ai_tool="challenge",
            ))
        if ch.reward_trust_bonus > 0:
            trust = _get_or_create_trust(db, sub.user_id)
            trust.score = min(1.0, trust.score + ch.reward_trust_bonus)
            trust.updated_at = datetime.utcnow()
    db.commit()
    # Уведомляем участника
    applicant = db.query(User).filter(User.id == sub.user_id).first()
    if applicant and applicant.telegram_id:
        msgs = {
            "approved": f"✅ Вызов <b>{ch.title}</b> одобрен! +{ch.reward_fire_score} к FIRE Score" +
                        (f"\n🏆 {ch.reward_achievement_title}" if ch and ch.reward_achievement_title else ""),
            "rejected": f"❌ Вызов <b>{ch.title}</b> отклонён.\nКомментарий: {body.comment or '—'}",
            "revision": f"🔄 Нужны доработки по <b>{ch.title}</b>.\n{body.comment or ''}",
        }
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": applicant.telegram_id,
                          "text": msgs.get(body.decision, ""), "parse_mode": "HTML"},
                )
        except Exception:
            pass
    return {"ok": True, "status": sub.status}

@app.get("/submissions/my")
def my_submissions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    subs = db.query(ChallengeSubmission).filter(
        ChallengeSubmission.user_id == user.id
    ).order_by(ChallengeSubmission.submitted_at.desc()).all()
    result = []
    for s in subs:
        ch = db.query(Challenge).filter(Challenge.id == s.challenge_id).first()
        result.append({
            "id": s.id,
            "challenge_title": ch.title if ch else "?",
            "category": ch.category if ch else "?",
            "difficulty": ch.difficulty if ch else "?",
            "status": s.status,
            "jury_comment": s.jury_comment,
            "submitted_at": s.submitted_at.isoformat(),
        })
    return result


# ── Trust Score ────────────────────────────────────────────────

@app.get("/me/trust")
def my_trust(user: User = Depends(current_user), db: Session = Depends(get_db)):
    trust = _get_or_create_trust(db, user.id)
    fire = calc_fire_score(user, db)["total"]
    return {
        "score": round(trust.score, 2),
        "validated_reports": trust.validated_reports,
        "rejected_reports": trust.rejected_reports,
        "validations_done": trust.validations_done,
        "fire_score": round(fire),
        "effective_score": round(fire * trust.score, 1),
    }


# ── Peer Validation отчётов ────────────────────────────────────

@app.get("/reports/pending-validation")
def pending_validations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    already = db.query(ReportValidation.report_id).filter(
        ReportValidation.validator_id == user.id
    ).subquery()
    reports = db.query(Report).filter(
        Report.user_id != user.id,
        ~Report.id.in_(already),
    ).order_by(Report.created_at.desc()).limit(5).all()
    result = []
    for r in reports:
        author = db.query(User).filter(User.id == r.user_id).first()
        result.append({
            "report_id": r.id, "month": r.month,
            "author_pid": author.pid if author else "?",
            "savings_pct": r.savings_pct, "invest_pct": r.invest_pct,
            "budget_yes": r.budget_yes, "income_gt_expense": r.income_gt_expense,
        })
    return result

@app.post("/reports/{report_id}/validate")
def validate_report_peer(
    report_id: int,
    body: ValidateReport,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if body.decision not in ("approve", "reject"):
        raise HTTPException(400, "decision: approve / reject")
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(404, "Отчёт не найден")
    if report.user_id == user.id:
        raise HTTPException(400, "Нельзя валидировать свой отчёт")
    existing = db.query(ReportValidation).filter(
        ReportValidation.report_id == report_id,
        ReportValidation.validator_id == user.id,
    ).first()
    if existing:
        raise HTTPException(400, "Вы уже проголосовали")
    rv = ReportValidation(
        report_id=report_id, validator_id=user.id,
        decision=body.decision, decided_at=datetime.utcnow(),
    )
    db.add(rv)
    # +0.01 trust валидатору за участие
    v_trust = _get_or_create_trust(db, user.id)
    v_trust.validations_done += 1
    v_trust.score = min(1.0, v_trust.score + 0.01)
    v_trust.updated_at = datetime.utcnow()
    # Пересчёт trust автора при 2+ голосах
    all_votes = db.query(ReportValidation).filter(
        ReportValidation.report_id == report_id,
        ReportValidation.decision.isnot(None),
    ).all()
    votes_after = len(all_votes) + 1
    rejects = sum(1 for v in all_votes if v.decision == "reject") + (1 if body.decision == "reject" else 0)
    if votes_after >= 2:
        a_trust = _get_or_create_trust(db, report.user_id)
        if rejects / votes_after > 0.4:
            a_trust.rejected_reports += 1
            a_trust.score = max(0.1, a_trust.score - 0.1)
        else:
            a_trust.validated_reports += 1
            a_trust.score = min(1.0, a_trust.score + 0.05)
        a_trust.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "your_decision": body.decision, "total_votes": votes_after}