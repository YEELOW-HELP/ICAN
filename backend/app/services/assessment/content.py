"""Locale-keyed content for the Stage 1 Hybrid flow (Section 11: "do not
hard-code Ukrainian domain content into business logic"). Business logic
(next-question selection, state machine, extraction) never contains a
literal Ukrainian string -- it looks up a key here. Only `uk` has real
copy today; `ru`/`en`/`de` are architecture-ready keys, not translated yet
(explicitly out of scope for Stage 1)."""

from __future__ import annotations

DEFAULT_LOCALE = "uk"

_QUESTION_PROMPTS: dict[str, dict[str, str]] = {
    "name": {"uk": "Як тебе звати?"},
    "city": {"uk": "У якому місті ти зараз живеш?"},
    "current_status": {"uk": "Що з переліченого зараз про тебе правда?"},
    "total_experience": {"uk": "Скільки років загального досвіду роботи в тебе є (якщо є)?"},
    "key_skills_or_interests": {"uk": "Розкажи про свої навички або те, що тобі цікаво."},
    "desired_direction_hint": {"uk": "Чи є напрямок або сфера, яка тебе приваблює? Розкажи своїми словами."},
    "employment_format": {"uk": "Який формат зайнятості тобі підходить?"},
    "constraints": {"uk": "Чи є щось важливе, що варто врахувати (графік, локація, інше)?"},
}

_CHOICE_LABELS: dict[str, dict[str, str]] = {
    "working": {"uk": "Працюю"},
    "not_working": {"uk": "Не працюю"},
    "studying": {"uk": "Навчаюсь"},
    "other": {"uk": "Інше"},
    "full_time": {"uk": "Повна зайнятість"},
    "part_time": {"uk": "Часткова зайнятість"},
    "flexible": {"uk": "Гнучкий графік"},
}

MESSAGES: dict[str, dict[str, str]] = {
    "onboarding": {
        "uk": "Привіт! Це «МОЖУ: Мій Напрям». Пройдемо коротку діагностику, щоб краще зрозуміти твій напрям розвитку."
    },
    "consent_prompt": {
        "uk": "Перш ніж почати, підтверди, будь ласка, згоду на обробку даних для проходження діагностики."
    },
    "consent_confirm_button": {"uk": "Підтверджую згоду"},
    "no_access": {
        "uk": "Щоб почати діагностику, потрібен доступ. Введи промокод, якщо він у тебе є."
    },
    "promo_prompt": {"uk": "Введи промокод:"},
    "promo_invalid": {"uk": "Цей промокод недійсний або вже використаний максимальну кількість разів."},
    "promo_success": {"uk": "Доступ активовано! Починаємо діагностику."},
    "cv_offer": {"uk": "Завантажити резюме, якщо воно є, чи почати без нього?"},
    "cv_offer_upload_button": {"uk": "Завантажити резюме"},
    "cv_offer_skip_button": {"uk": "Почати без резюме"},
    "cv_upload_prompt": {"uk": "Надішли, будь ласка, файл резюме у форматі PDF або DOCX."},
    "cv_ack": {"uk": "Дякую! Врахую інформацію з резюме."},
    "cv_unsupported": {"uk": "Не вдалося прочитати файл. Спробуй PDF або DOCX, або продовжимо без резюме."},
    "cv_empty": {"uk": "Не вдалося розпізнати текст у файлі. Продовжимо без резюме."},
    "cv_too_large": {"uk": "Файл завеликий. Спробуй файл меншого розміру, або продовжимо без резюме."},
    "paused": {"uk": "Добре, зупиняємось тут. Напиши будь-що, коли будеш готовий продовжити -- я пам'ятаю, на чому ми зупинились."},
    "resumed": {"uk": "Продовжуємо з того ж місця."},
    "turn_error": {"uk": "Вибачте, сталася технічна помилка. Спробуйте, будь ласка, ще раз."},
    "completed": {"uk": "Діагностику завершено. Ми готуємо ваш персональний результат."},
    "structured_nudge": {"uk": "Обери, будь ласка, один із варіантів на кнопках вище."},
}


def get_message(key: str, locale: str = DEFAULT_LOCALE) -> str:
    entry = MESSAGES.get(key, {})
    return entry.get(locale) or entry.get(DEFAULT_LOCALE) or key


def get_question_prompt(question_id: str, locale: str = DEFAULT_LOCALE) -> str:
    entry = _QUESTION_PROMPTS.get(question_id, {})
    return entry.get(locale) or entry.get(DEFAULT_LOCALE) or question_id


def get_choice_label(choice: str, locale: str = DEFAULT_LOCALE) -> str:
    entry = _CHOICE_LABELS.get(choice, {})
    return entry.get(locale) or entry.get(DEFAULT_LOCALE) or choice
