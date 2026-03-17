"""
FIRE35 — Telegram группа-парсер.

Шаг 0: авторизоваться один раз
  python tg_auth.py --request
  python tg_auth.py --code XXXXX

Использование:
  # Показать участников чата без записи в БД
  python tg_parser.py --chat @fire35_group

  # Записать telegram_id/username в БД (матчинг P-001..P-051 по порядку или вручную)
  python tg_parser.py --chat @fire35_group --save

  # Привязать конкретный TG-username к P-XXX
  python tg_parser.py --link @username P-007

  # Показать текущие привязки из БД
  python tg_parser.py --status
"""
import asyncio
import argparse
import sys
import os

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import User as TgUser

load_dotenv()

API_ID   = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION  = "fire35_session"


# ─── helpers ──────────────────────────────────────────────

def get_db_session():
    """Импортируем DB только если нужен --save / --link / --status."""
    sys.path.insert(0, os.path.dirname(__file__))
    from database import SessionLocal, User
    return SessionLocal(), User


async def fetch_members(chat: str):
    """Собирает уникальных участников через историю сообщений (без прав админа)."""
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()

    seen = {}
    try:
        try:
            chat_id = int(chat)
        except ValueError:
            chat_id = chat
        entity = await client.get_entity(chat_id)
        print(f"[ok] Подключился к: {getattr(entity, 'title', chat)}")
        print("[..] Читаю историю сообщений (может занять минуту)...")
        async for msg in client.iter_messages(entity, limit=5000):
            sender = msg.sender
            if not sender or not isinstance(sender, TgUser):
                continue
            if sender.id in seen or sender.bot:
                continue
            seen[sender.id] = {
                "id":         sender.id,
                "username":   sender.username,
                "first_name": sender.first_name or "",
                "last_name":  sender.last_name or "",
                "bot":        sender.bot,
            }
    finally:
        await client.disconnect()

    return list(seen.values())


async def cmd_list(chat: str):
    """Напечатать участников."""
    members = await fetch_members(chat)
    humans = [m for m in members if not m["bot"]]
    print(f"\n[ok] Участников (без ботов): {len(humans)}\n")
    print(f"{'#':<4} {'TG ID':<14} {'Username':<20} {'Имя'}")
    print("-" * 60)
    for i, m in enumerate(humans, 1):
        uname = f"@{m['username']}" if m["username"] else "—"
        name  = f"{m['first_name']} {m['last_name']}".strip()
        print(f"{i:<4} {m['id']:<14} {uname:<20} {name}")


async def cmd_save(chat: str):
    """
    Получить участников и предложить привязку к P-XXX.
    Автоматически обновляет telegram_id + telegram_username если
    пользователь ещё не привязан.
    """
    members = await fetch_members(chat)
    humans  = [m for m in members if not m["bot"] and m["username"]]

    db, User = get_db_session()
    updated = 0

    for m in humans:
        uname = m["username"].lower()
        # Ищем уже привязанного
        existing = db.query(User).filter(
            User.telegram_username == uname
        ).first()
        if existing:
            # Обновляем telegram_id если не был
            if not existing.telegram_id:
                existing.telegram_id = str(m["id"])
                db.commit()
                print(f"[upd] {existing.pid} — telegram_id обновлён для @{uname}")
            continue

        # Ищем по telegram_id
        by_id = db.query(User).filter(
            User.telegram_id == str(m["id"])
        ).first()
        if by_id:
            if not by_id.telegram_username:
                by_id.telegram_username = uname
                db.commit()
                print(f"[upd] {by_id.pid} — username обновлён: @{uname}")
            continue

        print(f"[new] @{uname} ({m['first_name']} {m['last_name']}) — не привязан к P-XXX")
        print(f"      Привяжи: python tg_parser.py --link @{uname} P-XXX")

    db.close()
    print(f"\n[ok] Готово. Обновлено: {updated} записей.")


def cmd_link(username: str, pid: str):
    """Привязать @username к конкретному P-XXX."""
    db, User = get_db_session()

    username = username.lstrip("@").lower()
    pid      = pid.strip().upper()

    user = db.query(User).filter(User.pid == pid).first()
    if not user:
        print(f"[err] {pid} не найден в БД")
        db.close()
        return

    user.telegram_username = username
    db.commit()
    print(f"[ok] {pid} → @{username}")
    db.close()


def cmd_status():
    """Показать привязки TG ↔ P-XXX."""
    db, User = get_db_session()
    users = db.query(User).order_by(User.pid).all()

    linked   = [u for u in users if u.telegram_username]
    unlinked = [u for u in users if not u.telegram_username]

    print(f"\nПривязано: {len(linked)} / {len(users)}\n")
    print(f"{'PID':<8} {'TG Username':<22} {'Имя'}")
    print("-" * 50)
    for u in linked:
        name = f"{u.first_name or ''} {u.last_name or ''}".strip() or "—"
        print(f"{u.pid:<8} @{u.telegram_username:<21} {name}")

    if unlinked:
        print(f"\nНе привязаны ({len(unlinked)}):")
        print(", ".join(u.pid for u in unlinked))

    db.close()


# ─── main ─────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="FIRE35 Telegram Parser")
    p.add_argument("--chat",   help="Username или ссылка на чат (напр. @fire35_group)")
    p.add_argument("--save",   action="store_true", help="Сохранить в БД")
    p.add_argument("--link",   nargs=2, metavar=("@USERNAME", "P-XXX"),
                   help="Привязать username к участнику")
    p.add_argument("--status", action="store_true", help="Показать привязки из БД")
    args = p.parse_args()

    if args.status:
        cmd_status()
    elif args.link:
        cmd_link(args.link[0], args.link[1])
    elif args.chat and args.save:
        asyncio.run(cmd_save(args.chat))
    elif args.chat:
        asyncio.run(cmd_list(args.chat))
    else:
        p.print_help()


if __name__ == "__main__":
    main()
