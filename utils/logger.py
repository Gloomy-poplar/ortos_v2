import os
import requests
from datetime import datetime, timedelta
from config import Config

def log_message(user_name: str, user_id: str, message: str, response: str) -> None:
    """Логирование сообщений"""
    try:
        # Получаем текущее время в UTC и добавляем 3 часа для Минского времени
        utc_now = datetime.utcnow()
        minsk_time = utc_now + timedelta(hours=3)

        # Форматируем время в удобном формате
        local_time = minsk_time.strftime("%Y-%m-%d %H:%M:%S (Минск UTC+3)")

        # Создаем запись лога
        log_entry = f"{local_time} | {user_name} ({user_id}) | Вопрос: {message} | Ответ: {response}\n"

        # Пробуем несколько путей для записи логов
        log_paths = [
            Config.LOGS_FILE,
            '/home/Gungrave/mysite/chat_logs.txt',
            '/tmp/ortos_chat_logs.txt'
        ]

        for log_path in log_paths:
            try:
                # Создаем директорию если не существует
                os.makedirs(os.path.dirname(log_path), exist_ok=True)

                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(log_entry)
                print(f"✅ Лог записан в: {log_path}")
                break
            except Exception as e:
                print(f"❌ Ошибка записи в {log_path}: {e}")
                continue
        else:
            # Если все пути не сработали, пишем в консоль
            print(f"📝 Лог (в консоль): {log_entry.strip()}")

    except Exception as e:
        print(f"❌ Критическая ошибка логирования: {e}")

def send_telegram_message(chat_id: str, text: str) -> bool:
    """Отправка сообщения в Telegram"""
    try:
        response = requests.post(
            Config.TELEGRAM_URL + "/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text
            }
        )
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Ошибка отправки в Telegram: {e}")
        return False