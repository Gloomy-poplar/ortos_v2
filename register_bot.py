import requests

url = "https://b24-sdgm61.bitrix24.by/rest/1/bv5e5fucx8hy0bd1/imbot.register.json"

data = {
    "CODE": "ortos_consultant",
    "TYPE": "B",
    "EVENT_MESSAGE_ADD": "https://web-production-0df7.up.railway.app/bitrix/message",
    "EVENT_WELCOME_MESSAGE": "https://web-production-0df7.up.railway.app/bitrix/welcome",
    "EVENT_BOT_DELETE": "https://web-production-0df7.up.railway.app/bitrix/delete",
    "LANG": [
        {"LANGUAGE_ID": "ru", "TITLE": "ORTOS Consultant",
            "DESCRIPTION": "Консультант компании ORTOS — отвечает на вопросы клиентов"}
    ],
    "OPENLINE": "Y"
}

response = requests.post(url, json=data)
print(response.json())
