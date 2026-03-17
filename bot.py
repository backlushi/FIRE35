"""
FIRE35 Telegram Bot
- /start  → соглашение (1 раз) → Mini App
- /avatar → загрузить фото аватарки
- /sync_members → привязать telegram_id участников из чата
- Экспертная система вопросов: Ответить / Пропустить / Не моя тема
- Рейтинг полезности ответов
"""
import asyncio
import os
import sqlite3
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters,
)

BOT_TOKEN  = os.getenv("FIRE35_BOT_TOKEN", "8752856976:AAEIqm7ZLBQx5kV7hGcnsxOqnCHM-5WIw1I")
MINI_APP_URL = "https://fire35club.duckdns.org/fire35-app/"
DB_PATH    = "/root/fire35/fire35.db"
CLUB_CHAT  = "-1003880059370"
ADMIN_USERNAME = "npension35"

PHOTO_STATE       = 0    # ConversationHandler для /avatar
ANSWER_STATE      = 10   # ConversationHandler для ответа на вопрос эксперта
BROADCAST_TEXT    = 20   # ConversationHandler для рассылки
BROADCAST_CONFIRM = 21

TERMS_URL   = "https://fire35club.duckdns.org/fire35-app/terms.html"
PRIVACY_URL = "https://fire35club.duckdns.org/fire35-app/privacy.html"

CONSENT_TEXT = (
    "🔐 *Соглашение об обработке данных*\n\n"
    "Для участия в клубе FIRE35 мы сохраняем:\n"
    "• Ваш Telegram username и имя\n"
    "• Финансовые показатели *(в обезличенном виде)*\n"
    "• Прогресс по темам клуба\n\n"
    "Данные используются только внутри клуба и не передаются третьим лицам.\n\n"
    "📄 [Пользовательское соглашение]({terms})\n"
    "🔐 [Политика конфиденциальности]({privacy})\n\n"
    "Нажми *«Согласен(а)»* для продолжения 👇"
).format(terms=TERMS_URL, privacy=PRIVACY_URL)

WELCOME_TEXT = (
    "Ты попал в FIRE35 — приватный клуб Анара Бабаева.\n\n"
    "Здесь люди системно растят капитал и помогают друг другу быстрее двигаться к финансовой независимости.\n\n"
    "Что внутри:\n\n"
    "📊 Личный рейтинг\n"
    "Каждый месяц подаёшь отчёт → видишь своё место в клубе по % сбережений и инвестиций.\n\n"
    "🧠 Умные вопросы по твоей профессии\n"
    "Указываешь навыки → AI подбирает вопросы, где твоя экспертиза реально полезна.\n\n"
    "⚡ Ответы без спама\n"
    "Задаёшь вопрос → если похожий уже был, сразу получаешь лучший ответ эксперта.\n\n"
    "⭐ Рейтинг участников\n"
    "Отвечаешь полезно → растёт рейтинг → больше вопросов в сутки, витрина услуг и личные вопросы Анару без посредников.\n\n"
    "📈 Прогресс по ключевым темам\n"
    "Соцсети, капитал $1M, инвестиционные промпты и другие навыки.\n\n"
    "Всё работает прямо в Telegram Mini App — без сайтов и регистрации."
)


# ─── БД-утилиты ──────────────────────────────────────────────
def db_conn():
    return sqlite3.connect(DB_PATH)


def find_user(tg_id: int, username: str | None) -> dict | None:
    conn = db_conn()
    cur = conn.cursor()
    user = None
    if tg_id:
        cur.execute(
            "SELECT id, pid, first_name, profession, skills, consent_given, telegram_id "
            "FROM users WHERE telegram_id=?", (str(tg_id),)
        )
        user = cur.fetchone()
    if not user and username:
        cur.execute(
            "SELECT id, pid, first_name, profession, skills, consent_given, telegram_id "
            "FROM users WHERE LOWER(telegram_username)=LOWER(?)", (username,)
        )
        user = cur.fetchone()
    conn.close()
    if user:
        return {
            "id": user[0], "pid": user[1], "first_name": user[2],
            "profession": user[3], "skills": user[4],
            "consent_given": bool(user[5]), "telegram_id": user[6],
        }
    return None


