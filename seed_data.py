"""
FIRE35 — посев данных: 51 участник + отчёты + пароль по умолчанию
"""
import os
from passlib.context import CryptContext
from database import User, Report, init_db, SessionLocal

DEFAULT_PASSWORD = os.getenv("DEFAULT_PASSWORD", "fire2026")

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

PROFESSIONS = [
    "Инженер", "Инженер", "Инженер", "Инженер", "Инженер",
    "Инженер", "Инженер", "Инженер",
    "Предприниматель", "Предприниматель", "Предприниматель",
    "Предприниматель", "Предприниматель", "Предприниматель", "Предприниматель",
    "Врач", "Врач", "Врач",
    "Репетитор", "Репетитор", "Репетитор",
    "IT-специалист", "IT-специалист", "IT-специалист", "IT-специалист", "IT-специалист",
    "Финансист", "Финансист", "Финансист",
    "Менеджер", "Менеджер", "Менеджер",
    "Учитель", "Учитель",
    "Юрист", "Юрист",
    "Маркетолог", "Маркетолог",
    "Дизайнер", "Дизайнер",
    "Бухгалтер", "Бухгалтер",
    "Строитель",
    "Логист",
    "Переводчик",
    "Архитектор",
    "Риэлтор",
    "Психолог",
    "Фотограф",
    "Копирайтер",
    "Консультант",
]

REPORTS_FEB = [
    (85,70,True,True),(83,65,True,True),(77,60,True,True),(75,55,True,True),(72,50,True,True),
    (70,48,True,True),(68,45,True,True),(65,40,True,True),(63,38,True,True),(60,35,True,True),
    (58,30,True,True),(56,28,True,True),(55,25,True,True),(54,22,True,True),(52,20,True,True),
    (50,18,True,True),(48,15,True,True),(47,14,True,True),(46,12,True,True),(45,10,True,True),
    (44,10,True,True),(43,8,True,True),(42,8,True,True),(40,5,True,True),(39,5,True,True),
    (38,4,True,True),(37,4,True,True),(36,3,True,True),(35,3,True,True),(34,2,True,True),
    (33,2,True,False),(32,1,True,False),(30,0,False,True),(28,0,False,True),(27,0,False,True),
    (25,0,False,True),(22,0,False,False),(20,0,False,False),(18,0,False,False),(15,0,False,False),
    (12,0,False,False),(10,0,False,False),(8,0,False,False),(7,0,False,False),(6,0,False,False),
    (5,0,False,False),(4,0,False,False),(3,0,False,False),(2,0,False,False),(1,0,False,False),
    (0,0,False,False),
]

REPORTS_JAN = [
    (78,60,True,True),(80,62,True,True),(70,55,True,True),(68,48,True,True),(65,45,True,True),
    (62,40,True,True),(60,38,True,True),(58,35,True,True),(55,30,True,True),(52,28,True,True),
    (50,25,True,True),(48,22,True,True),(47,20,True,True),(46,18,True,True),(45,15,True,True),
    (43,12,True,True),(42,10,True,True),(40,8,True,True),(38,7,True,True),(36,6,True,True),
    (37,5,True,True),(35,4,True,True),(33,3,True,True),(31,2,True,True),(30,1,True,True),
    (28,0,False,True),(27,0,False,True),(26,0,False,True),(25,0,False,True),(24,0,False,True),
    (23,0,False,False),(20,0,False,False),(25,0,False,True),(22,0,False,True),(20,0,False,True),
    (18,0,False,True),(15,0,False,False),(12,0,False,False),(10,0,False,False),(8,0,False,False),
    (5,0,False,False),(3,0,False,False),(2,0,False,False),(1,0,False,False),(0,0,False,False),
    (0,0,False,False),(0,0,False,False),(0,0,False,False),(0,0,False,False),(0,0,False,False),
    (0,0,False,False),
]


def seed():
    init_db()
    db = SessionLocal()

    existing_count = db.query(User).count()
    if existing_count == 0:
        print(f"[seed] Создаём 51 участника с паролем '{DEFAULT_PASSWORD}'...")
        hashed = pwd_ctx.hash(DEFAULT_PASSWORD)
        users = []
        for i, profession in enumerate(PROFESSIONS, start=1):
            user = User(pid=f"P-{i:03d}", profession=profession, password_hash=hashed)
            db.add(user)
            users.append(user)
        db.commit()
        for u in users:
            db.refresh(u)

        print("[seed] Добавляем отчёты за 2026-01 и 2026-02...")
        for i, user in enumerate(users):
            if i < len(REPORTS_JAN):
                s, inv, bud, inc = REPORTS_JAN[i]
                db.add(Report(user_id=user.id, month="2026-01",
                              budget_yes=bud, income_gt_expense=inc,
                              savings_pct=float(s), invest_pct=float(inv)))
            if i < len(REPORTS_FEB):
                s, inv, bud, inc = REPORTS_FEB[i]
                db.add(Report(user_id=user.id, month="2026-02",
                              budget_yes=bud, income_gt_expense=inc,
                              savings_pct=float(s), invest_pct=float(inv)))
        db.commit()
        print(f"[seed] Готово! 51 участник, пароль по умолчанию: '{DEFAULT_PASSWORD}'")
    else:
        # Только ставим пароль тем у кого его нет
        hashed = pwd_ctx.hash(DEFAULT_PASSWORD)
        no_pwd = db.query(User).filter(User.password_hash.is_(None)).all()
        if no_pwd:
            print(f"[seed] Ставим пароль '{DEFAULT_PASSWORD}' для {len(no_pwd)} участников без пароля...")
            for u in no_pwd:
                u.password_hash = hashed
            db.commit()
            print(f"[seed] Обновлено: {len(no_pwd)} участников")
        else:
            print(f"[seed] {existing_count} участников уже есть, пароли заданы. Пропускаем.")

    db.close()


if __name__ == "__main__":
    seed()
