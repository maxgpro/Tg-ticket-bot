import os
import json
import atexit
import asyncio
import logging
import aioschedule as schedule
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from datetime import datetime, UTC, timedelta
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

load_dotenv()  # Загрузка переменных из .env
# Чтение переменных
TOKEN = os.getenv("TOKEN")
REMINDER_INTERVAL = int(os.getenv("REMINDER_INTERVAL"))
REMINDER_CHAT_ID = os.getenv("REMINDER_CHAT_ID")
STATUS_CHAT_ID = os.getenv("STATUS_CHAT_ID")
BD_HOST = os.getenv("BD_HOST")

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
active_tickets = {}
scheduled_jobs = {}


def now_utc3() -> datetime:
    return datetime.now(UTC) + timedelta(hours=3)


# --- Сервисы ---------------------------------------------------------

# Загрузка заявок из файла
def load_tickets():
    global active_tickets
    try:
        with open(BD_HOST, "r") as file:
            active_tickets = json.load(file)
        logging.info(f" === APP_LOG: Loaded Tickets — successful: {active_tickets}")

    except FileNotFoundError:
        active_tickets = {}
        logging.info(" === APP_LOG: No tickets file found. Starting fresh.")


# Сохранение заявок в файл
def save_tickets():
    try:
        # Открываем файл в текстовом режиме записи
        with open(BD_HOST, "w", encoding="utf-8") as file:
            # Сериализуем данные в JSON и записываем
            json.dump(active_tickets, file, indent=4, ensure_ascii=False)
        logging.info(" === APP_LOG: Tickets saved successfully.")
    except Exception as e:
        logging.error(f" === APP_LOG: Error saving tickets: {e}")


# Загрузка задач для активных заявок
def load_scheduler_jobs():
    for ticket_number in active_tickets:
        logging.info(f" === APP_LOG: Scheduler Job for ticket {ticket_number} restored.")
        schedule_reminder(ticket_number)
        logging.info(f" === APP_LOG: Loaded Scheduler Jobs — successful")


# Создание напоминания в планировщике
def schedule_reminder(ticket_number):
    # Создаем задачу и сохраняем ее в словаре
    scheduled_jobs[ticket_number] = schedule.every(REMINDER_INTERVAL).seconds.do(
        lambda: asyncio.create_task(send_reminder(ticket_number))
    )
    logging.info(f" === APP_LOG: Scheduler Job for ticket \"{ticket_number}\" created.")


# Удаление напоминания из планировщика
def remove_reminder(ticket_number):
    job = scheduled_jobs.pop(ticket_number, None)
    if job:
        schedule.cancel_job(job)
        logging.info(f" === APP_LOG: Scheduler Job for ticket \"{ticket_number}\" removed.")
    else:
        logging.warning(f" === APP_LOG: Scheduler Job for ticket \"{ticket_number}\" not found.")


# Отправка напоминания
async def send_reminder(ticket_number: str):
    try:
        logging.info(f" === APP_LOG: send_reminder called for ticket {ticket_number}")
        ticket = active_tickets.get(ticket_number)
        if ticket:
            ticket["remind_times"] += 1
            start_time = datetime.strptime(ticket["start_time"], '%H:%M %d.%m.%Y')
            elapsed_time = datetime.now() - timedelta(hours=3) - start_time  # Разница во времени
            elapsed_minutes = elapsed_time.total_seconds() // 60  # Преобразование в минуты

            # Отправляем сообщение как ответ на исходное сообщение
            sent_message = await bot.send_message(
                chat_id=REMINDER_CHAT_ID,
                text=f"{ticket_number} прошло {int(elapsed_minutes)} мин."
            )

            # Сохраняем message_id отправленного сообщения
            ticket["notification_messages"].append(sent_message.message_id)

            # Сохраняем обновленную заявку
            active_tickets[ticket_number] = ticket
            save_tickets()

            logging.info(f" === APP_LOG: Reminder sent for ticket {ticket_number}")
    except Exception as e:
        logging.error(f" === APP_LOG: Error in send_reminder for ticket {ticket_number}: {e}")