def link_tg_id(tg_id: int, username: str | None):
    if not username:
        return
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET telegram_id=? WHERE LOWER(telegram_username)=LOWER(?) "
        "AND (telegram_id IS NULL OR telegram_id='')",
        (str(tg_id), username),
    )
    conn.commit()
    conn.close()


def save_consent(user_id: int):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET consent_given=1 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


def save_avatar(tg_id: int, file_id: str) -> bool:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET avatar_file_id=? WHERE telegram_id=?", (file_id, str(tg_id)))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def create_new_user(tg_id: int, username: str | None, first_name: str | None, verified: bool = True) -> dict:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT pid FROM users WHERE pid GLOB 'P-[0-9]*' ORDER BY CAST(SUBSTR(pid, 3) AS INTEGER) DESC LIMIT 1")
    last = cur.fetchone()
    num = int(last[0].split("-")[1]) + 1 if last else 1
    pid = f"P-{num:03d}"
    cur.execute(
        "INSERT INTO users (pid, telegram_id, telegram_username, first_name, consent_given) VALUES (?,?,?,?,1)",
        (pid, str(tg_id), username, first_name or username),
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": user_id, "pid": pid, "first_name": first_name, "profession": None, "skills": None, "consent_given": True}


def get_question(question_id: int) -> dict | None:
    """Получить вопрос и данные автора."""
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT cq.id, cq.question, cq.tags, cq.created_at, cq.user_id, "
        "u.telegram_id, u.telegram_username, u.first_name "
        "FROM club_questions cq JOIN users u ON u.id=cq.user_id "
        "WHERE cq.id=?", (question_id,)
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "question": row[1], "tags": row[2],
        "created_at": row[3], "user_id": row[4],
        "author_tg_id": row[5], "author_username": row[6], "author_name": row[7],
    }


def find_user_by_tg(tg_id: int) -> dict | None:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, pid, telegram_username, answer_score, total_answers "
        "FROM users WHERE telegram_id=?", (str(tg_id),)
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "pid": row[1], "telegram_username": row[2],
        "answer_score": row[3] or 0, "total_answers": row[4] or 0,
    }


def save_expert_answer(question_id: int, expert_user_id: int, answer_text: str, response_time_minutes: int) -> int:
    """Сохранить ответ эксперта, вернуть answer_id."""
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO question_answers (question_id, answer, expert_user_id, response_time_minutes, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (question_id, answer_text, expert_user_id, response_time_minutes, datetime.utcnow().isoformat())
    )
    answer_id = cur.lastrowid
    conn.commit()
    conn.close()
    return answer_id


def update_answer_rating(answer_id: int, is_useful: bool):
    """Сохранить оценку и обновить счёт эксперта."""
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT expert_user_id, is_useful FROM question_answers WHERE id=?", (answer_id,)
    )
    row = cur.fetchone()
    if not row or row[1] is not None:
        conn.close()
        return False  # уже оценено или не найдено

    expert_user_id = row[0]
    cur.execute("UPDATE question_answers SET is_useful=? WHERE id=?", (1 if is_useful else 0, answer_id))

    if expert_user_id:
        if is_useful:
            cur.execute(
                "UPDATE users SET answer_score=COALESCE(answer_score,0)+1, "
                "total_answers=COALESCE(total_answers,0)+1 WHERE id=?",
                (expert_user_id,)
            )
        else:
            cur.execute(
                "UPDATE users SET total_answers=COALESCE(total_answers,0)+1 WHERE id=?",
                (expert_user_id,)
            )

    conn.commit()
    conn.close()
    return True


def get_answer(answer_id: int) -> dict | None:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT qa.id, qa.answer, qa.expert_user_id, qa.is_useful, qa.question_id, "
        "u.telegram_id, u.telegram_username "
        "FROM question_answers qa LEFT JOIN users u ON u.id=qa.expert_user_id "
        "WHERE qa.id=?", (answer_id,)
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "answer": row[1], "expert_user_id": row[2],
        "is_useful": row[3], "question_id": row[4],
        "expert_tg_id": row[5], "expert_username": row[6],
    }


