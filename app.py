import os
import json
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import telebot
from monitor import (
    check_uptolink, check_single_code, check_all_codes,
    load_codes, save_codes, load_users, save_users,
    load_config, save_config, test_proxy_connection
)

# =================== CONFIG ===================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8703732480:AAE060Uo9Jq7zyIiLEEePlleLv2AqTCbJ4Y")
BASE_URL = os.getenv("BASE_URL", "https://uptolink-production-c43d.up.railway.app")

app = Flask(__name__, static_folder='frontend', static_url_path='')
CORS(app)

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# =================== TRẠNG THÁI ===================
is_checking = False
check_lock = threading.Lock()
last_result = {
    "new_codes": [],
    "codes_with": [],
    "codes_without": [],
    "status": "idle",
    "message": "",
    "timestamp": None
}
last_check_time = None
pending_users = []
check_counter = 0
log_messages = []

def log(msg):
    print(msg, flush=True)
    log_messages.append(msg)
    if len(log_messages) > 500:
        del log_messages[:len(log_messages) - 500]

# =================== API ===================
@app.route('/api/status', methods=['GET'])
def get_status():
    users = load_users()
    codes = load_codes()
    config = load_config()
    return jsonify({
        "users": len(users),
        "codes": list(codes),
        "is_checking": is_checking,
        "last_result": last_result,
        "pending_users": len(pending_users),
        "logs": log_messages[-80:],
        "proxy_config": config
    })

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(load_config())

@app.route('/api/config', methods=['POST'])
def save_proxy_config():
    try:
        data = request.json or {}
        config = {
            "use_proxy": bool(data.get("use_proxy", False)),
            "proxy_host": str(data.get("proxy_host", "")).strip(),
            "proxy_port": str(data.get("proxy_port", "")).strip(),
            "proxy_type": str(data.get("proxy_type", "http")).strip().lower(),
            "proxy_user": str(data.get("proxy_user", "")).strip(),
            "proxy_pass": str(data.get("proxy_pass", "")).strip()
        }
        save_config(config)
        print(f"[SAVE PROXY] use_proxy={config['use_proxy']}, host={config['proxy_host']}")
        return jsonify({"status": "success", "message": "✅ Đã lưu proxy"})
    except Exception as e:
        print(f"[SAVE ERROR] {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/test-proxy', methods=['POST'])
def test_proxy():
    success = test_proxy_connection(log_fn=log)
    config = load_config()
    return jsonify({
        "status": "ok", 
        "config": config,
        "proxy_alive": success,
        "message": "Proxy HOẠT ĐỘNG" if success else "Proxy DIE hoặc timeout"
    })

@app.route('/api/check', methods=['POST'])
def start_check():
    global is_checking, last_result, last_check_time, pending_users, check_counter, log_messages
    with check_lock:
        if is_checking:
            return jsonify({"status": "already_running", "message": "Đang kiểm tra, vui lòng đợi!"}), 429
        if last_check_time:
            time_diff = (datetime.now() - last_check_time).total_seconds() / 60
            if time_diff < 30:
                wait_minutes = int(30 - time_diff) + 1
                return jsonify({
                    "status": "cooldown",
                    "message": f"Vui lòng đợi {wait_minutes} phút nữa",
                    "last_result": last_result
                }), 429
        is_checking = True
        check_counter += 1
        last_result["status"] = "running"
        log(f"[*] BẮT ĐẦU KIỂM TRA PHIÊN {check_counter}")
    
    def run_check():
        global is_checking, last_result, last_check_time, pending_users
        try:
            new_codes = check_uptolink(log_fn=log)
            log(f"[*] Tìm thấy {len(new_codes)} mã mới")
            if not new_codes:
                last_result = {
                    "new_codes": [],
                    "codes_with": [],
                    "codes_without": [],
                    "status": "no_codes",
                    "message": "Không tìm thấy mã mới",
                    "timestamp": datetime.now().isoformat()
                }
                is_checking = False
                pending_users = []
                return
            codes_with, codes_without = check_all_codes(new_codes, log_fn=log)
            last_result = {
                "new_codes": new_codes,
                "codes_with": codes_with,
                "codes_without": codes_without,
                "status": "done",
                "message": f"Tìm thấy {len(codes_with)} mã có nút, {len(codes_without)} mã không có nút",
                "timestamp": datetime.now().isoformat()
            }
            last_check_time = datetime.now()
            if pending_users:
                send_telegram_report(new_codes, codes_with, codes_without)
            log(f"[*] KẾT THÚC KIỂM TRA PHIÊN {check_counter}")
        except Exception as e:
            last_result = {
                "new_codes": [],
                "codes_with": [],
                "codes_without": [],
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
            log(f"[!] Lỗi: {e}")
        finally:
            is_checking = False
            pending_users = []
    
    threading.Thread(target=run_check, daemon=True).start()
    return jsonify({"status": "started", "message": "Đã bắt đầu kiểm tra!"})

# =================== TELEGRAM (giữ nguyên) ===================
def send_telegram_report(new_codes, codes_with, codes_without):
    users = load_users()
    if not users: return
    msg1 = "PHÁT HIỆN MÃ MỚI ✅\n"
    for c in new_codes: msg1 += f"- {c}\n"
    msg1 += f"\n{datetime.now().strftime('%H:%M, %d/%m/%Y')}"
    msg2 = ""
    if codes_with:
        msg2 += "PHÁT HIỆN MÃ CÓ NÚT ✅\n"
        for c in codes_with: msg2 += f"- {c} - Có Nút 🔥\n"
    if codes_without:
        if msg2: msg2 += "================\n"
        msg2 += "MÃ KHÔNG CÓ NÚT ❗\n"
        for c in codes_without: msg2 += f"- {c} - 💢\n"
    if msg2: msg2 += f"\n{datetime.now().strftime('%H:%M, %d/%m/%Y')}"
    for user in users:
        try:
            bot.send_message(user, msg1)
            if msg2: bot.send_message(user, msg2)
        except: pass

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = str(message.chat.id)
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        save_users(users)
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton("🚀 Mở UptoLink Monitor", web_app=telebot.types.WebAppInfo(url=BASE_URL)))
    bot.reply_to(message, "🤖 **UptoLink Monitor Bot**\n\n📌 Mở Mini App để dùng.\n🌐 Hỗ trợ Proxy", reply_markup=keyboard, parse_mode="Markdown")

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return 'OK', 200

# =================== STATIC ===================
@app.route('/')
def serve_index():
    return send_from_directory('frontend', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('frontend', path)

# =================== MAIN ===================
if __name__ == '__main__':
    if not os.path.exists("users.json"): save_users([])
    if not os.path.exists("found_codes.json"): save_codes([])
    if not os.path.exists("config.json"):
        save_config({"use_proxy": False, "proxy_host": "", "proxy_port": "", "proxy_type": "http", "proxy_user": "", "proxy_pass": ""})
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)