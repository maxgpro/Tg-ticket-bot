import logging
import json
import atexit
import asyncio
import aioschedule as schedule
from config.config import TOKEN, REMINDER_INTERVAL, REMINDER_TOPIC_ID, STATUS_TOPIC_ID
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message


logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
active_tickets = {}
scheduled_jobs = {}

# --- Сервисы ---------------------------------------------------------

# Загрузка заявок из файла
def load_tickets():
    global active_tickets
    try:
        with open("tickets.json", "r") as file:
            active_tickets = json.load(file)
        logging.info("Tickets loaded successfully.")
    except FileNotFoundError:
        active_tickets = {}
        logging.info("No tickets file found. Starting fresh.")

# Сохранение заявок в файл
def save_tickets():
    try:
        with open("tickets.json", "w") as file:
            json.dump(active_tickets, file, indent=4, ensure_ascii=False)
        logging.info("Tickets saved successfully.")
    except Exception as e:
        logging.error(f"Error saving tickets: {e}")

# Загрузка задач для активных заявок
def load_scheduler_jobs():
    for ticket_number in active_tickets:
        schedule_reminder(ticket_number)
        logging.info(f"Task for ticket {ticket_number} restored.")

# Создание напоминания в планировщике
def schedule_reminder(ticket_number):
    # Создаем задачу и сохраняем ее в словаре
    job = schedule.every(REMINDER_INTERVAL).seconds.do(
        lambda: asyncio.create_task(send_reminder(ticket_number))
    )
    scheduled_jobs[ticket_number] = job
    logging.info(f"Reminder scheduled for ticket {ticket_number}.")

# Удаление напоминания из планировщика
def remove_reminder(ticket_number):
    job = scheduled_jobs.pop(ticket_number, None)
    if job:
        schedule.cancel_job(job)
        logging.info(f"Reminder for ticket {ticket_number} removed.")
    else:
        logging.warning(f"No reminder found for ticket {ticket_number}.")

# Отправка напоминания
async def send_reminder(ticket_number: str):
    try:
        logging.info(f"send_reminder called for ticket {ticket_number}")
        ticket = active_tickets.get(ticket_number)
        if ticket:
            ticket["remind_times"] += 1
            start_time = datetime.strptime(ticket["start_time"], '%H:%M %d.%m.%Y')
            elapsed_time = datetime.now() - start_time  # Разница во времени
            elapsed_minutes = elapsed_time.total_seconds() // 60  # Преобразование в минуты

            # Отправляем сообщение как ответ на исходное сообщение
            sent_message = await bot.send_message(
                chat_id = ticket["chat_id"],
                text = f"{ticket_number} прошло {int(elapsed_minutes)} мин.",
                message_thread_id = REMINDER_TOPIC_ID
            )

            # Сохраняем message_id отправленного сообщения
            ticket["notification_messages"].append(sent_message.message_id)

            # Сохраняем обновленную заявку
            active_tickets[ticket_number] = ticket
            save_tickets()

            logging.info(f"Reminder sent for ticket {ticket_number}")
    except Exception as e:
        logging.error(f"Error in send_reminder for ticket {ticket_number}: {e}")


def date_time_formatter(start_time: str) -> str:
    try:
        # Преобразование строки в объект datetime
        start_time_obj = datetime.strptime(start_time, '%H:%M %d.%m.%Y')
        # Форматирование с разделителем "—"
        formatted_start_time = start_time_obj.strftime('%H:%M — %d.%m.%Y')
        return formatted_start_time
    except Exception as e:
        logging.error(f"Error in date_time_formater: {e}")
        return start_time  # Возврат исходной строки, если произошла ошибка


# --- Команды бота ---------------------------------------------------------

