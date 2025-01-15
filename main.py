import telebot
from telebot import types
import logging
from datetime import datetime, timedelta
import sqlite3
import html
import time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from telebot.apihelper import ApiException

# ==============================
# Настройка логирования
# ==============================
logging.basicConfig(
    level=logging.INFO,  # Можно изменить на DEBUG для более подробного логирования
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# ==============================
# Инициализация бота
# ==============================
API_TOKEN = '7895081980:AAFsNiy5hnNbsx18Ep4GJveEfn-WRwY2O3w'  # Замените на токен вашего бота
bot = telebot.TeleBot(API_TOKEN, parse_mode=None)  # parse_mode будет устанавливаться в каждом методе отдельно

# ==============================
# Подключение к базе данных
# ==============================
conn = sqlite3.connect('bot_database.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц, если они не существуют
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT,
        username TEXT,
        telegram_profile TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        creator_id INTEGER NOT NULL,
        participant_id INTEGER NOT NULL,
        description TEXT NOT NULL,
        event_datetime TEXT NOT NULL,
        FOREIGN KEY (creator_id) REFERENCES users(user_id),
        FOREIGN KEY (participant_id) REFERENCES users(user_id)
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS reminders (
        reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        reminder_time TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events(event_id)
    )
''')
conn.commit()

# ==============================
# Инициализация планировщика
# ==============================
scheduler = BackgroundScheduler(timezone="Europe/Moscow")
scheduler.start()
logging.info("Планировщик уведомлений запущен.")

# ==============================
# Хранение состояний пользователей
# ==============================
user_states = {}

# Определение различных состояний
STATE_MAIN_MENU = 'MAIN_MENU'
STATE_CREATE_EVENT_SELECT_USER = 'CREATE_EVENT_SELECT_USER'
STATE_CREATE_EVENT_DESCRIPTION = 'CREATE_EVENT_DESCRIPTION'
STATE_CREATE_EVENT_DATETIME = 'CREATE_EVENT_DATETIME'
STATE_ADD_CUSTOM_REMINDER = 'ADD_CUSTOM_REMINDER'
STATE_EDIT_EVENT_DESCRIPTION = 'EDIT_EVENT_DESCRIPTION'
STATE_EDIT_EVENT_DATETIME = 'EDIT_EVENT_DATETIME'


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


# ==============================
# Обработчики команд и сообщений
# ==============================

@bot.message_handler(commands=['start'])
def start(message):
    try:
        user_id = message.from_user.id
        first_name = escape_html_text(message.from_user.first_name)
        last_name = escape_html_text(message.from_user.last_name or "")
        username = escape_html_text(message.from_user.username or "No Username")
        telegram_profile = f"https://t.me/{username}" if message.from_user.username else "No Username"

        logging.debug(f"/start: user_id = {user_id}")

        # Проверка, зарегистрирован ли пользователь
        cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        if cursor.fetchone():
            # Отправляем главное меню
            bot.send_message(
                user_id,
                "✅ Вы уже зарегистрированы.",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML"
            )
            user_states[user_id] = {'state': STATE_MAIN_MENU}
            logging.info(f"Пользователь {user_id} уже зарегистрирован.")
            return

        # Регистрация пользователя
        cursor.execute(
            "INSERT INTO users (user_id, first_name, last_name, username, telegram_profile) VALUES (?, ?, ?, ?, ?)",
            (user_id, first_name, last_name, username, telegram_profile)
        )
        conn.commit()

        # Отправляем главное меню
        bot.send_message(
            user_id,
            f"👋 Привет, {first_name} {last_name}! Вы успешно зарегистрированы.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )
        user_states[user_id] = {'state': STATE_MAIN_MENU}
        logging.info(f"Пользователь {user_id} зарегистрирован.")
    except Exception as e:
        logging.error("Ошибка в /start: %s", e)
        try:
            bot.send_message(
                message.chat.id,
                "❌ Произошла ошибка при регистрации. Пожалуйста, попробуйте позже.",
                parse_mode="HTML"
            )
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")


@bot.callback_query_handler(func=lambda call: True)
def callback_query_handler(call):
    try:
        user_id = call.from_user.id
        data = call.data
        logging.debug(f"callback_query: user_id = {user_id}, data = {data}")

        user_state = user_states.get(user_id, {'state': STATE_MAIN_MENU})

        if data == "main_menu":
            # Отправляем главное меню
            bot.send_message(
                user_id,
                "🏠 Главное меню:",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML"
            )
            user_states[user_id]['state'] = STATE_MAIN_MENU
            return

        if data == "create_event":
            initiate_create_event(user_id, call.message)
        elif data.startswith("select_user_"):
            participant_id = int(data.split("_")[-1])
            # Переходим к вводу описания события
            user_states[user_id] = {
                'state': STATE_CREATE_EVENT_DESCRIPTION,
                'participant_id': participant_id
            }
            bot.send_message(
                user_id,
                "✍️ Введите описание события:",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
            bot.register_next_step_handler(call.message, get_event_description)
            logging.info(f"Пользователь {user_id} выбрал пользователя {participant_id} для события.")
        elif data == "list_users":
            list_users(user_id)
        elif data == "my_events":
            show_my_events(user_id)
        elif data.startswith("edit_event_"):
            event_id = int(data.split("_")[-1])
            initiate_edit_event(user_id, event_id, call.message)
        elif data.startswith("delete_event_"):
            event_id = int(data.split("_")[-1])
            initiate_delete_event(user_id, event_id, call.message)
        elif data.startswith("confirm_delete_event_"):
            event_id = int(data.split("_")[-1])
            confirm_delete_event(user_id, event_id)
        elif data == "cancel_delete_event":
            cancel_delete_event(user_id)
        elif data == "add_custom_reminder_yes":
            user_states[user_id] = {'state': STATE_ADD_CUSTOM_REMINDER}
            bot.send_message(
                user_id,
                "🕒 Введите количество минут до события, за которое вы хотите получить напоминание (1-60):",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
            bot.register_next_step_handler(call.message, get_custom_reminder_time)
            logging.info(f"Пользователь {user_id} выбрал добавить дополнительное напоминание.")
        elif data == "add_custom_reminder_no":
            bot.send_message(
                user_id,
                "✅ Ваше событие успешно создано. Главное меню.",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML"
            )
            user_states[user_id] = {'state': STATE_MAIN_MENU}
            logging.info(f"Пользователь {user_id} отказался от добавления дополнительного напоминания.")
        else:
            logging.warning(f"Неизвестный callback_data: {data}")
    except ApiException as api_e:
        logging.error("APIException в callback_query_handler: %s", api_e)
        try:
            bot.send_message(
                call.message.chat.id,
                "❌ Произошла ошибка при обработке действия.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
        except ApiException as api_e2:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e2}")
    except Exception as e:
        logging.error("Ошибка в callback_query_handler: %s", e)
        try:
            bot.send_message(
                call.message.chat.id,
                "❌ Произошла ошибка при обработке действия.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")


def initiate_create_event(user_id, message):
    """Инициирует процесс создания нового события."""
    try:
        # Получение списка пользователей для выбора участника
        cursor.execute("SELECT user_id, first_name, last_name, username FROM users WHERE user_id != ?", (user_id,))
        users = cursor.fetchall()
        if not users:
            bot.send_message(
                user_id,
                "❌ Нет доступных пользователей для выбора участника.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
            logging.info(f"Пользователь {user_id} попытался создать событие, но нет доступных участников.")
            return

        # Создание клавиатуры для выбора участника
        markup = types.InlineKeyboardMarkup(row_width=1)
        for user in users:
            uid, first, last, username = user
            if username != "No Username":
                display_username = f"@{escape_html_text(username)}"
            else:
                display_username = "No Username"
            user_display = f"{escape_html_text(first)} {escape_html_text(last)} ({display_username})"
            btn = types.InlineKeyboardButton(user_display, callback_data=f"select_user_{uid}")
            markup.add(btn)

        # Кнопка для возврата в главное меню
        markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

        bot.send_message(
            user_id,
            "📋 Выберите участника для события:",
            reply_markup=markup,
            parse_mode="HTML"
        )
        logging.info(f"Пользователь {user_id} инициировал создание нового события.")
    except Exception as e:
        logging.error(f"Ошибка в initiate_create_event для пользователя {user_id}: {e}")
        try:
            bot.send_message(
                user_id,
                "❌ Произошла ошибка при инициации создания события.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")


def list_users(user_id):
    """Отображает список всех зарегистрированных пользователей."""
    try:
        cursor.execute("SELECT user_id, first_name, last_name, username FROM users")
        users = cursor.fetchall()
        if not users:
            bot.send_message(
                user_id,
                "❌ Нет зарегистрированных пользователей.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
            logging.info(f"Пользователь {user_id} запросил список пользователей, но он пуст.")
            return

        user_list = ""
        for user in users:
            uid, first, last, username = user
            if username != "No Username":
                display_username = f"@{escape_html_text(username)}"
            else:
                display_username = "No Username"
            user_list += f"👤 {escape_html_text(first)} {escape_html_text(last)} ({display_username})\n"

        response = f"📋 <b>Список пользователей:</b>\n{user_list}"
        bot.send_message(
            user_id,
            response,
            reply_markup=back_to_main_menu_keyboard(),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logging.info(f"Пользователь {user_id} запросил список всех пользователей.")
    except Exception as e:
        logging.error(f"Ошибка в list_users для пользователя {user_id}: {e}")
        try:
            bot.send_message(
                user_id,
                "❌ Произошла ошибка при получении списка пользователей.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")


def show_my_events(user_id):
    """Отображает события, связанные с пользователем."""
    try:
        cursor.execute("""
            SELECT event_id, description, event_datetime, participant_id, creator_id
            FROM events
            WHERE creator_id=? OR participant_id=?
            ORDER BY event_datetime
        """, (user_id, user_id))
        events = cursor.fetchall()
        logging.info(f"Пользователь {user_id} имеет {len(events)} событий.")
        if not events:
            bot.send_message(
                user_id,
                "📭 У вас нет запланированных событий.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
            return

        response = "📅 <b>Ваши события:</b>\n\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        for event in events:
            event_id, description, event_datetime, participant_id, creator_id = event
            try:
                event_dt_obj = datetime.fromisoformat(event_datetime)
                event_dt = event_dt_obj.strftime('%d.%m.%Y %H:%M')
            except ValueError:
                logging.error(f"Некорректный формат event_datetime для события {event_id}: {event_datetime}")
                event_dt = event_datetime  # Используем исходную строку, если парсинг не удался

            # Получение информации о участнике
            cursor.execute("SELECT first_name, last_name, username FROM users WHERE user_id=?", (participant_id,))
            participant = cursor.fetchone()
            if participant:
                participant_first, participant_last, participant_username = participant
                if participant_username != "No Username":
                    participant_display = f"@{escape_html_text(participant_username)}"
                else:
                    participant_display = "No Username"
                participant_full = f"{escape_html_text(participant_first)} {escape_html_text(participant_last)} ({participant_display})"
            else:
                participant_full = "Unknown User"

            # Получение информации о создателе
            cursor.execute("SELECT first_name, last_name, username FROM users WHERE user_id=?", (creator_id,))
            creator = cursor.fetchone()
            if creator:
                creator_first, creator_last, creator_username = creator
                if creator_username != "No Username":
                    creator_display = f"@{escape_html_text(creator_username)}"
                else:
                    creator_display = "No Username"
                creator_full = f"{escape_html_text(creator_first)} {escape_html_text(creator_last)} ({creator_display})"
            else:
                creator_full = "Unknown User"

            if user_id == creator_id:
                # Добавление кнопок "Редактировать" и "Удалить" для создателя
                edit_btn = types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_event_{event_id}")
                delete_btn = types.InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_event_{event_id}")
                markup.add(edit_btn, delete_btn)
            response += (
                f"• <b>ID:</b> {event_id}\n"
                f"  <b>Описание:</b> {description}\n"
                f"  <b>Дата и время:</b> {event_dt}\n"
                f"  <b>Участник:</b> {participant_full}\n"
                f"  <b>Создатель:</b> {creator_full}\n\n"
            )

        # Добавление кнопки "Вернуться в главное меню"
        markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

        bot.send_message(
            user_id,
            response,
            reply_markup=markup,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logging.info(f"Отправлен список событий пользователю {user_id}.")
    except Exception as e:
        logging.error(f"Ошибка в show_my_events для пользователя {user_id}: {e}")
        try:
            bot.send_message(
                user_id,
                "❌ Произошла ошибка при просмотре событий.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")


def initiate_edit_event(user_id, event_id, message):
    """Инициирует процесс редактирования события."""
    try:
        # Проверка, является ли пользователь создателем события
        cursor.execute("SELECT creator_id FROM events WHERE event_id=?", (event_id,))
        result = cursor.fetchone()
        if not result:
            bot.send_message(
                user_id,
                "❌ Событие не найдено.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
            logging.warning(f"Пользователь {user_id} попытался редактировать несуществующее событие {event_id}.")
            return

        creator_id = result[0]
        if user_id != creator_id:
            bot.send_message(
                user_id,
                "❌ Вы не являетесь создателем этого события.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
            logging.warning(
                f"Пользователь {user_id} попытался редактировать событие {event_id}, которое создал пользователь {creator_id}.")
            return

        # Переходим к вводу нового описания
        user_states[user_id] = {
            'state': STATE_EDIT_EVENT_DESCRIPTION,
            'event_id': event_id
        }
        bot.send_message(
            user_id,
            "✍️ Введите новое описание события:",
            reply_markup=back_to_main_menu_keyboard(),
            parse_mode="HTML"
        )
        bot.register_next_step_handler(message, edit_event_description)
        logging.info(f"Пользователь {user_id} начал редактирование события {event_id}.")
    except Exception as e:
        logging.error(f"Ошибка в initiate_edit_event для пользователя {user_id}, события {event_id}: {e}")
        try:
            bot.send_message(
                user_id,
                "❌ Произошла ошибка при инициации редактирования события.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")


def initiate_delete_event(user_id, event_id, message):
    """Инициирует процесс удаления события."""
    try:
        # Проверка, является ли пользователь создателем события
        cursor.execute("SELECT creator_id, participant_id FROM events WHERE event_id=?", (event_id,))
        result = cursor.fetchone()
        if not result:
            bot.send_message(
                user_id,
                "❌ Событие не найдено.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
            logging.warning(f"Пользователь {user_id} попытался удалить несуществующее событие {event_id}.")
            return

        creator_id, participant_id = result
        if user_id != creator_id:
            bot.send_message(
                user_id,
                "❌ Вы не являетесь создателем этого события.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
            logging.warning(
                f"Пользователь {user_id} попытался удалить событие {event_id}, которое создал пользователь {creator_id}.")
            return

        # Подтверждение удаления события
        markup = types.InlineKeyboardMarkup(row_width=2)
        confirm_btn = types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_delete_event_{event_id}")
        cancel_btn = types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_delete_event")
        markup.add(confirm_btn, cancel_btn)
        new_text = f"🗑️ Вы уверены, что хотите удалить событие ID:{event_id}?"
        bot.send_message(
            user_id,
            new_text,
            reply_markup=markup,
            parse_mode="HTML"
        )
        logging.info(f"Пользователь {user_id} инициировал удаление события {event_id}.")
    except Exception as e:
        logging.error(f"Ошибка в initiate_delete_event для пользователя {user_id}, события {event_id}: {e}")
        try:
            bot.send_message(
                user_id,
                "❌ Произошла ошибка при инициации удаления события.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")


def confirm_delete_event(user_id, event_id):
    """Подтверждает удаление события."""
    try:
        # Проверка, является ли пользователь создателем события
        cursor.execute("SELECT creator_id, participant_id FROM events WHERE event_id=?", (event_id,))
        result = cursor.fetchone()
        if not result:
            bot.send_message(
                user_id,
                "❌ Событие не найдено или уже было удалено.",
                parse_mode="HTML"
            )
            logging.warning(f"Событие {event_id} не найдено при попытке удаления.")
            return

        creator_id, participant_id = result
        if user_id != creator_id:
            bot.send_message(
                user_id,
                "❌ Вы не являетесь создателем этого события.",
                parse_mode="HTML"
            )
            logging.warning(f"Пользователь {user_id} попытался удалить чужое событие {event_id}.")
            return

        # Удаление напоминаний из базы данных
        cursor.execute("DELETE FROM reminders WHERE event_id=?", (event_id,))
        conn.commit()

        # Удаление события из базы данных
        cursor.execute("DELETE FROM events WHERE event_id=?", (event_id,))
        conn.commit()
        logging.info(f"Событие {event_id} успешно удалено пользователем {user_id}.")

        # Отмена запланированных напоминаний в планировщике
        job_prefix = f"reminder_{event_id}_"
        jobs = scheduler.get_jobs()
        for job in jobs:
            if job.id.startswith(job_prefix):
                scheduler.remove_job(job.id)
                logging.info(f"Удалена запланированная задача {job.id} для события {event_id}.")

        # Отправка уведомлений обоим участникам о удалении события
        send_event_deleted_notifications(event_id, creator_id, participant_id)

        # Отправка подтверждения удаления события и главного меню
        bot.send_message(
            user_id,
            "✅ Событие успешно удалено. Главное меню.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )
        user_states[user_id] = {'state': STATE_MAIN_MENU}
        logging.info(f"Отправлено подтверждение удаления события пользователю {user_id}.")
    except Exception as e:
        logging.error(f"Ошибка в confirm_delete_event для пользователя {user_id}, события {event_id}: {e}")
        try:
            bot.send_message(
                user_id,
                "❌ Произошла ошибка при удалении события.",
                parse_mode="HTML"
            )
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")


def cancel_delete_event(user_id):
    """Отменяет процесс удаления события."""
    try:
        bot.send_message(
            user_id,
            "❌ Удаление события отменено. Главное меню.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )
        user_states[user_id] = {'state': STATE_MAIN_MENU}
        logging.info(f"Пользователь {user_id} отменил удаление события.")
    except Exception as e:
        logging.error(f"Ошибка в cancel_delete_event для пользователя {user_id}: {e}")
        try:
            bot.send_message(
                user_id,
                "❌ Произошла ошибка при отмене удаления события.",
                parse_mode="HTML"
            )
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")


def send_event_deleted_notifications(event_id, creator_id, participant_id):
    """Отправляет уведомления о том, что событие было удалено."""
    try:
        notification_text = f"🗑️ Событие ID:{event_id} было удалено его создателем."

        # Отправка уведомления участнику
        bot.send_message(
            participant_id,
            notification_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logging.info(f"Участнику {participant_id} отправлено уведомление об удалении события {event_id}.")

        # Отправка уведомления создателю
        bot.send_message(
            creator_id,
            notification_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logging.info(f"Создателю {creator_id} отправлено уведомление об удалении события {event_id}.")
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомлений об удалении события {event_id}: {e}")


# ==============================
# Обработчики для ввода данных пользователем
# ==============================

def get_event_description(message):
    """Получает описание события от пользователя."""
    user_id = message.from_user.id
    state = user_states.get(user_id, {})
    if state.get('state') != STATE_CREATE_EVENT_DESCRIPTION:
        try:
            bot.send_message(
                user_id,
                "❌ Некорректное состояние для ввода описания.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
        logging.warning(f"Пользователь {user_id} находится в неверном состоянии для ввода описания.")
        return

    description = escape_html_text(message.text.strip())
    if not description:
        try:
            msg = bot.send_message(
                user_id,
                "❌ Описание не может быть пустым. Пожалуйста, введите описание события:",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
            logging.warning(f"Пользователь {user_id} ввёл пустое описание события.")
            bot.register_next_step_handler(msg, get_event_description)
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
        return

    user_states[user_id]['description'] = description
    user_states[user_id]['state'] = STATE_CREATE_EVENT_DATETIME

    # Запрашиваем дату и время события
    try:
        bot.send_message(
            user_id,
            "🕒 Введите дату и время события в формате DD.MM.YYYY HH:MM:",
            reply_markup=back_to_main_menu_keyboard(),
            parse_mode="HTML"
        )
        bot.register_next_step_handler(message, get_event_datetime)
        logging.info(f"Пользователь {user_id} ввёл описание события: {description}")
    except ApiException as api_e:
        logging.error(f"Ошибка при отправке запроса на дату и время: {api_e}")


def get_event_datetime(message):
    """Получает дату и время события от пользователя."""
    user_id = message.from_user.id
    state = user_states.get(user_id, {})
    if state.get('state') != STATE_CREATE_EVENT_DATETIME:
        try:
            bot.send_message(
                user_id,
                "❌ Некорректное состояние для ввода даты и времени.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
        logging.warning(f"Пользователь {user_id} находится в неверном состоянии для ввода даты и времени.")
        return

    datetime_text = message.text.strip()
    try:
        event_datetime = datetime.strptime(datetime_text, "%d.%m.%Y %H:%M")
        if event_datetime < datetime.now():
            try:
                msg = bot.send_message(
                    user_id,
                    "❌ Введите дату и время начиная с сегодняшнего дня и текущего времени:",
                    reply_markup=back_to_main_menu_keyboard(),
                    parse_mode="HTML"
                )
                logging.warning(f"Пользователь {user_id} ввёл дату из прошлого: {datetime_text}")
                bot.register_next_step_handler(msg, get_event_datetime)
            except ApiException as api_e:
                logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
            return

        # Проверка на пересечение событий
        participant_id = state.get('participant_id')
        if not participant_id:
            logging.error(f"Нет participant_id для пользователя {user_id} при создании события.")
            try:
                bot.send_message(
                    user_id,
                    "❌ Произошла ошибка при создании события. Пожалуйста, попробуйте снова.",
                    reply_markup=back_to_main_menu_keyboard(),
                    parse_mode="HTML"
                )
            except ApiException as api_e:
                logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
            return

        cursor.execute("""
            SELECT * FROM events
            WHERE participant_id=? AND event_datetime=?
        """, (participant_id, event_datetime.isoformat()))
        if cursor.fetchone():
            try:
                msg = bot.send_message(
                    user_id,
                    "❌ Выбранное время занято. Пожалуйста, выберите другое время:",
                    reply_markup=back_to_main_menu_keyboard(),
                    parse_mode="HTML"
                )
                logging.info(
                    f"Пользователь {user_id} попытался создать пересекающееся событие на {event_datetime.isoformat()}.")
                bot.register_next_step_handler(msg, get_event_datetime)
            except ApiException as api_e:
                logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
            return

        # Получение описания события
        description = state.get('description', 'No Description')

        # Создание события в базе данных
        cursor.execute("""
            INSERT INTO events (creator_id, participant_id, description, event_datetime)
            VALUES (?, ?, ?, ?)
        """, (user_id, participant_id, description, event_datetime.isoformat()))
        conn.commit()
        event_id = cursor.lastrowid
        logging.info(
            f"Создано новое событие от пользователя {user_id}: ID={event_id}, Описание='{description}', Дата и время={event_datetime.isoformat()}, Участник={participant_id}")

        # Планирование стандартных уведомлений (24 часа и 2 часа)
        standard_reminders = [timedelta(days=1), timedelta(hours=2)]
        for delta in standard_reminders:
            reminder_time = event_datetime - delta
            if reminder_time > datetime.now():
                cursor.execute("""
                    INSERT INTO reminders (event_id, reminder_time)
                    VALUES (?, ?)
                """, (event_id, reminder_time.isoformat()))
                conn.commit()
        # Планирование уведомлений
        schedule_notifications(event_id)

        # Отправка уведомлений обоим участникам о создании события
        send_event_created_notifications(user_id, event_id)

        # Предложение добавить дополнительное напоминание
        user_states[user_id] = {'state': STATE_ADD_CUSTOM_REMINDER}
        bot.send_message(
            user_id,
            "🎯 Хотите добавить дополнительное напоминание за определённое количество минут до события?",
            reply_markup=types.InlineKeyboardMarkup(row_width=2).add(
                types.InlineKeyboardButton("Да", callback_data="add_custom_reminder_yes"),
                types.InlineKeyboardButton("Нет", callback_data="add_custom_reminder_no")
            ),
            parse_mode="HTML"
        )
        logging.info(f"Пользователь {user_id} создал событие {event_id} и предложил добавить напоминание.")

    except ValueError:
        try:
            msg = bot.send_message(
                user_id,
                "❌ Неверный формат даты и времени. Пожалуйста, введите в формате DD.MM.YYYY HH:MM:",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
            logging.warning(
                f"Пользователь {user_id} ввёл неверный формат даты и времени: {datetime_text}")
            bot.register_next_step_handler(msg, get_event_datetime)
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
    except Exception as e:
        logging.error(f"Ошибка в get_event_datetime для пользователя {user_id}: {e}")
        try:
            bot.send_message(
                user_id,
                "❌ Произошла ошибка при обработке даты и времени.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")


def send_event_created_notifications(creator_id, event_id):
    """Отправляет уведомления о создании события создателю и участнику."""
    try:
        # Получение информации о событии
        cursor.execute("""
            SELECT event_id, participant_id, description, event_datetime FROM events
            WHERE event_id=?
        """, (event_id,))
        event = cursor.fetchone()
        if not event:
            logging.error(f"Не удалось найти событие с ID {event_id}.")
            return

        event_id, participant_id, description, event_datetime_str = event
        event_datetime = datetime.fromisoformat(event_datetime_str).strftime('%d.%m.%Y %H:%M')

        # Получение информации о участнике
        cursor.execute("SELECT first_name, last_name, username FROM users WHERE user_id=?", (participant_id,))
        participant = cursor.fetchone()
        if participant:
            participant_first, participant_last, participant_username = participant
            if participant_username != "No Username":
                participant_display = f"@{escape_html_text(participant_username)}"
            else:
                participant_display = "No Username"
            participant_full = f"{escape_html_text(participant_first)} {escape_html_text(participant_last)} ({participant_display})"
        else:
            participant_full = "Unknown User"

        # Получение информации о создателе
        cursor.execute("SELECT first_name, last_name, username FROM users WHERE user_id=?", (creator_id,))
        creator = cursor.fetchone()
        if creator:
            creator_first, creator_last, creator_username = creator
            if creator_username != "No Username":
                creator_display = f"@{escape_html_text(creator_username)}"
            else:
                creator_display = "No Username"
            creator_full = f"{escape_html_text(creator_first)} {escape_html_text(creator_last)} ({creator_display})"
        else:
            creator_full = "Unknown User"

        # Сообщение для участника
        notification_message_participant = (
            f"📅 Новое событие создано:\n\n"
            f"<b>Описание:</b> {description}\n"
            f"<b>Дата и время:</b> {event_datetime}\n"
            f"<b>Создатель:</b> {creator_full}"
        )
        bot.send_message(
            participant_id,
            notification_message_participant,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logging.info(f"Участнику {participant_id} отправлено уведомление о создании события {event_id}.")

        # Сообщение для создателя
        notification_message_creator = (
            f"📅 Вы создали новое событие:\n\n"
            f"<b>Описание:</b> {description}\n"
            f"<b>Дата и время:</b> {event_datetime}\n"
            f"<b>Участник:</b> {participant_full}"
        )
        bot.send_message(
            creator_id,
            notification_message_creator,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logging.info(f"Создателю {creator_id} отправлено уведомление о создании события {event_id}.")
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомлений о создании события {event_id}: {e}")


def edit_event_description(message):
    """Редактирует описание события."""
    user_id = message.from_user.id
    state = user_states.get(user_id, {})
    if state.get('state') != STATE_EDIT_EVENT_DESCRIPTION:
        try:
            bot.send_message(
                user_id,
                "❌ Некорректное состояние для редактирования описания.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
        logging.warning(f"Пользователь {user_id} находится в неверном состоянии для редактирования описания.")
        return

    new_description = escape_html_text(message.text.strip())
    if not new_description:
        try:
            msg = bot.send_message(
                user_id,
                "❌ Описание не может быть пустым. Пожалуйста, введите новое описание события:",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
            logging.warning(f"Пользователь {user_id} ввёл пустое описание при редактировании события.")
            bot.register_next_step_handler(msg, edit_event_description)
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
        return

    user_states[user_id]['new_description'] = new_description
    user_states[user_id]['state'] = STATE_EDIT_EVENT_DATETIME

    # Запрашиваем новую дату и время события
    try:
        bot.send_message(
            user_id,
            "🕒 Введите новую дату и время события в формате DD.MM.YYYY HH:MM:",
            reply_markup=back_to_main_menu_keyboard(),
            parse_mode="HTML"
        )
        bot.register_next_step_handler(message, edit_event_datetime)
        logging.info(f"Пользователь {user_id} ввёл новое описание события: {new_description}")
    except ApiException as api_e:
        logging.error(f"Ошибка при отправке запроса на новую дату и время: {api_e}")


def edit_event_datetime(message):
    """Редактирует дату и время события."""
    user_id = message.from_user.id
    state = user_states.get(user_id, {})
    if state.get('state') != STATE_EDIT_EVENT_DATETIME:
        try:
            bot.send_message(
                user_id,
                "❌ Некорректное состояние для редактирования даты и времени.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
        logging.warning(f"Пользователь {user_id} находится в неверном состоянии для редактирования даты и времени.")
        return

    datetime_text = message.text.strip()
    try:
        new_event_datetime = datetime.strptime(datetime_text, "%d.%m.%Y %H:%M")
        if new_event_datetime < datetime.now():
            try:
                msg = bot.send_message(
                    user_id,
                    "❌ Введите дату и время начиная с сегодняшнего дня и текущего времени:",
                    reply_markup=back_to_main_menu_keyboard(),
                    parse_mode="HTML"
                )
                logging.warning(f"Пользователь {user_id} ввёл дату из прошлого при редактировании: {datetime_text}")
                bot.register_next_step_handler(msg, edit_event_datetime)
            except ApiException as api_e:
                logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
            return

        event_id = state.get('event_id')
        new_description = state.get('new_description')

        if not event_id:
            logging.error(f"Нет event_id для пользователя {user_id} при редактировании даты и времени.")
            try:
                bot.send_message(
                    user_id,
                    "❌ Произошла ошибка при редактировании события. Пожалуйста, попробуйте снова.",
                    reply_markup=back_to_main_menu_keyboard(),
                    parse_mode="HTML"
                )
            except ApiException as api_e:
                logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
            return

        # Проверка на пересечение событий
        cursor.execute("""
            SELECT * FROM events
            WHERE participant_id=(SELECT participant_id FROM events WHERE event_id=?)
            AND event_datetime=?
            AND event_id != ?
        """, (event_id, new_event_datetime.isoformat(), event_id))
        if cursor.fetchone():
            try:
                msg = bot.send_message(
                    user_id,
                    "❌ Выбранное время занято. Пожалуйста, выберите другое время:",
                    reply_markup=back_to_main_menu_keyboard(),
                    parse_mode="HTML"
                )
                logging.info(
                    f"Пользователь {user_id} попытался редактировать событие {event_id} на занятое время {new_event_datetime.isoformat()}.")
                bot.register_next_step_handler(msg, edit_event_datetime)
            except ApiException as api_e:
                logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
            return

        # Обновление события в базе данных
        cursor.execute("""
            UPDATE events
            SET description=?, event_datetime=?
            WHERE event_id=?
        """, (new_description, new_event_datetime.isoformat(), event_id))
        conn.commit()
        logging.info(
            f"Событие {event_id} обновлено: Описание='{new_description}', Дата и время='{new_event_datetime.isoformat()}'.")

        # Удаление старых напоминаний
        cursor.execute("DELETE FROM reminders WHERE event_id=?", (event_id,))
        conn.commit()

        # Планирование стандартных уведомлений (24 часа и 2 часа)
        standard_reminders = [timedelta(days=1), timedelta(hours=2)]
        for delta in standard_reminders:
            reminder_time = new_event_datetime - delta
            if reminder_time > datetime.now():
                cursor.execute("""
                    INSERT INTO reminders (event_id, reminder_time)
                    VALUES (?, ?)
                """, (event_id, reminder_time.isoformat()))
                conn.commit()
        # Планирование уведомлений
        schedule_notifications(event_id)

        # Очистка состояния
        user_states[user_id] = {'state': STATE_MAIN_MENU}

        # Отправка уведомлений обоим участникам об обновлении события
        send_event_updated_notifications(user_id, event_id)

        # Отправка подтверждения редактирования события и главного меню
        bot.send_message(
            user_id,
            "✅ Ваше событие успешно отредактировано. Главное меню.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )
        logging.info(f"Отправлено подтверждение редактирования события пользователю {user_id}.")
    except ValueError:
        try:
            msg = bot.send_message(
                user_id,
                "❌ Неверный формат даты и времени. Пожалуйста, введите в формате DD.MM.YYYY HH:MM:",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
            logging.warning(
                f"Пользователь {user_id} ввёл неверный формат даты и времени при редактировании: {datetime_text}")
            bot.register_next_step_handler(msg, edit_event_datetime)
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
    except Exception as e:
        logging.error(f"Ошибка в edit_event_datetime для пользователя {user_id}: {e}")
        try:
            bot.send_message(
                user_id,
                "❌ Произошла ошибка при редактировании даты и времени.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")


def send_event_updated_notifications(creator_id, event_id):
    """Отправляет уведомления об обновлении события создателю и участнику."""
    try:
        # Получение информации о событии
        cursor.execute("""
            SELECT event_id, participant_id, description, event_datetime FROM events
            WHERE event_id=?
        """, (event_id,))
        event = cursor.fetchone()
        if not event:
            logging.error(f"Не удалось найти событие с ID {event_id}.")
            return

        event_id, participant_id, description, event_datetime_str = event
        event_datetime = datetime.fromisoformat(event_datetime_str).strftime('%d.%m.%Y %H:%M')

        # Получение информации о участнике
        cursor.execute("SELECT first_name, last_name, username FROM users WHERE user_id=?", (participant_id,))
        participant = cursor.fetchone()
        if participant:
            participant_first, participant_last, participant_username = participant
            if participant_username != "No Username":
                participant_display = f"@{escape_html_text(participant_username)}"
            else:
                participant_display = "No Username"
            participant_full = f"{escape_html_text(participant_first)} {escape_html_text(participant_last)} ({participant_display})"
        else:
            participant_full = "Unknown User"

        # Получение информации о создателе
        cursor.execute("SELECT first_name, last_name, username FROM users WHERE user_id=?", (creator_id,))
        creator = cursor.fetchone()
        if creator:
            creator_first, creator_last, creator_username = creator
            if creator_username != "No Username":
                creator_display = f"@{escape_html_text(creator_username)}"
            else:
                creator_display = "No Username"
            creator_full = f"{escape_html_text(creator_first)} {escape_html_text(creator_last)} ({creator_display})"
        else:
            creator_full = "Unknown User"

        # Сообщение для участника
        notification_message_participant = (
            f"📅 Событие обновлено:\n\n"
            f"<b>Описание:</b> {description}\n"
            f"<b>Дата и время:</b> {event_datetime}\n"
            f"<b>Создатель:</b> {creator_full}"
        )
        bot.send_message(
            participant_id,
            notification_message_participant,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logging.info(f"Участнику {participant_id} отправлено уведомление об обновлении события {event_id}.")

        # Сообщение для создателя
        notification_message_creator = (
            f"📅 Вы обновили событие:\n\n"
            f"<b>Описание:</b> {description}\n"
            f"<b>Дата и время:</b> {event_datetime}\n"
            f"<b>Участник:</b> {participant_full}"
        )
        bot.send_message(
            creator_id,
            notification_message_creator,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logging.info(f"Создателю {creator_id} отправлено уведомление об обновлении события {event_id}.")
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомлений об обновлении события {event_id}: {e}")


def get_custom_reminder_time(message):
    """Получает время для дополнительного напоминания от пользователя."""
    user_id = message.from_user.id
    state = user_states.get(user_id, {})
    if state.get('state') != STATE_ADD_CUSTOM_REMINDER:
        try:
            bot.send_message(
                user_id,
                "❌ Некорректное состояние для добавления напоминания.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
        logging.warning(f"Пользователь {user_id} находится в неверном состоянии для добавления напоминания.")
        return

    minutes_text = message.text.strip()
    try:
        minutes = int(minutes_text)
        if not (1 <= minutes <= 60):
            raise ValueError("Минуты вне допустимого диапазона.")

        # Получение последнего созданного события
        cursor.execute("SELECT event_id, event_datetime FROM events WHERE creator_id=? ORDER BY event_id DESC LIMIT 1",
                       (user_id,))
        event = cursor.fetchone()
        if not event:
            try:
                bot.send_message(
                    user_id,
                    "❌ Не удалось найти созданное событие.",
                    reply_markup=back_to_main_menu_keyboard(),
                    parse_mode="HTML"
                )
            except ApiException as api_e:
                logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
            logging.error(f"Не удалось найти созданное событие для пользователя {user_id}.")
            return

        event_id, event_datetime_str = event
        event_datetime = datetime.fromisoformat(event_datetime_str)
        reminder_time = event_datetime - timedelta(minutes=minutes)

        if reminder_time < datetime.now():
            try:
                bot.send_message(
                    user_id,
                    "❌ Время напоминания уже прошло. Пожалуйста, выберите другое время.",
                    reply_markup=back_to_main_menu_keyboard(),
                    parse_mode="HTML"
                )
            except ApiException as api_e:
                logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
            logging.warning(f"Пользователь {user_id} попытался установить прошедшее напоминание.")
            return

        # Добавление напоминания в базу данных
        cursor.execute("""
            INSERT INTO reminders (event_id, reminder_time)
            VALUES (?, ?)
        """, (event_id, reminder_time.isoformat()))
        conn.commit()

        # Планирование напоминания
        schedule_notifications(event_id)

        # Подтверждение
        confirmation_text = (
            f"✅ Событие создано на {event_datetime.strftime('%d.%m.%Y %H:%M')}.\n"
            f"Напоминание установлено за {minutes} минут до события на {reminder_time.strftime('%d.%m.%Y %H:%M')}."
        )
        bot.send_message(
            user_id,
            confirmation_text,
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )
        # Очистка состояния
        user_states[user_id] = {'state': STATE_MAIN_MENU}
        logging.info(
            f"Пользователь {user_id} добавил дополнительное напоминание за {minutes} минут до события {event_id}.")
    except ValueError:
        try:
            msg = bot.send_message(
                user_id,
                "❌ Неверный ввод. Пожалуйста, введите целое число от 1 до 60:",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
            logging.warning(f"Пользователь {user_id} ввёл некорректное количество минут: {minutes_text}")
            bot.register_next_step_handler(msg, get_custom_reminder_time)
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")
    except Exception as e:
        logging.error(f"Ошибка в get_custom_reminder_time для пользователя {user_id}: {e}")
        try:
            bot.send_message(
                user_id,
                "❌ Произошла ошибка при добавлении напоминания.",
                reply_markup=back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
        except ApiException as api_e:
            logging.error(f"Ошибка при отправке сообщения об ошибке: {api_e}")


# ==============================
# Основной цикл запуска бота
# ==============================

if __name__ == "__main__":
    while True:
        try:
            logging.info("Бот запущен и начал polling.")
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logging.error(f"Polling failed: {e}")
            logging.info("Перезапуск бота через 5 секунд...")
            time.sleep(5)  # Пауза перед повторным запуском