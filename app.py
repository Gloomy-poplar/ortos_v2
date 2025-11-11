import subprocess
import os
import requests
from flask import Flask, request, jsonify, redirect
import json
from typing import Dict
from config import Config
from services.bot_service import BotService
from utils.logger import log_message
from services.bitrix_chat_service import BitrixChatService
from datetime import datetime
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

print("[INFO] Starting ORTOS Bot Application...")

required_vars = ['GROQ_API_KEY', 'TELEGRAM_TOKEN']
missing_vars = []

for var in required_vars:
    if not os.environ.get(var):
        missing_vars.append(var)

if missing_vars:
    print(f"[ERROR] CRITICAL: Missing environment variables: {', '.join(missing_vars)}")
    print("[WARN] Application will continue but some features may not work")
else:
    print("[OK] All critical environment variables are set")

print(f"[INFO] Config loaded: TELEGRAM_TOKEN = {bool(Config.TELEGRAM_TOKEN)}")
print(f"[INFO] Config loaded: GROQ_API_KEY = {bool(Config.GROQ_API_KEY)}")

app = Flask(__name__)

bot_service = None
bitrix_chat_service = None

def init_services():
    global bot_service, bitrix_chat_service
    try:
        print("[INFO] Initializing BotService...")
        bot_service = BotService()
        print("[OK] BotService initialized")
    except Exception as e:
        print(f"[ERROR] Error initializing BotService: {e}")
        bot_service = None

    try:
        print("[INFO] Initializing BitrixChatService...")
        bitrix_chat_service = BitrixChatService()
        print("[OK] BitrixChatService initialized")
    except Exception as e:
        print(f"[ERROR] Error initializing BitrixChatService: {e}")
        bitrix_chat_service = None

@app.route('/')
def health():
    try:
        status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "bot_service": bot_service is not None,
                "bitrix_service": bitrix_chat_service is not None
            }
        }
        if request.headers.get('User-Agent', '').startswith('Railway'):
            return "OK", 200
        return jsonify(status), 200
    except Exception as e:
        print(f"[ERROR] Health check error: {e}")
        return "OK", 200

@app.route('/home')
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

