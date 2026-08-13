"""
Anti-spam module — защита от блокировок Telegram
- Умные задержки
- Дневные лимиты по возрасту аккаунта
- Прогрев аккаунтов
- Проверка первого сообщения
- Мониторинг состояния
"""
import sqlite3
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sender.db"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# DAILY LIMITS BY ACCOUNT AGE
# ============================================================

LIMITS_BY_AGE = {
    0: 3,      # День 0-1: макс 3 сообщения
    3: 5,      # День 1-3: макс 5
    7: 8,      # День 3-7: макс 8
    14: 12,    # День 7-14: макс 12
    30: 20,    # День 14-30: макс 20
    60: 30,    # День 30-60: макс 30
    90: 40,    # День 60-90: макс 40
    180: 60,   # День 90-180: макс 60
    365: 80,   # День 180+: макс 80
}


def get_daily_limit(account_age_days: int) -> int:
    """Дневной лимит сообщений по возрасту аккаунта."""
    limit = 3  # По умолчанию — минимум
    for age_threshold, age_limit in sorted(LIMITS_BY_AGE.items()):
        if account_age_days >= age_threshold:
            limit = age_limit
    return limit


def get_account_age(account_created_at: str) -> int:
    """Возраст аккаунта в днях."""
    if not account_created_at:
        return 0
    try:
        created = datetime.fromisoformat(account_created_at.replace('Z', '+00:00').split('+')[0])
        return (datetime.now() - created).days
    except Exception:
        return 0


def get_messages_sent_today(account_id: int) -> int:
    """Количество отправленных сообщений за сегодня."""
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    count = conn.execute(
        "SELECT COUNT(*) FROM message_log WHERE account_id = ? AND status = 'sent' AND date(sent_at) = ?",
        (account_id, today)
    ).fetchone()[0]
    conn.close()
    return count


def is_account_available(account_id: int, account_created_at: str) -> tuple[bool, str]:
    """Проверка доступности аккаунта для отправки."""
    age_days = get_account_age(account_created_at)
    daily_limit = get_daily_limit(age_days)
    sent_today = get_messages_sent_today(account_id)
    
    if sent_today >= daily_limit:
        return False, f"Дневной лимит: {sent_today}/{daily_limit}"
    
    return True, f"OK: {sent_today}/{daily_limit}"


# ============================================================
# SMART DELAYS
# ============================================================

def get_smart_delay(account_age_days: int, messages_today: int, is_first_message: bool = False) -> float:
    """
    Умная случайная задержка с учётом:
    - Возраста аккаунта
    - Количества отправленных сегодня
    - Первое ли это сообщение
    """
    # Базовые задержки по возрасту
    if account_age_days < 7:
        base_min, base_max = 180, 600      # 3-10 мин
    elif account_age_days < 14:
        base_min, base_max = 120, 420      # 2-7 мин
    elif account_age_days < 30:
        base_min, base_max = 90, 300       # 1.5-5 мин
    elif account_age_days < 90:
        base_min, base_max = 60, 180       # 1-3 мин
    else:
        base_min, base_max = 45, 150       # 45с-2.5 мин
    
    # Первое сообщение — дольше
    if is_first_message:
        base_min *= 1.5
        base_max *= 2.0
    
    # Увеличиваем при большом количестве сообщений
    if messages_today > 20:
        base_min *= 1.3
        base_max *= 1.5
    elif messages_today > 10:
        base_min *= 1.1
        base_max *= 1.2
    
    delay = random.uniform(base_min, base_max)
    
    # 5% шанс длинной паузы (имитация перерыва)
    if random.random() < 0.05:
        delay += random.uniform(600, 1800)  # +10-30 мин
    
    # 2% шанс очень длинной паузы (имитация обеда/отвлечения)
    if random.random() < 0.02:
        delay += random.uniform(1800, 3600)  # +30-60 мин
    
    return delay


def get_typing_delay(text_length: int) -> float:
    """
    Имитация времени набора текста.
    Средняя скорость: 200 символов/минуту = ~3.3/сек
    """
    base_time = text_length / 3.3  # секунды
    # Добавляем рандом ±30%
    variance = random.uniform(0.7, 1.3)
    return min(base_time * variance, 30)  # Макс 30 секунд


# ============================================================
# FIRST MESSAGE SAFETY
# ============================================================

