from services.bitrix_chat_service import BitrixChatService
from utils.logger import log_message
from services.bot_service import BotService, EmbeddingsBotService
from config import Config
import subprocess
import sys
import requests
from flask import Flask, request, jsonify, redirect
import json
from typing import Dict, Optional
from datetime import datetime
import os

os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Устанавливаем правильное кодирование для консоли Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


print("🚀 Starting ORTOS Bot Application...")
print(f"📊 Config loaded: TELEGRAM_TOKEN = {bool(Config.TELEGRAM_TOKEN)}")
print(f"📊 Config loaded: GROQ_API_KEY = {bool(Config.GROQ_API_KEY)}")

app = Flask(__name__)
bot_service = BotService()
embeddings_bot_service: Optional[EmbeddingsBotService] = None
bitrix_chat_service = BitrixChatService()

def get_embeddings_bot_service() -> EmbeddingsBotService:
    global embeddings_bot_service
    if embeddings_bot_service is None:
        embeddings_bot_service = EmbeddingsBotService()
    return embeddings_bot_service

# Webhook для Telegram


@app.route('/telegram/<token>', methods=['POST'])
def telegram_webhook(token):
    try:
        if token != Config.TELEGRAM_TOKEN:
            return jsonify({"error": "Invalid token"}), 403

        data = request.json
        message = data.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        user_name = message.get('chat', {}).get('first_name', 'Unknown')
        text = message.get('text', '')

        print(f"👤 {user_name} ({chat_id}): {text}")

        if text:
            service = get_embeddings_bot_service()
            ai_response = service.process_question(
                text, user_id=str(chat_id))
            log_message(user_name, chat_id, text, ai_response)

            requests.post(
                Config.TELEGRAM_URL + "/sendMessage",
                json={"chat_id": chat_id, "text": ai_response}
            )

        return jsonify({"status": "ok"})

    except Exception as e:
        print(f"❌ Ошибка webhook: {e}")
        return jsonify({"error": str(e)}), 500

# Bitrix24 Open Lines Webhook