@app.route('/telegram/<token>', methods=['POST'])
def telegram_webhook(token):
    try:
        if token != Config.TELEGRAM_TOKEN:
            return jsonify({"error": "Invalid token"}), 403
        if not bot_service:
            return jsonify({"error": "Bot service not available"}), 503

        data = request.json
        message = data.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        user_name = message.get('chat', {}).get('first_name', 'Unknown')
        text = message.get('text', '')

        if not text:
            return jsonify({"status": "ok"})

        print(f"[INFO] Telegram message from {user_name} (ID: {chat_id}): {text}")

        ai_response = bot_service.process_question(text, user_id=str(chat_id))
        log_message(user_name, chat_id, text, ai_response)

        send_url = f"{Config.TELEGRAM_URL}/sendMessage"
        requests.post(send_url, json={"chat_id": chat_id, "text": ai_response})

        return jsonify({"status": "ok"})

    except Exception as e:
        print(f"[ERROR] telegram_webhook: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/bitrix/openlines_webhook', methods=['GET', 'POST'])
def openlines_webhook():
    try:
        print("=" * 60)
        print("[INFO] BITRIX24 OPENLINES WEBHOOK CALLED!")

        if request.method == "GET":
            code = request.args.get("code")
            if code:
                return redirect(f"/install?code={code}")
            return "GET without code"

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

        print(f"[INFO] Data: {data}")

        event = data.get('event')
        if event == 'ONIMBOTMESSAGEADD':
            return handle_bitrix_message(data)
        elif event == 'ONIMBOTWELCOMEMESSAGE':
            return handle_welcome_message(data)
        else:
            print(f"[WARN] Unknown event: {event}")
            print("[INFO] Full payload:", data)

        return jsonify({"status": "ok"})

    except Exception as e:
        import traceback
        print(f"[ERROR] Bitrix webhook error: {e}")
        print(f"[INFO] TRACEBACK: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 200


def handle_bitrix_message(data):
    message = data.get('data[PARAMS][MESSAGE]', '') or data.get(
        'data', {}).get('MESSAGE', '')
    dialog_id = data.get('data[PARAMS][DIALOG_ID]', '') or data.get(
        'data', {}).get('DIALOG_ID', '')
    user_id = data.get('data[USER][ID]', '') or data.get(
        'data', {}).get('USER_ID', '')

    client_endpoint = data.get('auth[client_endpoint]', '')
    application_token = data.get('auth[application_token]', '')

    print(f"[INFO] Message: '{message}', Dialog: {dialog_id}, User: {user_id}")
    if client_endpoint:
        print(f"[INFO] Auth credentials found from webhook")

    if not message or not dialog_id:
        return jsonify({"status": "ignored"}), 200

    if not bot_service:
        return jsonify({"status": "error", "message": "Bot service not available"}), 200

    chat_id = None
    if dialog_id.startswith("chat"):
        try:
            chat_id = int(dialog_id.replace("chat", ""))
        except ValueError:
            print("[WARN] Could not extract chat_id from dialog_id")

    message_lower = message.lower()
    operator_keywords = ['оператор', 'человек', 'менеджер',
                         'специалист', 'живой', 'человека', 'свяжите с оператором']

    if any(keyword in message_lower for keyword in operator_keywords):
        return transfer_to_operator(dialog_id, user_id, chat_id, client_endpoint, application_token)

    try:
        ai_response = bot_service.process_question(
            message, user_id=str(user_id or dialog_id))
        log_message(f"BitrixUser_{user_id}", dialog_id, message, ai_response)

        if bitrix_chat_service:
            bitrix_chat_service.send_message(
                dialog_id, ai_response, client_endpoint, application_token)
        else:
            requests.post(
                f"{Config.BITRIX_WEBHOOK_URL}/imbot.message.add",
                json={
                    "BOT_ID": Config.BITRIX_BOT_ID,
                    "CLIENT_ID": Config.BITRIX_CLIENT_ID,
                    "DIALOG_ID": dialog_id,
                    "MESSAGE": ai_response
                },
                timeout=10
            )

        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"[ERROR] Bitrix AI processing error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 200


def transfer_to_operator(dialog_id, user_id, chat_id, client_endpoint=None, application_token=None):
    if not chat_id:
        return jsonify({"status": "error", "message": "no_chat_id"}), 400

    try:
        if bitrix_chat_service:
            bitrix_chat_service.transfer_to_operator(
                dialog_id, client_endpoint, application_token)
        else:
            requests.post(
                f"{Config.BITRIX_WEBHOOK_URL}/imbot.message.add",
                json={
                    "BOT_ID": Config.BITRIX_BOT_ID,
                    "CLIENT_ID": Config.BITRIX_CLIENT_ID,
                    "DIALOG_ID": dialog_id,
                    "MESSAGE": "Соединяю с оператором..."
                },
                timeout=10
            )
        return jsonify({"status": "transferred"}), 200
    except Exception as e:
        print(f"[ERROR] Transfer error: {e}")
        return jsonify({"status": "error"}), 200


def handle_welcome_message(data):
    dialog_id = data.get('data[PARAMS][DIALOG_ID]', '')
    if not dialog_id:
        return jsonify({"status": "ignored"}), 200

    welcome_msg = "👋 Добро пожаловать! Я — AI-консультант ORTOS. Задавайте вопросы о стельках!"

    try:
        if bitrix_chat_service:
            bitrix_chat_service.send_message(dialog_id, welcome_msg)
        else:
            requests.post(
                f"{Config.BITRIX_WEBHOOK_URL}/imbot.message.add",
                json={
                    "BOT_ID": Config.BITRIX_BOT_ID,
                    "CLIENT_ID": Config.BITRIX_CLIENT_ID,
                    "DIALOG_ID": dialog_id,
                    "MESSAGE": welcome_msg
                },
                timeout=10
            )
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"[ERROR] Welcome message error: {e}")
        return jsonify({"status": "error"}), 200


if __name__ == '__main__':
    init_services()
    port = int(os.environ.get('PORT', 5000))
    print(f"[INFO] Starting server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)