async def check_club_member(bot, tg_id: int) -> bool | None:
    try:
        member = await bot.get_chat_member(CLUB_CHAT, tg_id)
        if member.status in ("left", "kicked"):
            return False
        return True
    except Exception as e:
        err = str(e).lower()
        if "user not found" in err or "participant" in err or "not a member" in err:
            return False
        return None


def mini_app_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Открыть FIRE35 🔥", web_app=WebAppInfo(url=MINI_APP_URL))
    ]])


def profile_incomplete(user: dict) -> bool:
    return not user.get("profession") or not user.get("skills")


# ─── /start ──────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg = update.effective_user
    link_tg_id(tg.id, tg.username)
    user = find_user(tg.id, tg.username)

    # Всегда показываем описание клуба
    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode="HTML",
    )

    if user and user["consent_given"]:
        # Уже зарегистрирован — сразу кнопка открыть Mini App
        note = "\n\n_Заполни профиль и навыки во вкладке Профиль_ 👤" if profile_incomplete(user) else ""
        await update.message.reply_text(
            "👇 Открой приложение:" + note,
            parse_mode="Markdown",
            reply_markup=mini_app_keyboard(),
        )
        return

    context.user_data["pending_tg_id"]    = tg.id
    context.user_data["pending_username"] = tg.username
    context.user_data["pending_name"]     = tg.first_name

    await update.message.reply_text(
        CONSENT_TEXT,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Согласен(а)", callback_data="consent_agree"),
            InlineKeyboardButton("❌ Отказаться",  callback_data="consent_decline"),
        ]]),
    )


# ─── Соглашение — callback ────────────────────────────────────
async def consent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "consent_decline":
        await query.message.reply_text(
            "Без согласия участие в клубе невозможно. Напиши /start если передумаешь."
        )
        return

    tg_id    = context.user_data.get("pending_tg_id",    update.effective_user.id)
    username = context.user_data.get("pending_username", update.effective_user.username)
    name     = context.user_data.get("pending_name",     update.effective_user.first_name)

    user = find_user(tg_id, username)

    if not user:
        is_member = await check_club_member(context.bot, tg_id)
        if is_member is False:
            await query.message.reply_text(
                "⛔️ Вы не являетесь участником клуба *FIRE35*.\n\n"
                "Чтобы получить доступ, вступите в группу клуба или свяжитесь с организатором.",
                parse_mode="Markdown",
            )
            return
        elif is_member is None:
            user = create_new_user(tg_id, username, name, verified=False)
            await query.message.reply_text(
                "✅ Согласие принято!\n\n"
                "⏳ Ваш аккаунт ожидает подтверждения организатором клуба.\n"
                f"Напишите @{ADMIN_USERNAME} для активации.",
                parse_mode="Markdown",
            )
            return
        else:
            user = create_new_user(tg_id, username, name, verified=True)

    if user and not user["consent_given"]:
        save_consent(user["id"])

    display = user["first_name"] or username or "участник"
    note = "\n\n_Заполни профиль и навыки во вкладке Профиль_ 👤" if profile_incomplete(user) else ""
    await query.message.reply_text(
        f"✅ Добро пожаловать, *{display}*!" + note,
        parse_mode="Markdown",
        reply_markup=mini_app_keyboard(),
    )


# ─── /avatar ─────────────────────────────────────────────────
async def avatar_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📸 Отправь своё фото — оно станет аватаркой в приложении FIRE35.\n\n"
        "_Отправь фото ниже или /cancel для отмены._",
        parse_mode="Markdown",
    )
    return PHOTO_STATE


