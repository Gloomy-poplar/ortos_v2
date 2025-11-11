# -*- coding: utf-8 -*-
import requests
import sys

# Устанавливаем правильное кодирование для консоли Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from config import Config


class BitrixChatService:
    def __init__(self):
        self.webhook_url = Config.BITRIX_WEBHOOK_URL  # Вебхук бота
        self.bot_name = Config.BITRIX_BOT_NAME
        self.bot_code = Config.BITRIX_BOT_CODE
        self.session = requests.Session()

    def test_connection(self) -> bool:
        """Проверяет подключение к Битрикс24 через вебхук"""
        try:
            print(f"🔧 Тестируем подключение к: {self.webhook_url}")
            response = self.session.post(
                f"{self.webhook_url}/profile", timeout=10)
            print(f"📡 Статус: {response.status_code}")
            if response.status_code == 200 and response.json().get('result'):
                print("✅ Подключение успешно!")
                return True
            else:
                print(f"❌ Ошибка в ответе: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False

    def send_message(self, dialog_id: str, message: str) -> bool:
        """Отправляет сообщение в чат Битрикс24 через вебхук"""
        try:
            message_data = {"DIALOG_ID": dialog_id, "MESSAGE": message}
            print(f"📤 Отправляем сообщение в {dialog_id}: {message[:100]}...")
            response = self.session.post(f"{self.webhook_url}/im.message.add",
                                         json=message_data, timeout=10)
            print(
                f"📥 Ответ отправки: {response.status_code} - {response.text}")
            if response.status_code == 200 and response.json().get('result'):
                print(f"✅ Сообщение отправлено в чат {dialog_id}")
                return True
            else:
                print(f"❌ Ошибка API: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Ошибка отправки в чат: {e}")
            return False
