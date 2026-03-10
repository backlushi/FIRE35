"""
FIRE35 — FastAPI backend
Port 8001, контейнер fire35_backend
"""
import os
import httpx
from datetime import datetime, timedelta
from typing import Optional, List

import jwt
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from database import User, Report, ContactRequest, FcmToken, get_db, init_db

# ─── config ───────────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "fire35_jwt_secret_change_me")
JWT_EXPIRE_DAYS = 30
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "fire35_admin_secret")
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")   # Firebase Console → Project Settings → Cloud Messaging

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="FIRE35 API", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)


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


# ─── schemas ──────────────────────────────────────────────
class LoginRequest(BaseModel):
    pid: str
    password: str


class ReportCreate(BaseModel):
    month: Optional[str] = None
    budget_yes: bool
    income_gt_expense: bool
    savings_pct: float
    invest_pct: float

    @field_validator("invest_pct")
    @classmethod
    def invest_lte_savings(cls, v, info):
        savings = info.data.get("savings_pct", 0)
        if v > savings:
            raise ValueError("invest_pct не может превышать savings_pct")
        return v

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

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    telegram_username: Optional[str] = None
    first_name: Optional[str] = None
    skills: Optional[str] = None


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


# ─── routes ───────────────────────────────────────────────

@app.get("/")
def root():
    return {"project": "FIRE35", "status": "ok", "version": "2.1"}


# ── Auth ──────────────────────────────────────────────────

@app.post("/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    pid = body.pid.strip().upper()
    user = db.query(User).filter(User.pid == pid).first()
    if not user:
        raise HTTPException(status_code=401, detail="Участник не найден")
    if not user.password_hash:
        raise HTTPException(status_code=401,
                            detail="Пароль не задан. Обратитесь к администратору.")
    if not pwd_ctx.verify(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный пароль")
    token = make_token(user.id)
    return {"access_token": token, "token_type": "bearer", "pid": user.pid}


@app.post("/auth/login-tg")
def login_tg(body: TgLoginRequest, db: Session = Depends(get_db)):
    """
    Вход по Telegram username — без пароля.
    Работает только если admin заранее привязал @username к P-XXX через tg_parser.py.
    """
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

@app.get("/me", response_model=UserProfile)
def get_me(user: User = Depends(current_user)):
    return user


@app.patch("/me")
def update_me(
    body: UpdateProfileRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Обновить telegram_username, first_name, skills."""
    if body.telegram_username is not None:
        tg = body.telegram_username.strip().lstrip('@')
        user.telegram_username = tg or None
    if body.first_name is not None:
        user.first_name = body.first_name.strip() or None
    if body.skills is not None:
        user.skills = body.skills.strip() or None
    db.commit()
    return {"status": "ok"}


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
    """Справочник профессий. month — для показа savings_pct участника."""
    query = db.query(User).filter(User.profession.isnot(None))
    if search:
        query = query.filter(User.profession.ilike(f"%{search}%"))
    users = query.all()

    # Собираем рейтинг за месяц если запрошен
    ratings: dict[int, float] = {}
    if month:
        for r in db.query(Report).filter(Report.month == month).all():
            ratings[r.user_id] = r.savings_pct

    prof_map: dict[str, list] = {}
    for u in users:
        p = (u.profession or "Не указано").strip()
        prof_map.setdefault(p, []).append({
            "pid": u.pid,
            "profession": p,
            "skills": u.skills or "—",
            "telegram_username": u.telegram_username,
            "savings_pct": ratings.get(u.id),
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
    """Сохранить/обновить FCM токен устройства."""
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
    """Отправить запрос на контакт участнику."""
    to_pid = to_pid.strip().upper()
    target = db.query(User).filter(User.pid == to_pid).first()
    if not target:
        raise HTTPException(status_code=404, detail="Участник не найден")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Нельзя отправить запрос себе")

    # Проверяем нет ли уже активного запроса
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

    db.add(ContactRequest(from_user_id=user.id, to_user_id=target.id))
    db.commit()

    # Push-уведомление получателю
    fcm_row = db.query(FcmToken).filter(FcmToken.user_id == target.id).first()
    if fcm_row:
        await send_push(
            token=fcm_row.token,
            title="Запрос на знакомство",
            body=f"Участник {user.pid} хочет познакомиться. Открой FIRE35 → Участники",
            data={"type": "contact_request", "from_pid": user.pid},
        )

    return {"status": "sent"}


@app.get("/contact-requests/pending", response_model=List[ContactRequestOut])
def get_pending_requests(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Входящие запросы на контакт (ожидающие ответа)."""
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
def accept_request(
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