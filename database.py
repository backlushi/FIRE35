"""
FIRE35 — SQLite models via SQLAlchemy
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, Float,
    DateTime, ForeignKey, UniqueConstraint, LargeBinary, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:////root/fire35/fire35.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=True)
    pid = Column(String, unique=True, index=True)          # P-001 … P-051
    password_hash = Column(String, nullable=True)
    telegram_username = Column(String, nullable=True)      # @username для связи
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    profession = Column(String, nullable=True)
    skills = Column(String, nullable=True)                 # legacy текстовое поле
    topics_done    = Column(String,  nullable=True)        # "1,3,5" — изученные темы
    avatar_file_id = Column(String,  nullable=True)        # Telegram file_id фото
    consent_given  = Column(Boolean, nullable=True, default=False)
    # Рейтинг экспертности
    answer_score   = Column(Integer, default=0, nullable=True)
    total_answers  = Column(Integer, default=0, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)

    # ── Конфиденциальность и рекомендации ──
    intro_consent_given      = Column(Boolean, default=False, nullable=False)
    intro_consent_updated_at = Column(DateTime, nullable=True)
    question_visibility      = Column(String, default="skills_only", nullable=False)  # 'all' | 'skills_only'
    intro_receive            = Column(Boolean, default=True, nullable=False)           # получать рекомендации
    intro_frequency          = Column(String, default="biweekly", nullable=False)      # 'weekly'|'biweekly'|'monthly'|'never'
    last_seen                = Column(DateTime, nullable=True)                         # последнее появление в мини-апп
    onboarding_done          = Column(Boolean, default=False, nullable=False)           # прошёл вводный AI-тест

    reports = relationship("Report", back_populates="user")
    sent_requests = relationship(
        "ContactRequest", foreign_keys="ContactRequest.from_user_id",
        back_populates="from_user")
    received_requests = relationship(
        "ContactRequest", foreign_keys="ContactRequest.to_user_id",
        back_populates="to_user")
    skills_list = relationship("UserSkill", back_populates="user",
                               cascade="all, delete-orphan")
    sent_intros = relationship("Introduction", foreign_keys="Introduction.from_user_id",
                               back_populates="from_user")
    received_intros = relationship("Introduction", foreign_keys="Introduction.to_user_id",
                                   back_populates="to_user")


class UserSkill(Base):
    """Нормализованные навыки пользователя (до 12 штук)."""
    __tablename__ = "user_skills"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    skill_name = Column(String, nullable=False)   # нормализованный slug: "python", "smm"

    __table_args__ = (UniqueConstraint("user_id", "skill_name", name="uq_user_skill"),)

    user = relationship("User", back_populates="skills_list")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    month = Column(String, nullable=False)                 # "2026-02"
    budget_yes = Column(Boolean, nullable=False, default=False)
    income_gt_expense = Column(Boolean, nullable=False, default=False)
    savings_pct = Column(Float, nullable=False, default=0.0)
    invest_pct = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "month", name="uq_user_month"),)

    user = relationship("User", back_populates="reports")


class ContactRequest(Base):
    __tablename__ = "contact_requests"

    id = Column(Integer, primary_key=True, index=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="pending")   # pending / accepted / declined
    created_at = Column(DateTime, default=datetime.utcnow)

    from_user = relationship("User", foreign_keys=[from_user_id],
                             back_populates="sent_requests")
    to_user = relationship("User", foreign_keys=[to_user_id],
                           back_populates="received_requests")


class ClubQuestion(Base):
    __tablename__ = "club_questions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question = Column(String, nullable=False)
    tags = Column(String, nullable=True)          # "python,инвестиции,smm" через запятую
    is_duplicate = Column(Boolean, default=False, nullable=True)
    force_new = Column(Boolean, default=False, nullable=True)
    flag_count = Column(Integer, default=0, nullable=True)  # жалобы участников
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    answers = relationship("QuestionAnswer", back_populates="question",
                           cascade="all, delete-orphan",
                           order_by="QuestionAnswer.created_at")


class QuestionEmbedding(Base):
    """Векторное представление вопроса для поиска дубликатов."""
    __tablename__ = "question_embeddings"
    question_id = Column(Integer, ForeignKey("club_questions.id"), primary_key=True)
    embedding = Column(LargeBinary, nullable=False)   # numpy float32 bytes
    created_at = Column(DateTime, default=datetime.utcnow)
    question = relationship("ClubQuestion", foreign_keys=[question_id])


class QuestionDuplicate(Base):
    """Запись о найденном дубликате вопроса."""
    __tablename__ = "question_duplicates"
    id = Column(Integer, primary_key=True, index=True)
    original_question_id = Column(Integer, ForeignKey("club_questions.id"), nullable=False)
    duplicate_question_id = Column(Integer, ForeignKey("club_questions.id"), nullable=False)
    similarity_score = Column(Float, nullable=False)
    handled_at = Column(DateTime, default=datetime.utcnow)
    original = relationship("ClubQuestion", foreign_keys=[original_question_id])
    duplicate = relationship("ClubQuestion", foreign_keys=[duplicate_question_id])


class QuestionAnswer(Base):
    __tablename__ = "question_answers"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("club_questions.id"), nullable=False)
    answer = Column(String, nullable=False)
    # Для экспертной системы (NULL = ответ Анара):
    expert_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    response_time_minutes = Column(Integer, nullable=True)
    is_useful = Column(Boolean, nullable=True)   # принятый ответ (автором вопроса)
    vote_score = Column(Integer, default=0, nullable=False)  # сумма голосов участников
    created_at = Column(DateTime, default=datetime.utcnow)

    question = relationship("ClubQuestion", back_populates="answers")
    expert = relationship("User", foreign_keys=[expert_user_id])
    votes = relationship("AnswerVote", back_populates="answer", cascade="all, delete-orphan")


class AnswerVote(Base):
    """Голос участника за ответ (+1 upvote, -1 downvote)."""
    __tablename__ = "answer_votes"

    id = Column(Integer, primary_key=True, index=True)
    answer_id = Column(Integer, ForeignKey("question_answers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vote = Column(Integer, nullable=False)          # +1 или -1
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("answer_id", "user_id", name="uq_answer_vote"),)

    answer = relationship("QuestionAnswer", back_populates="votes")
    user = relationship("User")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    text = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class FullReport(Base):
    """Полный текстовый отчёт участника (из бот-анкеты)."""
    __tablename__ = "full_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    month = Column(String, nullable=False)
    budget_text = Column(String, nullable=True)
    income_text = Column(String, nullable=True)
    savings_text = Column(String, nullable=True)
    invest_text = Column(String, nullable=True)
    books = Column(String, nullable=True)
    failures = Column(String, nullable=True)
    fears = Column(String, nullable=True)
    achievements = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "month", name="uq_full_report_user_month"),)
    user = relationship("User")


class FcmToken(Base):
    __tablename__ = "fcm_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    token = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Introduction(Base):
    """Рекомендация знакомства между двумя участниками (генерируется cron-джобой)."""
    __tablename__ = "introductions"

    id           = Column(Integer, primary_key=True, index=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    to_user_id   = Column(Integer, ForeignKey("users.id"), nullable=False)
    score        = Column(Float, nullable=False, default=0.0)   # match-score 0..1
    reason       = Column(String, nullable=True)                 # текст причины совпадения
    status       = Column(String, default="pending")             # pending|sent|accepted|skipped
    created_at   = Column(DateTime, default=datetime.utcnow)

    from_user = relationship("User", foreign_keys=[from_user_id], back_populates="sent_intros")
    to_user   = relationship("User", foreign_keys=[to_user_id],   back_populates="received_intros")
    feedbacks = relationship("IntroFeedback", back_populates="introduction",
                             cascade="all, delete-orphan")


class IntroFeedback(Base):
    """Реакция пользователя на рекомендацию знакомства."""
    __tablename__ = "intro_feedback"

    id             = Column(Integer, primary_key=True, index=True)
    intro_id       = Column(Integer, ForeignKey("introductions.id"), nullable=False)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    feedback       = Column(String, nullable=False)    # 'accept'|'skip'
    created_at     = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("intro_id", "user_id", name="uq_intro_feedback"),)

    introduction = relationship("Introduction", back_populates="feedbacks")
    user         = relationship("User")


class GameSession(Base):
    """Сессия мультиплеерной игры в Монополию."""
    __tablename__ = "game_sessions"

    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    host_user_id  = Column(Integer, ForeignKey("users.id"), nullable=False)
    guest_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status        = Column(String, default="waiting")   # waiting|active|finished
    state_json    = Column(String, nullable=True)        # полный JSON-стейт игры
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow)

    host  = relationship("User", foreign_keys=[host_user_id])
    guest = relationship("User", foreign_keys=[guest_user_id])


class Achievement(Base):
    """Достижение участника — результат работы с AI."""
    __tablename__ = "achievements"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    content      = Column(String, nullable=False)       # описание достижения
    prompt_text  = Column(String, nullable=True)        # промпт который использовали
    ai_tool      = Column(String, nullable=True)        # ChatGPT, Claude, Midjourney…
    media_url    = Column(String, nullable=True)        # путь к файлу или ссылка
    media_type   = Column(String, nullable=True)        # "photo" | "audio" | None
    likes        = Column(Integer, default=0, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow)

    user  = relationship("User")
    liked = relationship("AchievementLike", back_populates="achievement",
                         cascade="all, delete-orphan")


class AchievementLike(Base):
    """Реакция участника на достижение (fire / idea)."""
    __tablename__ = "achievement_likes"

    id             = Column(Integer, primary_key=True, index=True)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=False)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    reaction       = Column(String, default="fire", nullable=False)  # "fire" | "idea"
    created_at     = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("achievement_id", "user_id", name="uq_ach_like"),)

    achievement = relationship("Achievement", back_populates="liked")
    user        = relationship("User")


class TrainerAttempt(Base):
    """Попытка участника в тренажёре промптов (без сохранения в лидерборд)."""
    __tablename__ = "trainer_attempts"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic_id     = Column(String, nullable=False)       # investments|budget|realestate|career|mindset
    score        = Column(Integer, default=0)
    max_score    = Column(Integer, default=100)
    prompt_text  = Column(String, nullable=False)
    feedback_json = Column(String, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class AiBattleChallenge(Base):
    """Еженедельный AI-батл: задание недели."""
    __tablename__ = "ai_battle_challenges"

    id            = Column(Integer, primary_key=True, index=True)
    week          = Column(String, unique=True, nullable=False)  # "2026-W11"
    theme         = Column(String, nullable=False)               # "Промпт-инжиниринг"
    task          = Column(String, nullable=False)               # Описание задания
    criteria_json = Column(String, nullable=False)               # JSON список критериев
    created_at    = Column(DateTime, default=datetime.utcnow)

    submissions = relationship("AiBattleSubmission", back_populates="challenge")


class AiBattleSubmission(Base):
    """Ответ участника на AI-батл задание."""
    __tablename__ = "ai_battle_submissions"

    id           = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(Integer, ForeignKey("ai_battle_challenges.id"), nullable=False)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    prompt_text  = Column(String, nullable=False)
    score        = Column(Integer, nullable=False, default=0)    # 0-100
    feedback_json = Column(String, nullable=True)                # JSON с разбором
    submitted_at  = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("challenge_id", "user_id", name="uq_battle_user_challenge"),)

    challenge = relationship("AiBattleChallenge", back_populates="submissions")
    user      = relationship("User")


class Message(Base):
    """Личное сообщение между двумя участниками (только друзья)."""
    __tablename__ = "messages"

    id          = Column(Integer, primary_key=True, index=True)
    sender_id   = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content     = Column(String, nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)
    read_at     = Column(DateTime, nullable=True)

    sender   = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    # Миграции: добавляем новые колонки если их нет
    with engine.connect() as conn:
        # --- users ---
        user_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(users)"))]
        for col, definition in [
            ("password_hash",     "TEXT"),
            ("telegram_username", "TEXT"),
            ("topics_done",       "TEXT"),
            ("avatar_file_id",    "TEXT"),
            ("consent_given",     "INTEGER DEFAULT 0"),
            ("answer_score",      "INTEGER DEFAULT 0"),
            ("total_answers",     "INTEGER DEFAULT 0"),
        ]:
            if col not in user_cols:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {definition}"))

        # --- club_questions ---
        q_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(club_questions)"))]
        if "tags" not in q_cols:
            conn.execute(text("ALTER TABLE club_questions ADD COLUMN tags TEXT"))
        # --- club_questions new cols ---
        if "is_duplicate" not in q_cols:
            conn.execute(text("ALTER TABLE club_questions ADD COLUMN is_duplicate INTEGER DEFAULT 0"))
        if "force_new" not in q_cols:
            conn.execute(text("ALTER TABLE club_questions ADD COLUMN force_new INTEGER DEFAULT 0"))
        # remove auto_answered_from_id if exists (replaced by is_duplicate)

        # --- question_answers ---
        qa_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(question_answers)"))]
        for col, definition in [
            ("expert_user_id",        "INTEGER"),
            ("response_time_minutes", "INTEGER"),
            ("is_useful",             "INTEGER"),
            ("vote_score",            "INTEGER DEFAULT 0"),
        ]:
            if col not in qa_cols:
                conn.execute(text(f"ALTER TABLE question_answers ADD COLUMN {col} {definition}"))

        # --- club_questions: flag_count for moderation ---
        if "flag_count" not in q_cols:
            conn.execute(text("ALTER TABLE club_questions ADD COLUMN flag_count INTEGER DEFAULT 0"))

        # --- users: privacy & intro fields ---
        for col, definition in [
            ("intro_consent_given",      "INTEGER DEFAULT 0"),
            ("intro_consent_updated_at", "DATETIME"),
            ("question_visibility",      "TEXT DEFAULT 'skills_only'"),
            ("intro_receive",            "INTEGER DEFAULT 1"),
            ("intro_frequency",          "TEXT DEFAULT 'biweekly'"),
            ("last_name",                "TEXT"),
            ("last_seen",                "DATETIME"),
            ("onboarding_done",          "INTEGER DEFAULT 0"),
        ]:
            if col not in user_cols:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {definition}"))

        # --- achievements: media_type ---
        ach_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(achievements)"))]
        if "media_type" not in ach_cols:
            conn.execute(text("ALTER TABLE achievements ADD COLUMN media_type TEXT"))

        # --- achievement_likes: reaction ---
        like_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(achievement_likes)"))]
        if "reaction" not in like_cols:
            conn.execute(text("ALTER TABLE achievement_likes ADD COLUMN reaction TEXT DEFAULT 'fire'"))

        conn.commit()

    # Таблицы создаются через create_all выше, дополнительных миграций не нужно
