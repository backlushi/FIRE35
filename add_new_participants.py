"""
Добавляем 15 новых участников FIRE35 (P-052..P-066)
с реальными отчётами за февраль 2026.
Запускается через: python add_new_participants.py
"""
import paramiko
import io

SSH_HOST = "185.73.126.238"
SSH_USER = "root"
SSH_PASS = "ANPCq2t8Gr73N"

# ─── скрипт, который выполнится ВНУТРИ контейнера ─────────
INNER_SCRIPT = '''
import sys, os
sys.path.insert(0, "/app")
os.environ.setdefault("DEFAULT_PASSWORD", "fire2026")

from passlib.context import CryptContext
from database import SessionLocal, User, Report, init_db

init_db()
db = SessionLocal()
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
hashed = pwd_ctx.hash("fire2026")

PARTICIPANTS = [
    # pid, first_name, last_name, profession
    ("P-052", "Наталья",   "Добровольская", "Специалист"),
    ("P-053", "Эльвира",   "",              "Бухгалтер"),
    ("P-054", "Марина",    "",              "Финансист"),
    ("P-055", "Никита",    "Юманов",        "Инженер"),
    ("P-056", "Anton",     "Paster",        "Специалист"),
    ("P-057", "Максим",    "",              "Госслужащий"),
    ("P-058", "Алексей",   "Ромадин",       "Менеджер"),
    ("P-059", "Михаил",    "Суханов",       "Инженер"),
    ("P-060", "Анастасия", "Яшкина",        "Риэлтор"),
    ("P-061", "Пётр",      "",              "Инженер"),
    ("P-062", "Вячеслав",  "",              "Инженер"),
    ("P-063", "Роман",     "",              "Маркетолог"),
    ("P-064", "Иван",      "",              "Инженер"),
    ("P-065", "Евгений",   "",              "IT-специалист"),
    ("P-066", "Оксана",    "",              "Специалист"),
]

# (pid, budget_yes, income_gt_expense, savings_pct, invest_pct)
REPORTS = {
    "P-052": (False, True,  30.0,  0.0),   # Наталья: сбер 30%, инвест 0%
    "P-053": (True,  True,  20.0, 100.0),  # Эльвира: 20%, всё в инвест
    "P-054": (True,  True,  50.0, 100.0),  # Марина: 50%, всё в инвест
    "P-055": (False, True,  60.0,  60.0),  # Никита: 60%, 60% из них в инвест
    "P-056": (False, False, 25.0, 100.0),  # Anton: ~25%, всё в инвест
    "P-057": (True,  True,  13.0,   0.0),  # Максим: 13%, ещё не инвестирует
    "P-058": (True,  True,   0.0,   0.0),  # Алексей: гасит кредиты
    "P-059": (False, False,  7.0, 100.0),  # Михаил: 5-10%, всё в инвест
    "P-060": (True,  True,  16.0, 100.0),  # Анастасия: 16%, всё в инвест
    "P-061": (True,  True,  30.0,  25.0),  # Пётр: 30%, 25% из них на вклад
    "P-062": (True,  True,  70.0, 100.0),  # Вячеслав: 70% (ипотека)
    "P-063": (True,  True,  10.0,   0.0),  # Роман: 10%, инвест 0%
    "P-064": (True,  False, 25.0,  90.0),  # Иван: 25%, 90% в инвест
    "P-065": (True,  True,  64.0, 100.0),  # Евгений: 63.63%, всё в инвест
    "P-066": (True,  True,  64.0, 100.0),  # Оксана: 64%, всё в инвест
}

added = 0
skipped = 0

for pid, first_name, last_name, profession in PARTICIPANTS:
    existing = db.query(User).filter(User.pid == pid).first()
    if existing:
        print(f"  [skip] {pid} уже существует")
        skipped += 1
        continue

    user = User(
        pid=pid,
        first_name=first_name,
        last_name=last_name if last_name else None,
        profession=profession,
        password_hash=hashed,
    )
    db.add(user)
    db.flush()  # получаем user.id

    bud, inc, sav, inv = REPORTS[pid]
    report = Report(
        user_id=user.id,
        month="2026-02",
        budget_yes=bud,
        income_gt_expense=inc,
        savings_pct=sav,
        invest_pct=inv,
    )
    db.add(report)
    added += 1
    print(f"  [+] {pid} {first_name} {last_name} ({profession}) — сбер {sav}%")

db.commit()
db.close()

total = db.query(User).count() if False else added + skipped
print(f"\\n[done] Добавлено: {added}, пропущено: {skipped}")
print(f"[done] Пароль для всех новых: fire2026")
'''

def main():
    print(f"[1] Подключаемся к {SSH_HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS)

    # Загружаем скрипт во временный файл на сервер
    print("[2] Загружаем скрипт на сервер...")
    sftp = client.open_sftp()
    sftp.putfo(io.BytesIO(INNER_SCRIPT.encode("utf-8")), "/tmp/add_fire35_users.py")
    sftp.close()

    # Копируем файл ВНУТРЬ контейнера
    print("[3] Копируем скрипт в контейнер...")
    _, stdout_cp, stderr_cp = client.exec_command(
        "docker cp /tmp/add_fire35_users.py fire35_backend:/tmp/add_fire35_users.py"
    )
    stdout_cp.read(); stderr_cp.read()

    # Запускаем внутри контейнера
    print("[4] Запускаем внутри fire35_backend...")
    stdin, stdout, stderr = client.exec_command(
        "docker exec fire35_backend python /tmp/add_fire35_users.py"
    )
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")

    if out:
        print(out)
    if err:
        print("[stderr]", err)

    # Проверяем итоговое число участников
    print("[5] Проверяем кол-во участников в базе...")
    _, stdout2, _ = client.exec_command(
        'docker exec fire35_backend python -c '
        '"from database import SessionLocal, User; db=SessionLocal(); '
        'print(f\'Итого участников: {db.query(User).count()}\'); db.close()"'
    )
    print(stdout2.read().decode())

    client.close()
    print("[done] Готово!")

if __name__ == "__main__":
    main()