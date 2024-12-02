# Installation

`cp .env.dist .env` — Make and fill config

`cp tickets.json.dist tickets.json` — Make Ticket Storage

`docker compose build` — Build Docker


# Work

`docker compose up` — Start

`docker exec -it tg-bot bash` — Go into container

## Without Docker

`python3 -m venv venv` — Create a virtual environment

`source venv/bin/activate` - Activate Virtual Environment

`deactivate` — Deactivate Virtual Environment

`python3 app/main.py` — Start bot

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
        "message_thread_id": "",
        "message_id": "ID сообщения, создавшего заявку",
        "opens_message_id": "",
        "remind_times": 0,
        "notification_messages": []
    }
}
```

# Backlog

- start_time взять из message.date
- разделить логику