def check_first_message(text: str) -> tuple[bool, str]:
    """
    Проверка безопасности первого сообщения.
    Возвращает (safe, reason).
    """
    text_lower = text.lower()
    
    # Проверка на ссылки
    link_patterns = ['http://', 'https://', 't.me/', 'telegram.me/', 'www.']
    for pattern in link_patterns:
        if pattern in text_lower:
            return False, f"🚫 Ссылки в первом сообщении запрещены! ({pattern})"
    
    # Проверка на длину
    if len(text) > 500:
        return False, "🚫 Первое сообщение слишком длинное (макс 500 символов)"
    
    # Проверка на спам-слова
    spam_words = [
        'заработок', 'доход', 'миллион', 'бесплатно', 'акция',
        'скидка', 'промокод', 'выиграй', 'приз', 'лотерея',
        'крипто', 'bitcoin', 'инвестиции', 'гарантия',
    ]
    for word in spam_words:
        if word in text_lower:
            return False, f"🚫 Спам-слово в первом сообщении: '{word}'"
    
    # Проверка на CAPS
    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    if caps_ratio > 0.5 and len(text) > 20:
        return False, "🚫 Слишком много заглавных букв"
    
    # Проверка на эмодзи спам
    emoji_count = sum(1 for c in text if ord(c) > 127000)
    if emoji_count > 5:
        return False, "🚫 Слишком много эмодзи"
    
    return True, "✅ Первое сообщение безопасно"


def is_first_contact(contact_username: str) -> bool:
    """Проверяем, писали ли мы этому контакту раньше."""
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM message_log WHERE contact_username = ? AND status = 'sent'",
        (contact_username,)
    ).fetchone()[0]
    conn.close()
    return count == 0


# ============================================================
# ACCOUNT WARMING
# ============================================================

def get_warming_status(account_created_at: str) -> dict:
    """Статус прогрева аккаунта."""
    age_days = get_account_age(account_created_at)
    
    if age_days < 1:
        return {"status": "new", "label": "Новый", "emoji": "🔴", "max_messages": 3}
    elif age_days < 7:
        return {"status": "fresh", "label": "Свежий", "emoji": "🟠", "max_messages": 8}
    elif age_days < 14:
        return {"status": "warming", "label": "Прогрев", "emoji": "🟡", "max_messages": 12}
    elif age_days < 30:
        return {"status": "warm", "label": "Прогретый", "emoji": "🟢", "max_messages": 20}
    elif age_days < 90:
        return {"status": "mature", "label": "Зрелый", "emoji": "🟢", "max_messages": 40}
    else:
        return {"status": "veteran", "label": "Ветеран", "emoji": "💚", "max_messages": 80}


# ============================================================
# FLOOD MANAGEMENT
# ============================================================

class FloodManager:
    """Менеджер flood wait'ов."""
    
    def __init__(self):
        self.flood_until = {}  # account_id -> timestamp
    
    def is_flooded(self, account_id: int) -> bool:
        return self.flood_until.get(account_id, 0) > time.time()
    
    def set_flood(self, account_id: int, seconds: int):
        self.flood_until[account_id] = time.time() + seconds
    
    def get_wait_time(self, account_id: int) -> int:
        remaining = self.flood_until.get(account_id, 0) - time.time()
        return max(0, int(remaining))
    
    def clear_flood(self, account_id: int):
        self.flood_until.pop(account_id, None)
    
    def get_available_accounts(self, accounts: list) -> list:
        """Фильтрует аккаунты без флуда."""
        return [a for a in accounts if not self.is_flooded(a['id'])]
    
    def get_soonest_available(self) -> int:
        """Время до ближайшего доступного аккаунта."""
        if not self.flood_until:
            return 0
        now = time.time()
        future_times = [t for t in self.flood_until.values() if t > now]
        if not future_times:
            return 0
        return int(min(future_times) - now)


# Глобальный экземпляр
flood_manager = FloodManager()


# ============================================================
# DAILY SCHEDULE
# ============================================================

def get_sending_window() -> tuple[int, int]:
    """Окно отправки (часы). Не отправляем ночью."""
    return 9, 22  # с 9:00 до 22:00


def is_in_sending_window() -> bool:
    """Проверка, находимся ли в окне отправки."""
    start, end = get_sending_window()
    current_hour = datetime.now().hour
    return start <= current_hour < end


def get_random_pause_in_window() -> int:
    """Случайная пауза в рамках окна отправки."""
    # Имитация обеда (12-14) — длинная пауза
    hour = datetime.now().hour
    if 12 <= hour <= 14:
        return random.randint(1800, 3600)  # 30-60 мин
    
    # Имитация перерыва
    if random.random() < 0.1:
        return random.randint(600, 1800)  # 10-30 мин
    
    return 0