async def avatar_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo   = update.message.photo[-1]
    file_id = photo.file_id
    ok = save_avatar(update.effective_user.id, file_id)
    if ok:
        await update.message.reply_text(
            "✅ Аватарка обновлена! Перезапусти приложение, чтобы увидеть изменения.",
            reply_markup=mini_app_keyboard(),
        )
    else:
        await update.message.reply_text(
            "⚠️ Аккаунт не найден. Сначала нажми /start и войди в клуб."
        )
    return ConversationHandler.END


async def avatar_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


# ─── Экспертная система вопросов ──────────────────────────────

async def expert_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Эксперт нажал «Ответить» — запрашиваем текст ответа."""
    query = update.callback_query
    await query.answer()

    question_id = int(query.data.split("_")[-1])
    question = get_question(question_id)

    if not question:
        await query.message.reply_text("⚠️ Вопрос не найден.")
        return ConversationHandler.END

    context.user_data["answering_question_id"] = question_id
    context.user_data["question_created_at"] = question["created_at"]
    context.user_data["question_author_tg_id"] = question["author_tg_id"]
    context.user_data["question_text"] = question["question"]

    await query.message.reply_text(
        f"✍️ <b>Отвечаешь на вопрос:</b>\n\n"
        f"<i>{question['question']}</i>\n\n"
        f"Напиши свой ответ (до 1000 символов). /cancel — отмена.",
        parse_mode="HTML",
    )
    return ANSWER_STATE


async def expert_reply_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получили текст ответа от эксперта."""
    answer_text = update.message.text.strip()
    if not answer_text:
        await update.message.reply_text("Ответ не может быть пустым. Попробуй ещё раз или /cancel.")
        return ANSWER_STATE

    if len(answer_text) > 1000:
        await update.message.reply_text("Слишком длинный ответ (максимум 1000 символов). Сократи и отправь снова.")
        return ANSWER_STATE

    question_id = context.user_data.get("answering_question_id")
    question_created_str = context.user_data.get("question_created_at", "")
    author_tg_id = context.user_data.get("question_author_tg_id")
    question_text = context.user_data.get("question_text", "")

    # Рассчитываем время ответа в минутах
    response_time = None
    try:
        q_time = datetime.fromisoformat(question_created_str)
        delta = datetime.utcnow() - q_time
        response_time = int(delta.total_seconds() / 60)
    except Exception:
        pass

    # Находим эксперта в БД
    expert = find_user_by_tg(update.effective_user.id)
    if not expert:
        await update.message.reply_text("⚠️ Твой аккаунт не найден. Напиши /start.")
        return ConversationHandler.END

    # Сохраняем ответ
    answer_id = save_expert_answer(question_id, expert["id"], answer_text, response_time)

    # Подтверждение эксперту
    speed_msg = ""
    if response_time is not None and response_time <= 60:
        speed_msg = "\n\n🔥 <b>Быстрый ответ!</b> +1 вопрос тебе сегодня."
    await update.message.reply_text(
        f"✅ Ответ отправлен!" + speed_msg,
        parse_mode="HTML",
        reply_markup=mini_app_keyboard(),
    )

    # Уведомляем автора вопроса с кнопками оценки
    if author_tg_id:
        expert_name = f"@{expert['telegram_username']}" if expert.get("telegram_username") else "участник"
        score_str = f" (⭐ {expert['answer_score']})" if expert["answer_score"] > 0 else ""
        rating_keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("👍 Полезно!", callback_data=f"qa_useful_{answer_id}"),
            InlineKeyboardButton("👎 Не очень",  callback_data=f"qa_no_{answer_id}"),
        ]])
        await context.bot.send_message(
            chat_id=author_tg_id,
            text=(
                f"💬 <b>{expert_name}{score_str} ответил на твой вопрос:</b>\n\n"
                f"<i>Q: {question_text}</i>\n\n"
                f"<b>A:</b> {answer_text}\n\n"
                f"Это было полезно?"
            ),
            parse_mode="HTML",
            reply_markup=rating_keyboard,
        )

    return ConversationHandler.END


async def expert_reply_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


