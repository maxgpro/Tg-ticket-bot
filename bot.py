import logging
import json
import atexit
import asyncio
import aioschedule as schedule
from config.config import TOKEN, REMINDER_INTERVAL
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
            elapsed_time = timedelta(seconds=ticket["remind_times"] * REMINDER_INTERVAL)
            start_time = datetime.strptime(ticket["start_time"], '%H:%M %d.%m.%Y')

            # Отправляем сообщение как ответ на исходное сообщение
            await bot.send_message(
                chat_id=ticket["chat_id"],
                text=f"Reminder: Ticket {ticket_number} opened {elapsed_time} "
                     f"({start_time.strftime('%H:%M %d.%m.%Y')})",
                reply_to_message_id=ticket["message_id"]  # Ответ на сообщение
            )
            logging.info(f"Reminder sent for ticket {ticket_number}")
    except Exception as e:
        logging.error(f"Error in send_reminder for ticket {ticket_number}: {e}")




# --- Команды бота ---------------------------------------------------------

@router.message()
async def handle_message(message: Message):
    # Проверяем, что сообщение пришло из группы или супергруппы
    if message.chat.type in ["group", "supergroup"]:
        logging.info(f"Message received from the group: {message.chat.title} | {message.text}")

        now = datetime.now().strftime('%H:%M %d.%m.%Y')
        chat_id = message.chat.id
        # Приводим текст к единому виду, удаляя лишние пробелы
        message_text = message.text.strip().lower()

        # Открыть заявку
        if "ticket open" in message_text:
            logging.info(f"{datetime.now().strftime('%H:%M %d.%m.%Y')}: Method \"ticket open\" triggered")

            # Извлекаем номер заявки
            try:
                ticket_number = message_text.split("ticket open")[1].split()[0]
            except IndexError as e:
                logging.error(f"Failed to extract ticket number: {e}")
                await message.reply("Не могу распознать номер заявки. Попробуйте ещё раз.")
                return
            
            # Проверяем, существует ли уже такая заявка
            if ticket_number in active_tickets:
                logging.warning(f"Ticket {ticket_number} already exists.")
                await message.reply(f"Ticket {ticket_number} already exists.")
                return

            active_tickets[ticket_number] = {
                "chat_id": chat_id,
                "message_id": message.message_id,
                "start_time": now,
                "remind_times": 0
            }
            save_tickets()
            schedule_reminder(ticket_number)
            await message.reply(f"Ticket {ticket_number} was open ({now})")

        # Закрыть заявку
        if "ticket close" in message_text:
            logging.info(f"{datetime.now().strftime('%H:%M %d.%m.%Y')}: Method \"ticket close\" triggered")

            # Извлекаем номер заявки
            try:
                ticket_number = message_text.split("ticket close")[1].split()[0]
            except IndexError:
                await message.reply("I can't recognize the application number. Try again.")
                return

            if ticket_number in active_tickets:
                ticket = active_tickets[ticket_number]
                try:
                    # Удаляем сообщение с ticket open
                    await bot.delete_message(chat_id=ticket["chat_id"], message_id=ticket["message_id"])
                    logging.info(f"Message for ticket {ticket_number} deleted.")
                except Exception as e:
                    logging.error(f"Failed to delete message for ticket {ticket_number}: {e}")

                remove_reminder(ticket_number)  # Удаляем задачу из планировщика
                del active_tickets[ticket_number]  # Удаляем из списка активных заявок
                save_tickets()  # Сохраняем изменения
                await message.reply(f"Ticket {ticket_number} was closed.")
            else:
                await message.reply(f"Ticket {ticket_number} not found.")


        # Показать открытые заявки
        if "opens" in message.text.lower():
            logging.info(f"{datetime.now().strftime('%H:%M %d.%m.%Y')}: Method \"opens\" triggered")
            formatted_tickets = json.dumps(active_tickets, indent=4, ensure_ascii=False)
            await bot.send_message(chat_id=chat_id, text=f"<pre>{formatted_tickets}</pre>", parse_mode="HTML")


        # Помощь по командам
        if "bot help" in message.text.lower():
            logging.info(f"{datetime.now().strftime('%H:%M %d.%m.%Y')}: Method \"bot help\" triggered")
            
            help_text = (
                "📋 **Доступные команды**:\n"
                "1. **Открыть заявку:**\n"
                "Напишите `ticket open `<номер заявки> чтобы создать новое оповещение.\n"
                "   _Пример: ticket open 1234_\n\n"
                "2. **Закрыть заявку:**\n"
                "Напишите `ticket close `<номер заявки> чтобы удалить оповещение.\n"
                "   _Пример: ticket close 1234_\n\n"
                "3. **Показать открытые заявки:**\n"
                "   Напишите `opens` для просмотра списка открытых оповещений.\n"
            )

            await message.reply(help_text, parse_mode="Markdown")


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