def date_time_formatter(start_time: str) -> str:
    try:
        # Преобразование строки в объект datetime
        start_time_obj = datetime.strptime(start_time, '%H:%M %d.%m.%Y')
        # Форматирование с разделителем "—"
        formatted_start_time = start_time_obj.strftime('%H:%M — %d.%m.%Y')
        return formatted_start_time
    except Exception as e:
        logging.error(f" === APP_LOG: Error in date_time_formater: {e}")
        return start_time  # Возврат исходной строки, если произошла ошибка

# --- Команды бота ---------------------------------------------------------
@router.message()
async def handle_message(message: Message):
    # Проверяем, что сообщение пришло из группы или супергруппы
    if message.chat.type in ["group", "supergroup"]:
        logging.info(f" === APP_LOG: Message received from the group: {message.chat.title} | {message.text}")

        now = now_utc3().strftime('%H:%M %d.%m.%Y')
        chat_id = message.chat.id
        topic_id = message.message_thread_id

        # Проверка на наличие текста в сообщении
        if message.text:
            message_text = message.text.lower()
        else:
            logging.warning("Received a message without text.")
            return

        # Открыть заявку
        if message_text == "+":
            if message.reply_to_message is None:
                logging.warning("'+' command was used without reply")
                return

            ticket_number = message.reply_to_message.caption

            chat_id = message.reply_to_message.chat.id
            topic_id = message.reply_to_message.message_thread_id

            if ticket_number in active_tickets:
                logging.warning(f"Ticket {ticket_number} already exists.")
                await message.reply(f"Ticket {ticket_number} already exists.")
            else:
                # Отправляем сообщение в тему Статус
                opens_message_id = await bot.send_message(
                    chat_id=STATUS_CHAT_ID,
                    text=f"{ticket_number}\n📥 открыт в {date_time_formatter(now)}"
                )

                active_tickets[ticket_number] = {
                    "start_time": now,
                    "chat_id": chat_id,
                    "message_thread_id": topic_id,
                    "message_id": message.message_id,
                    "opens_message_id": opens_message_id.message_id,
                    "remind_times": 0,
                    "notification_messages": []
                }
                save_tickets()
                schedule_reminder(ticket_number)

            try:
                # Удаляем сообщение с +
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                logging.info(f" === APP_LOG: Message for ticket {ticket_number} deleted.")
            except Exception as e:
                logging.error(f"Failed to delete message for ticket {ticket_number}: {e}")

        elif message_text == "-":
            logging.info('deleting method was used')

            if message.reply_to_message is None:
                logging.warning("'-' command was used without reply")
                return

            ticket_number = message.reply_to_message.caption

            logging.info(
                f" === APP_LOG: {now_utc3().strftime('%H:%M %d.%m.%Y')}: topic_id={message.message_thread_id} Method=\"- \"")

            if ticket_number in active_tickets:
                ticket = active_tickets[ticket_number]

                try:
                    await bot.delete_message(chat_id=ticket["chat_id"], message_id=message.reply_to_message.message_id)
                    # Удаляем сообщение с -
                    await bot.delete_message(chat_id=ticket["chat_id"], message_id=message.message_id)
                    logging.info(f" === APP_LOG: Message for ticket {ticket_number} deleted.")
                except Exception as e:
                    logging.error(f" === APP_LOG: Failed to delete message for ticket {ticket_number}: {e}")

                # Отправляем сообщение о закрытии в тему Статус
                await bot.edit_message_text(
                    chat_id=STATUS_CHAT_ID,
                    message_id=ticket['opens_message_id'],
                    text=f"{ticket_number}\n📥 открыт в {date_time_formatter(ticket['start_time'])}\n✅ закрыт в {date_time_formatter(now)}",

                )

                remove_reminder(ticket_number)  # Удаляем задачу из планировщика
                try:
                    # Удаляем сообщение с -
                    await bot.delete_message(chat_id=ticket["chat_id"], message_id=ticket["message_id"])
                    logging.info(f" === APP_LOG: Message for ticket {ticket_number} deleted.")
                except Exception as e:
                    logging.error(f" === APP_LOG: Failed to delete message for ticket {ticket_number}: {e}")

                # Удаляем все сообщения-оповещения
                for msg_id in ticket.get("notification_messages", []):
                    try:
                        await bot.delete_message(chat_id=REMINDER_CHAT_ID, message_id=msg_id)
                        logging.info(f" === APP_LOG: Deleted notification message {msg_id} for ticket {ticket_number}")
                    except Exception as e:
                        logging.error(
                            f" === APP_LOG: Failed to delete notification message {msg_id} for ticket {ticket_number}: {e}")

                del active_tickets[ticket_number]  # Удаляем из списка активных заявок
                save_tickets()  # Сохраняем изменения
                try:
                    await bot.delete_message(chat_id=ticket["chat_id"], message_id=message.reply_to_message.message_id)
                except Exception as e:
                    logging.error(f" === APP_LOG: Failed to delete message for ticket {ticket_number}: {e}")
            else:
                await message.reply(f"{ticket_number} Не найден.")

        # Показать открытые заявки
        elif "list" in message.text.lower():
            formatted_tickets = json.dumps(active_tickets, indent=4, ensure_ascii=False)
            await bot.send_message(
                chat_id=message.chat.id,
                text=f"<pre>{formatted_tickets}</pre>",
                parse_mode="HTML",
                message_thread_id=message.message_thread_id
            )

        # Показать содержимое файла tickets.json
        elif "dump" in message.text.lower():
            try:
                with open(BD_HOST, "r", encoding="utf-8") as file:
                    file_content = json.load(file)

                formatted_content = json.dumps(file_content, indent=4, ensure_ascii=False)

                await bot.send_message(
                    chat_id=message.chat.id,
                    text=f"<pre>{formatted_content}</pre>",
                    parse_mode="HTML",
                    message_thread_id=message.message_thread_id
                )
            except FileNotFoundError:
                logging.error(" === APP_LOG: tickets.json file not found.")
            except json.JSONDecodeError as e:
                logging.error(f" === APP_LOG: Error decoding tickets.json: {e}")
            except Exception as e:
                logging.error(f" === APP_LOG: Unexpected error while reading tickets.json: {e}")

        # Помощь по командам
        elif "bot help" in message.text.lower():
            logging.info(f" === APP_LOG: {now_utc3().strftime('%H:%M %d.%m.%Y')}: Method \"bot help\" triggered")

            help_text = (
                "📋 **Доступные команды**:\n"
                "1. **Открыть заявку:**\n"
                "Напишите `+ `<номер заявки> чтобы создать новое оповещение.\n"
                "   _Пример: + 1234_\n\n"
                "2. **Закрыть заявку:**\n"
                "Напишите `- `<номер заявки> чтобы удалить оповещение.\n"
                "   _Пример: - 1234_\n\n"
                "3. **Показать открытые заявки:**\n"
                "   Напишите `list` для просмотра списка открытых оповещений.\n"
            )

            await message.reply(help_text, parse_mode="Markdown")

        # Вернуть ID топика
        elif "tid" in message_text:
            logging.info(f" === APP_LOG: thread_id = {message.message_thread_id}")


# --- Инициализация ---------------------------------------------------------

logging.info(f" === APP_LOG: Inited Router  — {dp.include_router(router)}")  # Регистрация маршрутизатора
load_tickets()  # Загрузка заявок из БД
load_scheduler_jobs()  # Загрузка задач планировщика из БД


# Основной цикл для выполнения задач планировщика
async def run_scheduler():
    while True:
        for job in schedule.jobs:
            if job.should_run:
                await asyncio.create_task(job.run())
        await asyncio.sleep(1)


# Основная функция запуска
async def main():
    asyncio.create_task(run_scheduler())
    await dp.start_polling(bot)


if __name__ == "__main__":
    atexit.register(save_tickets)
    asyncio.run(main())