async def expert_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Эксперт нажал «Пропустить»."""
    query = update.callback_query
    await query.answer("Пропущено")
    await query.edit_message_reply_markup(reply_markup=None)


async def expert_notmine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Эксперт нажал «Не моя тема»."""
    query = update.callback_query
    await query.answer("Понял, не буду присылать похожие")
    await query.edit_message_reply_markup(reply_markup=None)


# ─── Оценка ответа автором ───────────────────────────────────

async def answer_rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Автор вопроса оценивает ответ эксперта."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    action = parts[1]   # "useful" или "no"
    answer_id = int(parts[2])

    is_useful = (action == "useful")

    success = update_answer_rating(answer_id, is_useful)

    if not success:
        await query.answer("Оценка уже выставлена или ответ не найден", show_alert=True)
        return

    # Убираем кнопки
    await query.edit_message_reply_markup(reply_markup=None)

    if is_useful:
        await query.message.reply_text("👍 Спасибо за оценку! +1 к рейтингу эксперта.")
        # Уведомить эксперта
        answer = get_answer(answer_id)
        if answer and answer.get("expert_tg_id"):
            expert_name = f"@{answer['expert_username']}" if answer.get("expert_username") else "Ты"
            await context.bot.send_message(
                chat_id=answer["expert_tg_id"],
                text="⭐ Твой ответ оценили как полезный! +1 к рейтингу.",
            )
    else:
        await query.message.reply_text("Оценка сохранена.")


# ─── Пассивный сбор: любое сообщение в группе ────────────────
async def group_message_collector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    sender = update.effective_user
    if not sender or sender.is_bot:
        return

    conn = db_conn()
    cur  = conn.cursor()
    user_row = None
    if sender.username:
        cur.execute("SELECT id, telegram_id FROM users WHERE LOWER(telegram_username)=LOWER(?)", (sender.username,))
        user_row = cur.fetchone()
    if not user_row:
        cur.execute("SELECT id, telegram_id FROM users WHERE telegram_id=?", (str(sender.id),))
        user_row = cur.fetchone()

    if user_row:
        uid, existing_tg_id = user_row
        if not existing_tg_id:
            cur.execute("UPDATE users SET telegram_id=? WHERE id=?", (str(sender.id), uid))
            conn.commit()
    conn.close()


# ─── /myid, /link, /sync_members ─────────────────────────────
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await update.message.reply_text(
        f"🆔 Твой Telegram ID: `{u.id}`\n"
        f"👤 Имя: {u.first_name or '—'}\n"
        f"🔗 Username: @{u.username or '—'}",
        parse_mode="Markdown",
    )


async def link_pid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Использование: /link P-001 TELEGRAM_ID")
        return

    pid   = context.args[0].upper()
    tg_id = context.args[1].strip()

    conn = db_conn()
    cur  = conn.cursor()
    cur.execute("SELECT id, first_name FROM users WHERE pid=?", (pid,))
    row = cur.fetchone()
    if not row:
        await update.message.reply_text(f"❌ PID {pid} не найден в базе.")
        conn.close()
        return

    cur.execute("UPDATE users SET telegram_id=? WHERE pid=?", (tg_id, pid))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Готово!\n*{pid}* ({row[1] or '—'}) привязан к telegram\\_id `{tg_id}`",
        parse_mode="Markdown",
    )


async def sync_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.args[0] if context.args else CLUB_CHAT
    await update.message.reply_text(
        f"⏳ Синхронизирую участников из чата `{chat_id}`...",
        parse_mode="Markdown",
    )

    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, telegram_username FROM users
        WHERE telegram_username IS NOT NULL AND telegram_username != ''
          AND (telegram_id IS NULL OR telegram_id = '')
    """)
    users = cur.fetchall()
    conn.close()

    linked = 0
    not_found = 0
    errors = []

    for uid, uname in users:
        try:
            member = await context.bot.get_chat_member(chat_id, f"@{uname}")
            conn = db_conn()
            cur = conn.cursor()
            cur.execute("UPDATE users SET telegram_id=? WHERE id=?", (str(member.user.id), uid))
            conn.commit()
            conn.close()
            linked += 1
        except Exception as e:
            err_msg = str(e)
            not_found += 1
            if len(errors) < 3 and err_msg not in errors:
                errors.append(err_msg)
        await asyncio.sleep(1.0)

    err_text = ""
    if errors:
        err_text = "\n\n⚠️ Примеры ошибок:\n" + "\n".join(f"• `{e[:80]}`" for e in errors)

    await update.message.reply_text(
        f"✅ Готово!\n\n"
        f"🔗 Привязано: *{linked}*\n"
        f"❓ Не найдено: {not_found}" + err_text,
        parse_mode="Markdown",
    )


async def dup_ok_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Автор доволен авто-ответом."""
    query = update.callback_query
    await query.answer("Отлично! 🎉")
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("✅ Рады помочь! Если понадобится — задавай новые вопросы.")