@router.message()
async def handle_message(message: Message):
    # Проверяем, что сообщение пришло из группы или супергруппы
    if message.chat.type in ["group", "supergroup"]:
        logging.info(f"Message received from the group: {message.chat.title} | {message.text}")

        now = datetime.now().strftime('%H:%M %d.%m.%Y')
        chat_id = message.chat.id
        topic_id = message.message_thread_id

        # Проверка на наличие текста в сообщении
        if message.text:
            message_text = message.text.lower()
        else:
            logging.warning("Received a message without text.")
            return


        # Открыть заявку
        if "+ " in message_text:
            logging.info(f" === APP_LOG: {datetime.now().strftime('%H:%M %d.%m.%Y')}: topic_id={message.message_thread_id} Method=\"+ \"")

            # Извлекаем номер заявки
            try:
                ticket_number = message_text.split("+ ")[1].split()[0]
            except IndexError as e:
                logging.error(f"Failed to extract ticket number: {e}")
                await message.reply("Не могу распознать номер заявки. Попробуйте ещё раз.")
                return
            
            # Проверяем, существует ли уже такая заявка
            if ticket_number in active_tickets:
                logging.warning(f"Ticket {ticket_number} already exists.")
                await message.reply(f"Ticket {ticket_number} already exists.")
                return

            # Отправляем сообщение в тему Статус
            opens_message_id = await bot.send_message(
                chat_id = chat_id,
                text = f"{ticket_number}\n📥 открыт в {date_time_formatter(now)}",
                message_thread_id = STATUS_TOPIC_ID
            )

            active_tickets[ticket_number] = {
                "chat_id": chat_id,
                "message_thread_id": topic_id,
                "message_id": message.message_id,
                "opens_message_id": opens_message_id.message_id,
                "start_time": now,
                "remind_times": 0,
                "notification_messages": []
            }
            save_tickets()
            schedule_reminder(ticket_number)

            try:
                # Удаляем сообщение с +
                await bot.delete_message(chat_id = chat_id, message_id=message.message_id)
                logging.info(f" === APP_LOG: Message for ticket {ticket_number} deleted.")
            except Exception as e:
                logging.error(f"Failed to delete message for ticket {ticket_number}: {e}")

        # Закрыть заявку
        if "- " in message_text:
            logging.info(f" === APP_LOG: {datetime.now().strftime('%H:%M %d.%m.%Y')}: topic_id={message.message_thread_id} Method=\"- \"")

            # Извлекаем номер заявки
            try:
                ticket_number = message_text.split("- ")[1].split()[0]
            except IndexError:
                await message.reply("I can't recognize the application number. Try again.")
                return

            if ticket_number in active_tickets:
                ticket = active_tickets[ticket_number]

                # Отправляем сообщение о закрытии в тему Статус
                await bot.edit_message_text(
                    chat_id = chat_id,
                    message_id = ticket['opens_message_id'],
                    text = f"{ticket_number}\n📥 открыт в {date_time_formatter(ticket['start_time'])}\n✅ закрыт в {date_time_formatter(now)}",
                )

                try:
                    # Удаляем сообщение с + 
                    await bot.delete_message(chat_id=ticket["chat_id"], message_id=ticket["message_id"])
                    logging.info(f"Message for ticket {ticket_number} deleted.")
                except Exception as e:
                    logging.error(f"Failed to delete message for ticket {ticket_number}: {e}")

                # Удаляем все сообщения-оповещения
                for msg_id in ticket.get("notification_messages", []):
                    try:
                        await bot.delete_message(chat_id=ticket["chat_id"], message_id=msg_id)
                        logging.info(f"Deleted notification message {msg_id} for ticket {ticket_number}")
                    except Exception as e:
                        logging.error(f"Failed to delete notification message {msg_id} for ticket {ticket_number}: {e}")

                remove_reminder(ticket_number)  # Удаляем задачу из планировщика
                del active_tickets[ticket_number]  # Удаляем из списка активных заявок
                save_tickets()  # Сохраняем изменения

                try:
                    # Удаляем сообщение с - 
                    await bot.delete_message(chat_id=ticket["chat_id"], message_id=message.message_id)
                    logging.info(f" === APP_LOG: Message for ticket {ticket_number} deleted.")
                except Exception as e:
                    logging.error(f" === APP_LOG: Failed to delete message for ticket {ticket_number}: {e}")

            else:
                await message.reply(f"{ticket_number} Не найден.")


        # Показать открытые заявки
        if "list" in message.text.lower():
            logging.info(f" === APP_LOG: {datetime.now().strftime('%H:%M %d.%m.%Y')}: topic_id={message.message_thread_id} Method=\"list\"")
            formatted_tickets = json.dumps(active_tickets, indent=4, ensure_ascii=False)
            await bot.send_message(
                chat_id = message.chat.id,
                text = f"<pre>{formatted_tickets}</pre>",
                parse_mode = "HTML",
                message_thread_id = message.message_thread_id
            )


        # Помощь по командам
        if "bot help" in message.text.lower():
            logging.info(f" === APP_LOG: {datetime.now().strftime('%H:%M %d.%m.%Y')}: Method \"bot help\" triggered")
            
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
        if "tid" in message_text:
            logging.info(f" === APP_LOG: thread_id = {message.message_thread_id}")

# --- Инициализация ---------------------------------------------------------

dp.include_router(router) # Регистрация маршрутизатора
load_tickets() # Загрузка заявок из БД
load_scheduler_jobs() # Загрузка задач планировщика из БД

# Основной цикл для выполнения задач планировщика
async def run_scheduler():
    while True:
        await schedule.run_pending()
        await asyncio.sleep(1)

# Основная функция запуска
async def main():
    asyncio.create_task(run_scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    atexit.register(save_tickets)
    asyncio.run(main())
