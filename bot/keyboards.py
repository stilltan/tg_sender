"""Keyboard builders for the bot."""
from telegram import (
    ReplyKeyboardMarkup, 
    ReplyKeyboardRemove, 
    KeyboardButton, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup
)


def build_main_menu() -> ReplyKeyboardMarkup:
    """Main menu keyboard."""
    keyboard = [
        [KeyboardButton("📋 Контакты"), KeyboardButton("📤 Рассылка")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("📝 Шаблоны")],
        [KeyboardButton("⚙️ Настройки"), KeyboardButton("❓ Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def build_contacts_menu() -> InlineKeyboardMarkup:
    """Contacts submenu."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Все контакты", callback_data="contacts_all"),
            InlineKeyboardButton("✅ Активные", callback_data="contacts_active"),
        ],
        [
            InlineKeyboardButton("📩 Написанные", callback_data="contacts_contacted"),
            InlineKeyboardButton("❌ Не заинтересованы", callback_data="contacts_not_interested"),
        ],
        [
            InlineKeyboardButton("🚫 Заблокировали", callback_data="contacts_blocked"),
            InlineKeyboardButton("➕ Добавить контакт", callback_data="contact_add"),
        ],
        [
            InlineKeyboardButton("📥 Импорт из Google Sheets", callback_data="import_gsheets"),
            InlineKeyboardButton("📥 Импорт из CSV", callback_data="import_csv"),
        ],
        [
            InlineKeyboardButton("🗑 Очистить все", callback_data="contacts_delete_all"),
            InlineKeyboardButton("◀️ Назад", callback_data="back_main"),
        ],
    ])


def build_contact_actions(contact_id: int) -> InlineKeyboardMarkup:
    """Actions for a specific contact."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Написали", callback_data=f"mark_contacted_{contact_id}"),
            InlineKeyboardButton("❌ Не заинтересован", callback_data=f"mark_not_interested_{contact_id}"),
        ],
        [
            InlineKeyboardButton("🚫 Заблокировал", callback_data=f"mark_blocked_{contact_id}"),
            InlineKeyboardButton("🔄 Сбросить статус", callback_data=f"mark_active_{contact_id}"),
        ],
        [
            InlineKeyboardButton("🗑 Удалить", callback_data=f"contact_delete_{contact_id}"),
            InlineKeyboardButton("◀️ Назад", callback_data="contacts_all"),
        ],
    ])


def build_contacts_list_keyboard(contacts: list, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    """Paginated contacts list."""
    start = page * per_page
    end = start + per_page
    page_contacts = contacts[start:end]
    
    buttons = []
    for c in page_contacts:
        status_icon = {
            'active': '🟢',
            'contacted': '✅',
            'not_interested': '❌',
            'blocked': '🚫',
        }.get(c['status'], '⚪')
        
        name = c['name'] or c['username']
        buttons.append([
            InlineKeyboardButton(
                f"{status_icon} {name}",
                callback_data=f"contact_{c['id']}"
            )
        ])
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"contacts_page_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(f"📄 {page+1}", callback_data="noop"))
    if end < len(contacts):
        nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"contacts_page_{page+1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back_contacts")])
    
    return InlineKeyboardMarkup(buttons)


def build_campaign_menu() -> InlineKeyboardMarkup:
    """Campaign management menu."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📤 Новая рассылка", callback_data="campaign_new"),
            InlineKeyboardButton("📋 Мои рассылки", callback_data="campaign_list"),
        ],
        [
            InlineKeyboardButton("📊 Статистика рассылок", callback_data="campaign_stats"),
            InlineKeyboardButton("◀️ Назад", callback_data="back_main"),
        ],
    ])


def build_campaign_actions(campaign_id: int, status: str) -> InlineKeyboardMarkup:
    """Actions for a specific campaign."""
    buttons = []
    
    if status in ['draft', 'paused']:
        buttons.append([
            InlineKeyboardButton("▶️ Запустить", callback_data=f"campaign_start_{campaign_id}"),
        ])
    
    if status == 'running':
        buttons.append([
            InlineKeyboardButton("⏸ Пауза", callback_data=f"campaign_pause_{campaign_id}"),
            InlineKeyboardButton("⏹ Стоп", callback_data=f"campaign_stop_{campaign_id}"),
        ])
    
    buttons.extend([
        [
            InlineKeyboardButton("📊 Детали", callback_data=f"campaign_detail_{campaign_id}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"campaign_delete_{campaign_id}"),
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="campaign_list")],
    ])
    
    return InlineKeyboardMarkup(buttons)


def build_confirm_keyboard(action: str, item_id: int = 0) -> InlineKeyboardMarkup:
    """Generic confirmation keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да", callback_data=f"confirm_{action}_{item_id}"),
            InlineKeyboardButton("❌ Нет", callback_data=f"cancel_{action}"),
        ],
    ])


def build_templates_menu() -> InlineKeyboardMarkup:
    """Templates management menu."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Все шаблоны", callback_data="templates_all"),
            InlineKeyboardButton("➕ Создать шаблон", callback_data="template_create"),
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_main")],
    ])


def build_back_button(callback_data: str = "back_main") -> InlineKeyboardMarkup:
    """Simple back button."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Назад", callback_data=callback_data)]
    ])