async def dup_force_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Автор хочет всё равно разослать вопрос экспертам."""
    query = update.callback_query
    await query.answer()
    qid = int(query.data.split("_")[-1])

    # Вызываем API через HTTP
    user = find_user(query.from_user.id, query.from_user.username)
    if not user:
        await query.answer("Аккаунт не найден", show_alert=True)
        return

    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            # Получаем JWT
            from datetime import datetime, timedelta
            import jwt as pyjwt
            JWT_SECRET_LOCAL = "fire35_jwt_secret_prod"
            token = pyjwt.encode(
                {"sub": str(user["id"]), "exp": datetime.utcnow() + timedelta(hours=1)},
                JWT_SECRET_LOCAL, algorithm="HS256"
            )
            r = await client.post(
                f"http://localhost:8001/questions/{qid}/force-new",
                headers={"Authorization": f"Bearer {token}"},
            )
            if r.status_code == 200:
                await query.edit_message_reply_markup(reply_markup=None)
                await query.message.reply_text(
                    "✅ Вопрос отправлен экспертам клуба! "
                    "Ответ придёт в личку 🔔"
                )
            else:
                await query.message.reply_text("⚠️ Не удалось отправить. Попробуй через Mini App.")
    except Exception as e:
        print(f"[Bot] force-new error: {e}")
        await query.message.reply_text("⚠️ Ошибка. Попробуй через Mini App → задать вопрос снова.")


# ─── Рассылка (только для P-001) ──────────────────────────────
def get_all_telegram_ids() -> list[str]:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT telegram_id FROM users WHERE telegram_id IS NOT NULL AND telegram_id != ''"
    )
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg = update.effective_user
    user = find_user(tg.id, tg.username)
    if not user or user.get("pid") != "P-001":
        await update.message.reply_text("⛔ Нет доступа.")
        return ConversationHandler.END
    await update.message.reply_text(
        "📢 Введи текст рассылки (поддерживается HTML-форматирование).\n"
        "Или /cancel для отмены."
    )
    return BROADCAST_TEXT


async def broadcast_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data["broadcast_text"] = text
    ids = get_all_telegram_ids()
    context.user_data["broadcast_ids"] = ids
    await update.message.reply_text(
        f"📋 Сообщение:\n\n{text}\n\n"
        f"Будет отправлено <b>{len(ids)}</b> участникам.\n"
        "Отправить?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Отправить", callback_data="bc_yes"),
            InlineKeyboardButton("❌ Отмена",    callback_data="bc_no"),
        ]]),
    )
    return BROADCAST_CONFIRM


async def broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "bc_no":
        await query.message.reply_text("Рассылка отменена.")
        return ConversationHandler.END

    text = context.user_data.get("broadcast_text", "")
    ids  = context.user_data.get("broadcast_ids", [])

    await query.message.reply_text(f"🚀 Начинаю рассылку на {len(ids)} участников...")

    sent = 0
    failed = 0
    for tg_id in ids:
        try:
            await context.bot.send_message(
                chat_id=int(tg_id),
                text=text,
                parse_mode="HTML",
            )
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # ~20 сообщений/сек, не превышаем лимит Telegram

    await query.message.reply_text(
        f"✅ Рассылка завершена.\n"
        f"Отправлено: {sent}\n"
        f"Ошибок (бот заблокирован / нет telegram_id): {failed}"
    )
    return ConversationHandler.END


async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Рассылка отменена.")
    return ConversationHandler.END


# ─── Contact Requests ─────────────────────────────────────────
def _update_contact_request(req_id: int, status: str) -> dict | None:
    """Обновить статус запроса на знакомство в БД."""
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE contact_requests SET status=? WHERE id=? AND status='pending'",
        (status, req_id),
    )
    if cur.rowcount == 0:
        conn.close()
        return None
    cur.execute(
        "SELECT cr.from_user_id, cr.to_user_id, "
        "fu.telegram_id, fu.first_name, fu.last_name, fu.pid, "
        "tu.telegram_id, tu.first_name, tu.last_name, tu.pid, tu.telegram_username "
        "FROM contact_requests cr "
        "JOIN users fu ON fu.id=cr.from_user_id "
        "JOIN users tu ON tu.id=cr.to_user_id "
        "WHERE cr.id=?",
        (req_id,),
    )
    row = cur.fetchone()
    conn.commit()
    conn.close()
    if not row:
        return None
    return {
        "from_tg_id": row[2], "from_name": f"{row[3] or ''} {row[4] or ''}".strip() or row[5],
        "to_tg_id": row[6],   "to_name":   f"{row[7] or ''} {row[8] or ''}".strip() or row[9],
        "to_pid": row[9], "to_username": row[10],
    }


async def contact_accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    req_id = int(query.data.split("_")[-1])

    data = _update_contact_request(req_id, "accepted")
    if not data:
        await query.edit_message_text("ℹ️ Запрос уже обработан.")
        return

    # Уведомить отправителя запроса
    if data["from_tg_id"]:
        try:
            await context.bot.send_message(
                chat_id=int(data["from_tg_id"]),
                text=(
                    f"✅ <b>{data['to_name']}</b> принял(а) ваш запрос на знакомство!\n"
                    + (f"Telegram: @{data['to_username']}" if data["to_username"] else "")
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass

    await query.edit_message_text(
        f"✅ Вы приняли запрос на знакомство от <b>{data['from_name']}</b>.",
        parse_mode="HTML",
    )


async def contact_decline_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    req_id = int(query.data.split("_")[-1])

    data = _update_contact_request(req_id, "declined")
    if not data:
        await query.edit_message_text("ℹ️ Запрос уже обработан.")
        return

    await query.edit_message_text(
        f"❌ Вы отклонили запрос на знакомство от <b>{data['from_name']}</b>.",
        parse_mode="HTML",
    )


# ─── Intro recommendation callbacks ───────────────────────────
def _update_intro_status(intro_id: int, status: str) -> dict | None:
    """Обновить статус рекомендации и вернуть данные участника."""
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE introductions SET status=? WHERE id=? AND status IN ('pending','sent')",
        (status, intro_id),
    )
    if cur.rowcount == 0:
        conn.close()
        return None
    cur.execute(
        "SELECT i.from_user_id, fu.telegram_id, fu.first_name, fu.last_name, fu.pid, fu.telegram_username "
        "FROM introductions i JOIN users fu ON fu.id=i.from_user_id WHERE i.id=?",
        (intro_id,),
    )
    row = cur.fetchone()
    conn.commit()
    conn.close()
    if not row:
        return None
    return {
        "from_tg_id": row[1],
        "from_name": f"{row[2] or ''} {row[3] or ''}".strip() or row[4],
        "from_username": row[5],
    }


async def intro_accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    intro_id = int(query.data.split("_")[-1])

    data = _update_intro_status(intro_id, "accepted")
    if not data:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    # Автоматически создаём contact request через API
    user = find_user(query.from_user.id, query.from_user.username)
    if user and data["from_tg_id"]:
        try:
            import httpx, jwt as pyjwt
            token = pyjwt.encode(
                {"sub": str(user["id"]), "exp": __import__("datetime").datetime.utcnow() + __import__("datetime").timedelta(minutes=5)},
                "fire35_jwt_secret_prod", algorithm="HS256"
            )
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    f"http://localhost:8001/contact-request/{data.get('from_pid', '')}",
                    headers={"Authorization": f"Bearer {token}"},
                )
        except Exception:
            pass

        # Уведомляем рекомендованного участника
        try:
            sender_name = f"{query.from_user.first_name or ''} {query.from_user.last_name or ''}".strip()
            await context.bot.send_message(
                chat_id=int(data["from_tg_id"]),
                text=(
                    f"👋 <b>{sender_name}</b> хочет познакомиться с вами!\n"
                    f"Он увидел вас в рекомендациях клуба FIRE35."
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass

    # Получаем from_pid для корректного запроса
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT fu.pid FROM introductions i JOIN users fu ON fu.id=i.from_user_id WHERE i.id=?", (intro_id,))
    row = cur.fetchone()
    conn.close()
    from_pid = row[0] if row else "?"

    await query.edit_message_text(
        f"✅ Запрос на знакомство с <b>{data['from_name']}</b> отправлен!\n"
        f"Скоро они получат уведомление.",
        parse_mode="HTML",
    )


async def intro_skip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Пропущено")
    intro_id = int(query.data.split("_")[-1])
    _update_intro_status(intro_id, "skipped")
    # Просто убираем кнопки
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass


# ─── main ─────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ConversationHandler для /avatar
    avatar_conv = ConversationHandler(
        entry_points=[CommandHandler("avatar", avatar_start)],
        states={PHOTO_STATE: [MessageHandler(filters.PHOTO, avatar_receive)]},
        fallbacks=[CommandHandler("cancel", avatar_cancel)],
    )

    # ConversationHandler для экспертных ответов
    answer_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(expert_reply_start, pattern=r"^qa_reply_\d+$")],
        states={
            ANSWER_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, expert_reply_receive),
                CommandHandler("cancel", expert_reply_cancel),
            ]
        },
        fallbacks=[CommandHandler("cancel", expert_reply_cancel)],
        per_user=True,
        per_chat=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("link", link_pid))
    app.add_handler(CommandHandler("sync_members", sync_members))
    app.add_handler(CallbackQueryHandler(consent_callback, pattern="^consent_"))
    app.add_handler(CallbackQueryHandler(expert_skip,    pattern=r"^qa_skip_\d+$"))
    app.add_handler(CallbackQueryHandler(expert_notmine, pattern=r"^qa_notmine_\d+$"))
    app.add_handler(CallbackQueryHandler(answer_rate_callback, pattern=r"^qa_(useful|no)_\d+$"))
    app.add_handler(CallbackQueryHandler(dup_ok_callback,        pattern=r"^dup_ok_\d+$"))
    app.add_handler(CallbackQueryHandler(dup_force_callback,     pattern=r"^dup_force_\d+$"))
    app.add_handler(CallbackQueryHandler(contact_accept_callback,  pattern=r"^contact_accept_\d+$"))
    app.add_handler(CallbackQueryHandler(contact_decline_callback, pattern=r"^contact_decline_\d+$"))
    app.add_handler(CallbackQueryHandler(intro_accept_callback,    pattern=r"^intro_accept_\d+$"))
    app.add_handler(CallbackQueryHandler(intro_skip_callback,      pattern=r"^intro_skip_\d+$"))
    app.add_handler(avatar_conv)
    app.add_handler(answer_conv)
    # Пассивный сбор из группы
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & ~filters.COMMAND,
        group_message_collector,
    ))

    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            BROADCAST_TEXT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_receive)],
            BROADCAST_CONFIRM: [CallbackQueryHandler(broadcast_confirm, pattern="^bc_(yes|no)$")],
        },
        fallbacks=[CommandHandler("cancel", broadcast_cancel)],
        per_user=True,
        per_chat=False,
    )

    app.add_handler(broadcast_conv)
    print(f"Bot started. Mini App: {MINI_APP_URL}")
    app.run_polling()


if __name__ == "__main__":
    main()
