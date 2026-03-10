"""
Двухшаговая Telethon авторизация.
Шаг 1: python tg_auth.py --request   (отправляет код в TG)
Шаг 2: python tg_auth.py --code 12345 (вводишь код из TG)
"""
import asyncio, argparse, os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

load_dotenv()

API_ID    = int(os.getenv("API_ID"))
API_HASH  = os.getenv("API_HASH")
PHONE     = os.getenv("TG_PHONE")
SESSION   = "fire35_session"
HASH_FILE = "phone_code_hash.txt"


async def request_code():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()
    result = await client.send_code_request(PHONE)
    with open(HASH_FILE, "w") as f:
        f.write(result.phone_code_hash)
    print(f"[ok] Код отправлен на {PHONE}")
    print(f"[next] Запусти: python tg_auth.py --code XXXXX")
    await client.disconnect()


async def sign_in(code: str):
    if not os.path.exists(HASH_FILE):
        print("[err] Сначала запусти: python tg_auth.py --request")
        return
    with open(HASH_FILE) as f:
        phone_code_hash = f.read().strip()

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()
    try:
        await client.sign_in(PHONE, code, phone_code_hash=phone_code_hash)
    except SessionPasswordNeededError:
        pwd = input("Включена 2FA. Введи пароль: ")
        await client.sign_in(password=pwd)

    me = await client.get_me()
    print(f"[ok] Вошли как: {me.first_name} (@{me.username})")
    print(f"[ok] Session файл создан: {SESSION}.session")
    os.remove(HASH_FILE)
    await client.disconnect()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--request", action="store_true")
    p.add_argument("--code", type=str)
    args = p.parse_args()

    if args.request:
        asyncio.run(request_code())
    elif args.code:
        asyncio.run(sign_in(args.code))
    else:
        print("Использование:")
        print("  Шаг 1: python tg_auth.py --request")
        print("  Шаг 2: python tg_auth.py --code 12345")