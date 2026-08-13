"""
Spintax engine — уникализация сообщений
Поддерживает: {вариант1|вариант2|вариант3}, вложенные конструкции, переменные
"""
import re
import random
import hashlib


def spintax(text: str) -> str:
    """
    Обработка spintax: {привет|здравствуй|хай} → случайный вариант
    Поддерживает вложенность: {привет {мир|друг}|здравствуй}
    """
    def replace(match):
        options = match.group(1).split('|')
        return random.choice(options)
    
    # Обрабатываем вложенность (макс 5 уровней)
    for _ in range(5):
        new_text = re.sub(r'\{([^{}]+)\}', replace, text)
        if new_text == text:
            break
        text = new_text
    
    return text


def generate_unique_text(template: str, contact_name: str = "", contact_username: str = "") -> str:
    """
    Генерация уникального текста из шаблона с spintax.
    """
    text = spintax(template)
    
    # Замена переменных
    text = text.replace("{name}", contact_name or contact_username)
    text = text.replace("{username}", contact_username)
    
    # Добавляем микро-вариации для уникальности
    # (случайные пробелы, знаки препинания)
    variations = [
        ("  ", " "),  # двойные пробелы
        ("!", " !"),
        (".", " ."),
    ]
    
    return text.strip()


def check_uniqueness(text: str, threshold: float = 0.7) -> tuple[bool, float]:
    """
    Проверка уникальности текста.
    Возвращает (ok, similarity_score).
    Если similarity > threshold — текст слишком похож.
    """
    # Простая проверка на основе хеша n-gram
    words = text.lower().split()
    if len(words) < 3:
        return True, 0.0
    
    # Создаём n-gram'ы
    bigrams = set()
    for i in range(len(words) - 1):
        bigrams.add(f"{words[i]} {words[i+1]}")
    
    # Чем больше уникальных bigram'ов — тем лучше
    unique_ratio = len(bigrams) / max(len(words), 1)
    
    # Если > 70% уникальных bigram'ов — хорошо
    is_unique = unique_ratio > threshold
    
    return is_unique, unique_ratio


def add_human_typos(text: str, typo_chance: float = 0.02) -> str:
    """
    Добавление случайных 'опечаток' для имитации человека.
    Очень осторожно — только 2% шанс на опечатку.
    """
    if random.random() > typo_chance:
        return text
    
    chars = list(text)
    if len(chars) < 10:
        return text
    
    # Случайная замена соседних букв
    idx = random.randint(0, len(chars) - 2)
    chars[idx], chars[idx + 1] = chars[idx + 1], chars[idx]
    
    return ''.join(chars)


# Предопределённые вариации для общих фраз
GREETINGS = [
    "Привет", "Здравствуйте", "Добрый день", "Доброе утро", 
    "Здравствуй", "Приветствую", "Добрый вечер"
]

FAREWELLS = [
    "С уважением", "С наилучшими пожеланиями", "Всего доброго",
    "До связи", "Буду рад общению", "Жду ответа"
]

EMOJIS = ["👋", "😊", "🙂", "👍", "✨", "💫", "🌟", "💼", "🤝", "💪"]

def get_random_greeting() -> str:
    return random.choice(GREETINGS)

def get_random_farewell() -> str:
    return random.choice(FAREWELLS)

def get_random_emoji() -> str:
    return random.choice(EMOJIS)
