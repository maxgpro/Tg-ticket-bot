# Installation
`sudo apt update`

`sudo apt install python3` — Install python3

`sudo apt install python3-venv` — Install the virtual environment manager

`python3 -m venv venv` — Create a virtual environment

`cp tickets.json.dist tickets.json` — Make Storage

`cp config/config.py.dist config/config.py` — Make Config


# Work
`source venv/bin/activate` - Activate Virtual Envairament

`deactivate` — Deactivate

`python3 bot.py` — Start bot

# Service Comands
`pip install --upgrade pip` — Update pip

`pip install aiogram aioschedule` — Install dependencies

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
