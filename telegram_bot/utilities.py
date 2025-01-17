import html
from app import *
from datetime import datetime, timedelta
from apscheduler.triggers.date import DateTrigger
from telebot.apihelper import ApiException
# ==============================
# Функции-утилиты
# ==============================

def escape_html_text(text):
    """Экранирует специальные символы HTML."""
    return html.escape(text)


def schedule_notifications(event_id):
    """Планирует все напоминания для события."""
    cursor.execute("SELECT creator_id, participant_id, description, event_datetime FROM events WHERE event_id=?",
                   (event_id,))
    event = cursor.fetchone()
    if not event:
        logging.error(f"Событие с ID {event_id} не найдено.")
        return
    creator_id, participant_id, description, event_datetime_str = event
    event_datetime = datetime.fromisoformat(event_datetime_str)

    # Получение всех напоминаний для события
    cursor.execute("SELECT reminder_time FROM reminders WHERE event_id=?", (event_id,))
    reminders = cursor.fetchall()

    for reminder in reminders:
        reminder_time_str = reminder[0]
        reminder_time = datetime.fromisoformat(reminder_time_str)
        if reminder_time > datetime.now():
            job_id = f"reminder_{event_id}_{reminder_time.timestamp()}"
            if not scheduler.get_job(job_id):
                scheduler.add_job(
                    send_reminder,
                    trigger=DateTrigger(run_date=reminder_time),
                    args=[creator_id, participant_id, description, event_id, event_datetime_str],
                    id=job_id,
                    replace_existing=True
                )
                logging.info(f"Запланировано напоминание для события {event_id} на {reminder_time.isoformat()}.")


def send_reminder(creator_id, participant_id, description, event_id, event_datetime_str):
    """Отправляет напоминание о событии."""
    try:
        # Получение информации о пользователях
        cursor.execute("SELECT username FROM users WHERE user_id=?", (creator_id,))
        creator = cursor.fetchone()
        creator_username = f"@{escape_html_text(creator[0])}" if creator and creator[
            0] != "No Username" else "No Username"

        cursor.execute("SELECT username FROM users WHERE user_id=?", (participant_id,))
        participant = cursor.fetchone()
        participant_username = f"@{escape_html_text(participant[0])}" if participant and participant[
            0] != "No Username" else "No Username"

        # Формирование сообщения с никнеймами
        reminder_text = (
            f"⏰ Напоминание о событии:\n\n"
            f"<b>Описание:</b> {escape_html_text(description)}\n"
            f"<b>Дата и время:</b> {datetime.fromisoformat(event_datetime_str).strftime('%d.%m.%Y %H:%M')}\n"
            f"<b>Создатель:</b> {creator_username}\n"
            f"<b>Участник:</b> {participant_username}"
        )
        # Отправка напоминания создателю
        bot.send_message(
            creator_id,
            reminder_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logging.info(f"Отправлено напоминание создателю {creator_id} о событии {event_id}.")

        # Отправка напоминания участнику
        bot.send_message(
            participant_id,
            reminder_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logging.info(f"Отправлено напоминание участнику {participant_id} о событии {event_id}.")
    except Exception as e:
        logging.error(f"Ошибка при отправке напоминания для события {event_id}: {e}")


def main_menu_keyboard():
    """Создаёт главное меню с inline-кнопками."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    my_events_btn = types.InlineKeyboardButton("📅 Мои события", callback_data="my_events")
    create_event_btn = types.InlineKeyboardButton("➕ Создать новое событие", callback_data="create_event")
    list_users_btn = types.InlineKeyboardButton("👥 Просмотреть пользователей", callback_data="list_users")
    markup.add(my_events_btn, create_event_btn, list_users_btn)
    return markup


def back_to_main_menu_keyboard():
    """Создаёт кнопку для возврата в главное меню."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    main_menu_btn = types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    markup.add(main_menu_btn)
    return markup





