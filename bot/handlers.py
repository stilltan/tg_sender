"""Bot handlers for Telegram Sender."""
from __future__ import annotations

import asyncio
import random
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import db
from bot.config import (
    BOT_TOKEN, SUPER_ADMIN_ID, ADMIN_GROUP_ID,
    STATE_IDLE, STATE_WAITING_MESSAGE, STATE_WAITING_DELAY,
    STATE_WAITING_CONTACT, STATE_IMPORTING,
    BOT_API_BASE_URL
)
from bot.keyboards import (
    build_main_menu, build_contacts_menu, build_contact_actions,
    build_contacts_list_keyboard, build_campaign_menu, build_campaign_actions,
    build_confirm_keyboard, build_templates_menu, build_back_button
)

# ============================================================
# START / HELP
# ============================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    
    # Add as admin if super admin
    if user.id == SUPER_ADMIN_ID:
        db.add_admin(user.id, user.username, user.first_name, is_super=True)
    elif not db.is_admin(user.id):
        await update.message.reply_text(
            "⛔️ У вас нет доступа к этому боту.\n"
            "Обратитесь к администратору.",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        f"Я бот для рассылки сообщений в Telegram.\n\n"
        f"📋 *Основные функции:*\n"
        f"• Управление контактами\n"
        f"• Создание шаблонов сообщений\n"
        f"• Запуск рассылок с задержками\n"
        f"• Отметка статуса контактов\n"
        f"• Статистика и аналитика\n\n"
        f"Выберите действие в меню ниже:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_main_menu()
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_text = """
📖 *Инструкция по использованию:*

*📋 Контакты:*
• Просматривайте список контактов
• Отмечайте статус: написали, не заинтересован, заблокировал
• Импортируйте из Google Sheets или CSV

*📤 Рассылка:*
• Создайте шаблон сообщения
• Выберите группу контактов
• Настройте задержку между сообщениями
• Запустите рассылку

*📊 Статистика:*
• Количество контактов по статусам
• Результаты рассылок
• Процент успешных отправок

*Команды:*
/start - Главное меню
/help - Эта справка
/stats - Быстрая статистика
/cancel - Отмена текущего действия
"""
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick statistics."""
    stats = db.get_statistics()
    
    text = f"""
📊 *Быстрая статистика:*

👥 Всего контактов: {stats['total_contacts']}
✅ Активных: {stats['active_contacts']}
📩 Написано: {stats['contacted']}
❌ Не заинтересованы: {stats['not_interested']}
🚫 Заблокировали: {stats['blocked']}

📤 Рассылок: {stats['total_campaigns']}
📨 Отправлено: {stats['total_sent']}
⚠️ Ошибок: {stats['total_failed']}
📈 Успешность: {stats['success_rate']}%
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ============================================================
# MAIN MENU HANDLERS
# ============================================================

async def handle_menu_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle main menu text buttons."""
    text = update.message.text
    
    if text == "📋 Контакты":
        await show_contacts_menu(update, context)
    elif text == "📤 Рассылка":
        await show_campaign_menu(update, context)
    elif text == "📊 Статистика":
        await cmd_stats(update, context)
    elif text == "📝 Шаблоны":
        await show_templates_menu(update, context)
    elif text == "⚙️ Настройки":
        await show_settings(update, context)
    elif text == "❓ Помощь":
        await cmd_help(update, context)


async def show_contacts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show contacts submenu."""
    await update.message.reply_text(
        "📋 *Управление контактами*\n\n"
        "Выберите действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_contacts_menu()
    )


async def show_campaign_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show campaign submenu."""
    await update.message.reply_text(
        "📤 *Управление рассылками*\n\n"
        "Выберите действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_campaign_menu()
    )


async def show_templates_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show templates submenu."""
    await update.message.reply_text(
        "📝 *Шаблоны сообщений*\n\n"
        "Выберите действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_templates_menu()
    )


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show settings."""
    admins = db.get_all_admins()
    admins_text = "\n".join([f"• @{a.get('username', 'N/A')} (ID: {a['telegram_id']})" for a in admins])
    
    await update.message.reply_text(
        f"⚙️ *Настройки*\n\n"
        f"*Администраторы:*\n{admins_text}\n\n"
        f"*Для добавления администратора:*\n"
        f"Отправьте его Telegram ID командой:\n"
        f"/add_admin <telegram_id>",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_back_button()
    )


# ============================================================
# CALLBACK HANDLERS
# ============================================================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard callbacks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    if not db.is_admin(user_id):
        await query.edit_message_text("⛔️ Нет доступа")
        return
    
    # Navigation
    if data == "back_main":
        await query.edit_message_text(
            "Главное меню. Выберите действие:",
            reply_markup=None
        )
        await query.message.reply_text(
            "Выберите действие:",
            reply_markup=build_main_menu()
        )
        return
    
    if data == "back_contacts":
        await query.edit_message_text(
            "📋 *Управление контактами*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_contacts_menu()
        )
        return
    
    # Contacts
    if data.startswith("contacts_"):
        await handle_contacts_callback(query, data, context)
    elif data.startswith("contact_"):
        await handle_contact_callback(query, data, context)
    elif data.startswith("mark_"):
        await handle_mark_callback(query, data, context)
    elif data.startswith("import_"):
        await handle_import_callback(query, data, context)
    
    # Campaigns
    elif data.startswith("campaign_"):
        await handle_campaign_callback(query, data, context)
    
    # Templates
    elif data.startswith("template"):
        await handle_template_callback(query, data, context)
    
    # Confirmations
    elif data.startswith("confirm_"):
        await handle_confirm_callback(query, data, context)
    elif data.startswith("cancel_"):
        await query.edit_message_text("❌ Действие отменено")


async def handle_contacts_callback(query, data: str, context) -> None:
    """Handle contacts list callbacks."""
    if data == "contacts_all":
        contacts = db.get_all_contacts()
        await show_contacts_list(query, contacts, "Все контакты")
    
    elif data == "contacts_active":
        contacts = db.get_all_contacts(status="active")
        await show_contacts_list(query, contacts, "Активные контакты")
    
    elif data == "contacts_contacted":
        contacts = db.get_all_contacts(status="contacted")
        await show_contacts_list(query, contacts, "Написанные контакты")
    
    elif data == "contacts_not_interested":
        contacts = db.get_all_contacts(status="not_interested")
        await show_contacts_list(query, contacts, "Не заинтересованные")
    
    elif data == "contacts_blocked":
        contacts = db.get_all_contacts(status="blocked")
        await show_contacts_list(query, contacts, "Заблокировавшие")
    
    elif data == "contacts_delete_all":
        await query.edit_message_text(
            "⚠️ Вы уверены, что хотите удалить ВСЕ контакты?",
            reply_markup=build_confirm_keyboard("delete_all_contacts")
        )
    
    elif data.startswith("contacts_page_"):
        page = int(data.split("_")[-1])
        contacts = context.user_data.get('current_contacts', [])
        title = context.user_data.get('current_contacts_title', 'Контакты')
        await show_contacts_list(query, contacts, title, page=page)


async def show_contacts_list(query, contacts: list, title: str, page: int = 0) -> None:
    """Show paginated contacts list."""
    # Store in context for pagination
    # Note: This is a simplified version - in production you'd use context.user_data
    
    status_counts = {
        'active': sum(1 for c in contacts if c['status'] == 'active'),
        'contacted': sum(1 for c in contacts if c['status'] == 'contacted'),
        'not_interested': sum(1 for c in contacts if c['status'] == 'not_interested'),
        'blocked': sum(1 for c in contacts if c['status'] == 'blocked'),
    }
    
    text = f"📋 *{title}*\n\n"
    text += f"Всего: {len(contacts)}\n"
    text += f"🟢 Активных: {status_counts['active']}\n"
    text += f"✅ Написано: {status_counts['contacted']}\n"
    text += f"❌ Не заинтересованы: {status_counts['not_interested']}\n"
    text += f"🚫 Заблокировали: {status_counts['blocked']}\n\n"
    text += "Выберите контакт для действий:"
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_contacts_list_keyboard(contacts, page)
    )


async def handle_contact_callback(query, data: str, context) -> None:
    """Handle single contact view."""
    if data == "contact_add":
        context.user_data['state'] = STATE_WAITING_CONTACT
        await query.edit_message_text(
            "➕ *Добавление контакта*\n\n"
            "Отправьте username (например: @username) или ссылку t.me/username\n\n"
            "Можно добавить несколько контактов, каждый с новой строки.\n"
            "Формат: @username или @username | Имя | Описание",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_back_button("back_contacts")
        )
        return
    
    contact_id = int(data.split("_")[-1])
    contact = db.get_contact(contact_id)
    
    if not contact:
        await query.edit_message_text("❌ Контакт не найден")
        return
    
    status_emoji = {
        'active': '🟢',
        'contacted': '✅',
        'not_interested': '❌',
        'blocked': '🚫',
    }.get(contact['status'], '⚪')
    
    text = f"""
👤 *Информация о контакте*

{status_emoji} *Статус:* {contact['status']}
*Username:* @{contact['username']}
*Имя:* {contact.get('name', 'Не указано')}
*Группа:* {contact.get('group_name', 'default')}
*Описание:* {contact.get('description', 'Нет описания')}
*Последний контакт:* {contact.get('last_contacted', 'Нет')}
*Добавлен:* {contact.get('created_at', 'Неизвестно')}
"""
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_contact_actions(contact_id)
    )


async def handle_mark_callback(query, data: str, context) -> None:
    """Handle contact status marking."""
    parts = data.split("_")
    status = parts[1]
    contact_id = int(parts[2])
    
    status_map = {
        'contacted': 'contacted',
        'not': 'not_interested',
        'blocked': 'blocked',
        'active': 'active',
    }
    
    # Handle "not_interested" case
    if status == 'not' and len(parts) > 2 and parts[2] == 'interested':
        status = 'not_interested'
        contact_id = int(parts[3])
    
    db_status = status_map.get(status, status)
    db.mark_contact(contact_id, db_status)
    
    contact = db.get_contact(contact_id)
    
    await query.answer(f"✅ Статус обновлён: {db_status}")
    
    # Refresh contact view
    status_emoji = {
        'active': '🟢',
        'contacted': '✅',
        'not_interested': '❌',
        'blocked': '🚫',
    }.get(db_status, '⚪')
    
    text = f"""
👤 *Информация о контакте*

{status_emoji} *Статус:* {db_status}
*Username:* @{contact['username']}
*Имя:* {contact.get('name', 'Не указано')}
*Группа:* {contact.get('group_name', 'default')}
*Последний контакт:* {db_status} - сейчас
"""
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_contact_actions(contact_id)
    )


async def handle_import_callback(query, data: str, context) -> None:
    """Handle import callbacks."""
    if data == "import_gsheets":
        context.user_data['state'] = STATE_IMPORTING
        context.user_data['import_type'] = 'gsheets'
        await query.edit_message_text(
            "📥 *Импорт из Google Sheets*\n\n"
            "Отправьте ссылку на Google Таблицу.\n\n"
            "Таблица должна содержать столбцы:\n"
            "• SSYLKA или username - ссылка/username\n"
            "• NAME - имя\n"
            "• OPISANIYE - описание\n\n"
            "Или просто список ссылок t.me/...",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_back_button("back_contacts")
        )
    
    elif data == "import_csv":
        context.user_data['state'] = STATE_IMPORTING
        context.user_data['import_type'] = 'csv'
        await query.edit_message_text(
            "📥 *Импорт из CSV*\n\n"
            "Отправьте CSV файл с контактами.\n\n"
            "Формат CSV:\n"
            "username,name,description\n"
            "user1,Имя 1,Описание 1\n"
            "user2,Имя 2,Описание 2",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_back_button("back_contacts")
        )


async def handle_campaign_callback(query, data: str, context) -> None:
    """Handle campaign callbacks."""
    if data == "campaign_new":
        context.user_data['state'] = STATE_WAITING_MESSAGE
        context.user_data['campaign_step'] = 'name'
        await query.edit_message_text(
            "📤 *Создание новой рассылки*\n\n"
            "Шаг 1/4: Введите название рассылки:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_back_button()
        )
    
    elif data == "campaign_list":
        campaigns = db.get_all_campaigns()
        if not campaigns:
            await query.edit_message_text(
                "📋 У вас пока нет рассылок.\n"
                "Создайте первую рассылку!",
                reply_markup=build_campaign_menu()
            )
            return
        
        buttons = []
        for c in campaigns[:10]:
            status_emoji = {
                'draft': '📝',
                'running': '▶️',
                'paused': '⏸',
                'completed': '✅',
                'failed': '❌',
            }.get(c['status'], '⚪')
            
            buttons.append([
                InlineKeyboardButton(
                    f"{status_emoji} {c['name'][:30]}",
                    callback_data=f"campaign_view_{c['id']}"
                )
            ])
        
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back_main")])
        
        await query.edit_message_text(
            "📋 *Мои рассылки:*\n\nВыберите рассылку:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    elif data.startswith("campaign_view_"):
        campaign_id = int(data.split("_")[-1])
        campaign = db.get_campaign(campaign_id)
        
        if not campaign:
            await query.edit_message_text("❌ Рассылка не найдена")
            return
        
        status_emoji = {
            'draft': '📝',
            'running': '▶️',
            'paused': '⏸',
            'completed': '✅',
            'failed': '❌',
        }.get(campaign['status'], '⚪')
        
        text = f"""
📤 *Рассылка: {campaign['name']}*

{status_emoji} *Статус:* {campaign['status']}
*Сообщение:* {campaign['message_text'][:100]}...
*Группа:* {campaign.get('contact_group', 'all')}
*Задержка:* {campaign['delay_min']}-{campaign['delay_max']} сек

📊 *Прогресс:*
Всего: {campaign['total_contacts']}
Отправлено: {campaign['sent_count']}
Ошибок: {campaign['failed_count']}
"""
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_campaign_actions(campaign_id, campaign['status'])
        )
    
    elif data.startswith("campaign_start_"):
        campaign_id = int(data.split("_")[-1])
        db.update_campaign(campaign_id, status='running')
        await query.answer("▶️ Рассылка запущена!")
        # Here you would start the actual sending process
        await query.edit_message_text(
            "▶️ Рассылка запущена!\n\n"
            "Бот начал отправку сообщений.\n"
            "Используйте /stats для проверки прогресса.",
            reply_markup=build_back_button()
        )
    
    elif data.startswith("campaign_pause_"):
        campaign_id = int(data.split("_")[-1])
        db.update_campaign(campaign_id, status='paused')
        await query.answer("⏸ Рассылка приостановлена")
        await query.edit_message_text(
            "⏸ Рассылка приостановлена.",
            reply_markup=build_back_button()
        )
    
    elif data.startswith("campaign_delete_"):
        campaign_id = int(data.split("_")[-1])
        await query.edit_message_text(
            "⚠️ Вы уверены, что хотите удалить эту рассылку?",
            reply_markup=build_confirm_keyboard("delete_campaign", campaign_id)
        )


async def handle_template_callback(query, data: str, context) -> None:
    """Handle template callbacks."""
    if data == "templates_all":
        templates = db.get_all_templates()
        if not templates:
            await query.edit_message_text(
                "📝 У вас пока нет шаблонов.\n"
                "Создайте первый шаблон!",
                reply_markup=build_templates_menu()
            )
            return
        
        buttons = []
        for t in templates:
            buttons.append([
                InlineKeyboardButton(
                    f"📝 {t['name'][:30]}",
                    callback_data=f"template_view_{t['id']}"
                )
            ])
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back_main")])
        
        await query.edit_message_text(
            "📝 *Шаблоны сообщений:*\n\nВыберите шаблон:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    elif data == "template_create":
        context.user_data['state'] = STATE_WAITING_MESSAGE
        context.user_data['template_step'] = 'name'
        await query.edit_message_text(
            "📝 *Создание шаблона*\n\n"
            "Введите название шаблона:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_back_button()
        )
    
    elif data.startswith("template_view_"):
        template_id = int(data.split("_")[-1])
        template = db.get_template(template_id)
        
        if not template:
            await query.edit_message_text("❌ Шаблон не найден")
            return
        
        text = f"""
📝 *Шаблон: {template['name']}*

*Текст:*
{template['text']}

*Создан:* {template.get('created_at', 'Неизвестно')}
"""
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"template_edit_{template_id}"),
                InlineKeyboardButton("🗑 Удалить", callback_data=f"template_delete_{template_id}"),
            ],
            [InlineKeyboardButton("◀️ Назад", callback_data="templates_all")],
        ])
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=buttons
        )


async def handle_confirm_callback(query, data: str, context) -> None:
    """Handle confirmation callbacks."""
    parts = data.split("_")
    action = parts[1]
    
    if action == "delete" and parts[2] == "all" and parts[3] == "contacts":
        db.delete_all_contacts()
        await query.edit_message_text("✅ Все контакты удалены!")
    
    elif action == "delete" and parts[2] == "campaign":
        campaign_id = int(parts[3])
        db.delete_campaign(campaign_id)
        await query.edit_message_text("✅ Рассылка удалена!")
    
    elif action == "delete" and parts[2] == "template":
        template_id = int(parts[3])
        db.delete_template(template_id)
        await query.edit_message_text("✅ Шаблон удалён!")


# ============================================================
# MESSAGE HANDLERS (for states)
# ============================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages based on state."""
    state = context.user_data.get('state', STATE_IDLE)
    text = update.message.text
    
    if state == STATE_WAITING_CONTACT:
        await handle_new_contact(update, context, text)
    elif state == STATE_WAITING_MESSAGE:
        await handle_campaign_or_template_message(update, context, text)
    elif state == STATE_IMPORTING:
        await handle_import_message(update, context, text)
    else:
        await handle_menu_text(update, context)


async def handle_new_contact(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Handle new contact input."""
    lines = text.strip().split('\n')
    added = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        parts = [p.strip() for p in line.split('|')]
        username = parts[0]
        
        # Clean username
        if username.startswith('@'):
            username = username[1:]
        if 't.me/' in username:
            username = username.split('t.me/')[-1]
        
        name = parts[1] if len(parts) > 1 else None
        description = parts[2] if len(parts) > 2 else None
        
        db.add_contact(username, name, description)
        added += 1
    
    context.user_data['state'] = STATE_IDLE
    
    await update.message.reply_text(
        f"✅ Добавлено контактов: {added}",
        reply_markup=build_contacts_menu()
    )


async def handle_campaign_or_template_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Handle campaign/template creation messages."""
    if 'campaign_step' in context.user_data:
        step = context.user_data['campaign_step']
        
        if step == 'name':
            context.user_data['campaign_name'] = text
            context.user_data['campaign_step'] = 'message'
            await update.message.reply_text(
                "Шаг 2/4: Введите текст сообщения для рассылки:"
            )
        
        elif step == 'message':
            context.user_data['campaign_message'] = text
            context.user_data['campaign_step'] = 'group'
            
            groups = db.get_contact_groups()
            groups_text = ', '.join(groups) if groups else 'default'
            
            await update.message.reply_text(
                f"Шаг 3/4: Выберите группу контактов:\n\n"
                f"Доступные группы: {groups_text}\n\n"
                f"Введите название группы или 'all' для всех:"
            )
        
        elif step == 'group':
            context.user_data['campaign_group'] = text
            context.user_data['campaign_step'] = 'delay'
            await update.message.reply_text(
                "Шаг 4/4: Введите задержку между сообщениями (в секундах):\n\n"
                "Формат: мин-макс (например: 30-60)"
            )
        
        elif step == 'delay':
            try:
                if '-' in text:
                    delay_min, delay_max = map(int, text.split('-'))
                else:
                    delay_min = delay_max = int(text)
                
                campaign_id = db.create_campaign(
                    name=context.user_data['campaign_name'],
                    message_text=context.user_data['campaign_message'],
                    contact_group=context.user_data.get('campaign_group', 'all'),
                    delay_min=delay_min,
                    delay_max=delay_max
                )
                
                context.user_data['state'] = STATE_IDLE
                del context.user_data['campaign_step']
                
                await update.message.reply_text(
                    f"✅ Рассылка создана!\n\n"
                    f"Название: {context.user_data['campaign_name']}\n"
                    f"Задержка: {delay_min}-{delay_max} сек\n\n"
                    f"Запустите рассылку из меню 'Мои рассылки'.",
                    reply_markup=build_main_menu()
                )
            except ValueError:
                await update.message.reply_text(
                    "❌ Неверный формат. Введите: мин-макс (например: 30-60)"
                )
    
    elif 'template_step' in context.user_data:
        step = context.user_data['template_step']
        
        if step == 'name':
            context.user_data['template_name'] = text
            context.user_data['template_step'] = 'text'
            await update.message.reply_text(
                "Введите текст шаблона сообщения:"
            )
        
        elif step == 'text':
            db.add_template(
                name=context.user_data['template_name'],
                text=text
            )
            
            context.user_data['state'] = STATE_IDLE
            del context.user_data['template_step']
            
            await update.message.reply_text(
                "✅ Шаблон создан!",
                reply_markup=build_main_menu()
            )


async def handle_import_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Handle import messages."""
    import_type = context.user_data.get('import_type')
    
    if import_type == 'gsheets':
        # Parse Google Sheets URL or direct links
        if 'docs.google.com/spreadsheets' in text:
            # Extract sheet ID and fetch data
            await update.message.reply_text(
                "⏳ Загружаю данные из Google Sheets...\n\n"
                "Для работы с Google Sheets необходимо настроить API ключи.\n"
                "Пока что отправьте контакты вручную, каждый с новой строки.\n"
                "Формат: @username или t.me/username"
            )
        else:
            # Parse as list of usernames
            contacts = []
            for line in text.strip().split('\n'):
                line = line.strip()
                if line:
                    contacts.append({'username': line})
            
            count = db.import_contacts_from_list(contacts)
            context.user_data['state'] = STATE_IDLE
            
            await update.message.reply_text(
                f"✅ Импортировано контактов: {count}",
                reply_markup=build_contacts_menu()
            )
    
    elif import_type == 'csv':
        # Handle CSV would be done via document upload
        await update.message.reply_text(
            "📥 Пожалуйста, отправьте CSV файл как документ."
        )


# ============================================================
# DOCUMENT HANDLER
# ============================================================

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle document uploads (CSV)."""
    if context.user_data.get('import_type') != 'csv':
        return
    
    document = update.message.document
    
    if not document.file_name.endswith('.csv'):
        await update.message.reply_text("❌ Пожалуйста, отправьте CSV файл.")
        return
    
    try:
        file = await context.bot.get_file(document.file_id)
        file_path = f"/tmp/{document.file_name}"
        await file.download_to_drive(file_path)
        
        import pandas as pd
        df = pd.read_csv(file_path)
        
        contacts = []
        for _, row in df.iterrows():
            contacts.append({
                'username': str(row.get('username', row.get('SSYLKA', ''))),
                'name': str(row.get('name', row.get('NAME', ''))),
                'description': str(row.get('description', row.get('OPISANIYE', '')))
            })
        
        count = db.import_contacts_from_list(contacts)
        context.user_data['state'] = STATE_IDLE
        
        await update.message.reply_text(
            f"✅ Импортировано из CSV: {count} контактов",
            reply_markup=build_contacts_menu()
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка импорта: {str(e)}")


# ============================================================
# ADMIN COMMANDS
# ============================================================

async def cmd_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add admin by ID."""
    user = update.effective_user
    
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("⛔️ Только суперадмин может добавлять администраторов.")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /add_admin <telegram_id>")
        return
    
    try:
        new_admin_id = int(context.args[0])
        db.add_admin(new_admin_id)
        await update.message.reply_text(f"✅ Администратор добавлен: {new_admin_id}")
    except ValueError:
        await update.message.reply_text("❌ Неверный ID. Используйте числовой ID.")


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel current operation."""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Действие отменено.",
        reply_markup=build_main_menu()
    )
    return ConversationHandler.END


# ============================================================
# APPLICATION SETUP
# ============================================================

def create_application() -> Application:
    """Create and configure the bot application."""
    import os
    
    # Initialize database
    db.init_db()
    
    # Add super admin
    if SUPER_ADMIN_ID:
        db.add_admin(SUPER_ADMIN_ID, is_super=True)
    
    # Create application with proxy support
    builder = Application.builder().token(BOT_TOKEN)
    
    # Telegram API proxy (for blocked regions like Russia)
    api_base = BOT_API_BASE_URL
    if api_base:
        if not api_base.endswith("/bot"):
            api_base = api_base.rstrip("/") + "/bot"
        file_base = os.environ.get("BOT_API_FILE_BASE_URL", "").strip().rstrip("/")
        if not file_base:
            file_base = api_base[:-len("/bot")] + "/file/bot"
        builder = builder.base_url(api_base).base_file_url(file_base)
    
    application = builder.build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("add_admin", cmd_add_admin))
    application.add_handler(CommandHandler("cancel", cmd_cancel))
    
    # Callback handler
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Document handler
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    # Message handler (must be last)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    return application
