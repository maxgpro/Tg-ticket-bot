# Installation

`cp .env.dist .env` — Make and fill config

`cp tickets.json.dist tickets.json` — Make Ticket Storage

`docker compose buil` — Build Docker


# Work

`docker compose up -d` — Start

`docker exec -it tg-bot bash` — Go into container

## Without Docker

`source venv/bin/activate` - Activate Virtual Environment

`deactivate` — Deactivate Virtual Environment

`python3 bot.py` — Start bot

# Service Comands

`pip install --upgrade pip` — Update pip package manager

`pip install aiogram aioschedule python-dotenv` — Install dependencies

`pip list` — show uses dependencies

`pip freeze > requirements.txt` — save list of dependencies

# DB active_tickets.json
```json
{
    "<ticket_number>": {
        "start_time": "дата и время",
        "chat_id": "ID темы",
        "remind_times": 0,
        "message_id": "ID сообщения, создавшего заявку",
        "notification_messages": []  # Список ID сообщений-оповещений
    }
}
```

# Backlog

- start_time взять из message.date
- разделить логику