@app.route('/bitrix/openlines_webhook', methods=['GET', 'POST'])
def openlines_webhook():
    try:
        print("=" * 60)
        print("🤖 BITRIX24 OPENLINES WEBHOOK CALLED!")

        # Обработка GET запросов (OAuth callback)
        if request.method == "GET":
            code = request.args.get("code")
            if code:
                return redirect(f"/install?code={code}")
            return "GET without code"

        # Обработка POST запросов (сообщения из чата)
        print(f"📦 Method: {request.method}")
        print(f"📦 Headers: {dict(request.headers)}")
        print(f"📦 Content-Type: {request.content_type}")
        print(f"📦 Args: {request.args}")

        # Извлекаем данные в правильном формате для Bitrix24
        data = {}
        if request.content_type == 'application/json':
            data = request.json or {}
        elif request.form:
            data = request.form.to_dict()
        else:
            try:
                raw_data = request.get_data(as_text=True)
                if raw_data:
                    data = json.loads(raw_data)
            except:
                pass

        print(f"📨 Data: {data}")

        # Обрабатываем событие сообщения
        if data.get('event') == 'ONIMBOTMESSAGEADD':
            return handle_bitrix_message(data)

        # Обрабатываем приветственное сообщение
        elif data.get('event') == 'ONIMBOTWELCOMEMESSAGE':
            return handle_welcome_message(data)

        else:
            print(f"🤔 Unknown event: {data.get('event')}")

        return jsonify({"status": "ok"})

    except Exception as e:
        print(f"❌ Bitrix webhook error: {e}")
        import traceback
        print(f"🔍 TRACEBACK: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 200


def handle_bitrix_message(data):
    """Обработка сообщений из Bitrix24 Open Lines"""
    message = data.get('data[PARAMS][MESSAGE]', '') or data.get(
        'data', {}).get('MESSAGE', '')
    dialog_id = data.get('data[PARAMS][DIALOG_ID]', '') or data.get(
        'data', {}).get('DIALOG_ID', '')
    user_id = data.get('data[USER][ID]', '') or data.get(
        'data', {}).get('USER_ID', '')

    print(f"💬 Message: '{message}', Dialog: {dialog_id}, User: {user_id}")

    if not message or not dialog_id:
        print("❌ No message or dialog_id")
        return jsonify({"status": "ignored"}), 200

    # Извлекаем chat_id из dialog_id (пример: "chat48" → 48)
    chat_id = None
    if dialog_id.startswith("chat"):
        try:
            chat_id = int(dialog_id.replace("chat", ""))
        except ValueError:
            print("⚠️ Не удалось извлечь chat_id из dialog_id")

    # Обрабатываем команду перевода на оператора
    message_lower = message.lower()
    operator_keywords = ['оператор', 'человек', 'менеджер',
                         'специалист', 'живой', 'человека', 'свяжите с оператором']

    if any(keyword in message_lower for keyword in operator_keywords):
        print("🔄 Transferring to operator...")
        return transfer_to_operator(dialog_id, user_id, chat_id)

    # Игнорируем команды
    if message.startswith('/'):
        print("🤖 Ignoring command")
        return jsonify({"status": "ignored"}), 200

    # Обрабатываем через AI бота
    print(f"🤖 Processing message through AI...")
    try:
        ai_response = bot_service.process_question(
            message, user_id=str(user_id or dialog_id))
        print(f"🤖 AI Response: {ai_response[:100]}...")
    except Exception as e:
        print(f"❌ AI processing error: {e}")
        ai_response = "Извините, произошла ошибка. Попробуйте позже."

    # Отправляем ответ в Bitrix24 через imbot.message.add
    print(f"📤 Sending response to Bitrix24...")
    try:
        response = requests.post(
            "https://b24-sdgm61.bitrix24.by/rest/1/ummeoyhga98c0xoa/imbot.message.add",
            json={
                "BOT_ID": "36",
                "CLIENT_ID": "hk6ov2nmxj1keecgsr8sknzjzs4xs94i",
                "DIALOG_ID": dialog_id,
                "MESSAGE": ai_response
            },
            timeout=10
        )

        if response.status_code == 200:
            print("✅ Response sent successfully via imbot.message.add")
            log_message(f"BitrixUser_{user_id}",
                        dialog_id, message, ai_response)
        else:
            print(
                f"❌ Failed to send response: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"❌ Error sending to Bitrix24: {e}")

    return jsonify({"status": "ok"})


def transfer_to_operator(dialog_id, user_id, chat_id):
    """Перевод чата на операторов контакт-центра"""
    try:
        if not chat_id:
            print("⚠️ chat_id не найден, невозможно передать оператору")
            return jsonify({"status": "error", "message": "no_chat_id"}), 400

        # 1️⃣ Сообщаем клиенту, что оператор подключится
        client_text = "👩‍💼 Оператор сейчас подключится. Пожалуйста, ожидайте."
        client_response = requests.post(
            "https://b24-sdgm61.bitrix24.by/rest/1/ummeoyhga98c0xoa/imbot.message.add",
            json={
                "BOT_ID": "36",
                "CLIENT_ID": "hk6ov2nmxj1keecgsr8sknzjzs4xs94i",
                "DIALOG_ID": dialog_id,
                "MESSAGE": client_text
            },
            timeout=10
        )

        if client_response.status_code != 200:
            print(f"❌ Ошибка при отправке клиенту: {client_response.text}")
            return jsonify({"status": "error"}), 500

        print("✅ Сообщение клиенту отправлено")

        # 2️⃣ Передаём чат в контакт-центр (именно этот метод)
        transfer_response = requests.post(
            "https://b24-sdgm61.bitrix24.by/rest/1/ummeoyhga98c0xoa/imopenlines.bot.session.operator",
            json={
                "CHAT_ID": chat_id
            },
            timeout=10
        )

        if transfer_response.status_code == 200:
            print("✅ Чат передан контакт-центру")
            print(f"📨 Ответ Bitrix24: {transfer_response.text}")
        else:
            print(
                f"❌ Ошибка при передаче в контакт-центр: {transfer_response.text}")

        return jsonify({"status": "transferred"})

    except Exception as e:
        print(f"❌ Ошибка перевода на оператора: {e}")
        return jsonify({"status": "error"}), 500


def handle_welcome_message(data):
    """Приветственное сообщение"""
    print("🎉 Welcome message triggered")

    welcome_text = """👋 Добро пожаловать! 

Я консультант ORTOS по индивидуальным стелькам. 

Чем могу помочь?
• 🩺 Консультация по стелькам
• 💰 Узнать цены и сроки
• 📍 Найти ближайший салон
• 📞 Записаться на консультацию

🤖 **Если нужен живой оператор, просто напишите: "Оператор"**

Задайте ваш вопрос!"""

    # Извлекаем dialog_id из данных
    dialog_id = data.get('data[PARAMS][DIALOG_ID]', '') or data.get(
        'data', {}).get('DIALOG_ID', '')

    if dialog_id:
        try:
            response = requests.post(
                "https://b24-sdgm61.bitrix24.by/rest/1/ummeoyhga98c0xoa/imbot.message.add",
                json={
                    "BOT_ID": "36",
                    "CLIENT_ID": "hk6ov2nmxj1keecgsr8sknzjzs4xs94i",
                    "DIALOG_ID": dialog_id,
                    "MESSAGE": welcome_text
                }
            )
            if response.status_code == 200:
                print("✅ Welcome message sent")
            else:
                print(f"❌ Failed to send welcome message: {response.text}")
        except Exception as e:
            print(f"❌ Error sending welcome message: {e}")

    return jsonify({"status": "welcome_sent"})

# Остальные маршруты из оригинального кода


@app.route('/bitrix/debug')
def bitrix_debug():
    """Детальная диагностика подключения к Битрикс24"""
    try:
        debug_info = []
        debug_info.append("🔧 Детальная диагностика подключения к Битрикс24")
        debug_info.append("=" * 50)

        # Тест базового подключения
        debug_info.append("\n1. 📡 Тестируем базовое подключение...")
        test_url = f"{Config.BITRIX_WEBHOOK_URL}/profile"

        try:
            response = requests.post(test_url, timeout=10)
            debug_info.append(f"   URL: {test_url}")
            debug_info.append(f"   Статус: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                if result.get('result'):
                    debug_info.append("   ✅ Вебхук работает корректно!")
                else:
                    debug_info.append(f"   ❌ Ошибка в ответе: {result}")
            else:
                debug_info.append(f"   ❌ HTTP ошибка: {response.status_code}")
                debug_info.append(f"   📄 Ответ: {response.text}")

        except Exception as e:
            debug_info.append(f"   ❌ Ошибка подключения: {e}")

        debug_info.append("\n" + "=" * 50)
        html_content = "<h1>🔧 Диагностика Битрикс24</h1><pre style='background: #f5f5f5; padding: 20px; border-radius: 10px; white-space: pre-wrap;'>" + \
            "\n".join(debug_info) + "</pre>"
        html_content += '<p><a href="/">🏠 На главную</a></p>'

        return html_content

    except Exception as e:
        return f"<h1>❌ Ошибка диагностики</h1><pre>{str(e)}</pre>"

# Остальные маршруты...


@app.route('/')
def home():
    return """
    <h1>🤖 Консультант по индивидуальным стелькам ORTOS</h1>
    
    <div style="background: #e8f5e8; padding: 20px; border-radius: 10px; margin: 20px 0;">
    <h3>📱 Telegram бот:</h3>
    <p><a href="https://t.me/OrtosBelarus_bot" target="_blank" style="background: #0088cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">@OrtosBelarus_bot</a></p>
    </div>

    <div style="background: #fff3cd; padding: 20px; border-radius: 10px; margin: 20px 0;">
    <h3>🏢 Интеграция с Битрикс24:</h3>
    <p><strong>Бот активен и готов к работе!</strong></p>
    <p>Сообщения из открытых линий Bitrix24 будут обрабатываться AI-консультантом</p>
    <p><a href="/bitrix/test" style="background: #28a745; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px; margin: 0 10px;">Проверить подключение</a>
    <a href="/bitrix/debug" style="background: #6c757d; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">Диагностика</a></p>
    </div>

    <div style="background: #f8f9fa; padding: 15px; border-radius: 10px;">
    <h3>🔧 Администрирование:</h3>
    <ul>
        <li><a href="/admin/logs">📊 Просмотр логов консультаций</a></li>
        <li><a href="/test">🧪 Тестирование бота</a></li>
        <li><a href="/set_webhook">🔄 Активировать Telegram бота</a></li>
    </ul>
    </div>
    """


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Starting server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
