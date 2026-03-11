import os
import json
import uuid
import time
import threading
import datetime
import asyncio
from urllib.parse import quote_plus
from flask import Flask, request, jsonify, render_template_string
import requests
from bs4 import BeautifulSoup
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.background import BackgroundScheduler
import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
WEB_DOMAIN = os.getenv("WEB_DOMAIN", "http://127.0.0.1:5000")
PORT = int(os.getenv("PORT", 5000))
DATA_FILE = "track.json"

app = Flask(__name__)
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
scheduler = BackgroundScheduler()

intents = discord.Intents.default()
intents.message_content = True
discord_client = discord.Client(intents=intents)
tree = app_commands.CommandTree(discord_client)
discord_loop = None

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"setup_tokens": {}, "tracking": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def cleanup_expired_tokens():
    data = load_data()
    changed = False
    current_time = time.time()
    setup_tokens = data.get("setup_tokens", {})
    
    keys_to_delete =[]
    for token, info in setup_tokens.items():
        if current_time > info.get("expires_at", 0):
            keys_to_delete.append(token)
            
    for token in keys_to_delete:
        del setup_tokens[token]
        changed = True
        
    if changed:
        save_data(data)
        print(f"[DEBUG] Đã xóa {len(keys_to_delete)} token hết hạn.")

def convert_time_format(time_str, carrier):
    try:
        if carrier == "jt":
            time_part, date_part = time_str.split(" ")
            dt = datetime.datetime.strptime(date_part, "%Y-%m-%d")
            return f"{time_part} {dt.strftime('%d/%m/%Y')}"
    except Exception:
        return time_str
    return time_str

def scrape_spx(tracking_number):
    print(f"\n[DEBUG SPX] Bắt đầu cào dữ liệu SPX cho mã: {tracking_number}")
    url = "https://spx.vn/shipment/order/open/order/get_order_info"
    params = {
        "spx_tn": tracking_number,
        "language_code": "vi"
    }
    
    headers = {
        "source": "mobile",
        "referer": f"https://spx.vn/m/track?{quote_plus(tracking_number)}",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "accept": "application/json, text/plain, */*"
    }
    
    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        
        if res.status_code != 200:
            print(f"[DEBUG SPX] HTTP Status Code: {res.status_code}")
            return None

        data = res.json()
        if data.get("retcode") != 0:
            print(f"[DEBUG SPX] Lỗi từ API: {data.get('message', 'Không xác định')}")
            return None
            
        tracking_info = data.get("data", {}).get("sls_tracking_info", {})
        records = tracking_info.get("records",[])
        
        if not records:
            print("[DEBUG SPX] Không tìm thấy dữ liệu đơn hàng này.")
            return None
            
        history =[]
        for record in records:
            timestamp = record.get("actual_time")
            if timestamp:
                dt = datetime.datetime.fromtimestamp(timestamp)
                time_str = dt.strftime("%H:%M:%S %d/%m/%Y")
            else:
                time_str = "Thời gian không xác định"
                
            status = record.get("description") or record.get("tracking_name") or "Đang cập nhật"
            history.append({"status": status, "time": time_str})
            
        if not history:
            return None
            
        history.reverse()
        
        last_status = history[-1]["status"].lower()
        completed_keywords =["giao hàng thành công", "đã được giao", "đã ký nhận", "delivered"]
        completed = any(kw in last_status for kw in completed_keywords)
        
        print(f"[DEBUG SPX] Trạng thái cuối: {history[-1]['status']} | Hoàn thành: {completed}")
        return {"history": history, "completed": completed}

    except Exception as e:
        print(f"[DEBUG SPX] Exception Code SPX: {str(e)}")
        return None

def scrape_jt(tracking_number, phone):
    print(f"\n[DEBUG JT] Bắt đầu cào dữ liệu JT cho mã: {tracking_number} | Phone: {phone}")
    url = f"https://jtexpress.vn/vi/tracking?type=track&billcode={quote_plus(tracking_number)}&cellphone={quote_plus(phone)}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        res = requests.get(url, headers=headers, timeout=10)
        
        print(f"[DEBUG JT] HTTP Status Code: {res.status_code}")
        
        if res.status_code != 200:
            print(f"[DEBUG JT] Bị chặn hoặc lỗi mạng. HTML: {res.text[:500]}")
            return None

        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.find_all('div', class_='result-vandon-item')
        
        if not items:
            print("[DEBUG JT] Không tìm thấy thẻ div 'result-vandon-item' trong HTML")
            return None
            
        print(f"[DEBUG JT] Tìm thấy {len(items)} bản ghi lịch sử HTML")
        
        history =[]
        for item in items:
            spans = item.find_all('span')
            if len(spans) >= 2:
                time_part = spans[0].get_text(strip=True)
                date_part = spans[1].get_text(strip=True)
                raw_time = f"{time_part} {date_part}"
                
                divs = item.find_all('div')
                status = ""
                for div in divs:
                    if not div.find('div') and not div.find('span') and not div.find('svg'):
                        text = div.get_text(strip=True)
                        if text:
                            status = text
                if status:
                    history.append({"status": status, "time": convert_time_format(raw_time, "jt")})
                    
        if not history:
            print("[DEBUG JT] Không trích xuất được text lịch sử từ HTML")
            return None
            
        history.reverse()
        completed = any("Đơn hàng đã ký nhận" in h["status"] for h in history)
        
        print(f"[DEBUG JT] Trạng thái cuối: {history[-1]['status']} | Completed: {completed}")
        return {"history": history, "completed": completed}
    except Exception as e:
        print(f"[DEBUG JT] Exception Code JT: {str(e)}")
        return None

async def async_send_discord(channel_id, text):
    try:
        cid = int(channel_id)
        channel = discord_client.get_channel(cid)
        if not channel:
            try:
                channel = await discord_client.fetch_channel(cid)
            except Exception:
                pass
        
        if channel:
            await channel.send(text)
        else:
            user = discord_client.get_user(cid)
            if not user:
                try:
                    user = await discord_client.fetch_user(cid)
                except Exception:
                    pass
            if user:
                await user.send(text)
    except Exception as e:
        pass

def send_raw_message(target_id, platform, text):
    if platform == "telegram":
        try:
            bot.send_message(target_id, text, parse_mode="Markdown")
        except Exception:
            pass
    elif platform == "discord":
        if discord_loop and discord_loop.is_running():
            asyncio.run_coroutine_threadsafe(async_send_discord(target_id, text), discord_loop)

def send_update_message(target_id, platform, status, time_str):
    text = f"**{status}**\n---\n*{time_str}*"
    send_raw_message(target_id, platform, text)

def process_new_updates(target_id, platform, track_num, info, res):
    saved_time = info["last_time"]
    saved_status = info["last_status"]
    
    new_updates =[]
    
    latest = res["history"][-1]
    
    if latest["time"] != saved_time or latest["status"] != saved_status:
        new_updates.append(latest)

    if new_updates:
        for h in new_updates:
            send_update_message(target_id, platform, h["status"], h["time"])
            time.sleep(1) 
        
        info["last_status"] = latest["status"]
        info["last_time"] = latest["time"]
        
        if res["completed"]:
            return "DELETE"
        return True
    
    if res["completed"]:
        return "DELETE"
        
    return False

def check_spx_job():
    data = load_data()
    changed = False
    for key, tracks in list(data.get("tracking", {}).items()):
        platform = "discord" if key.startswith("discord_") else "telegram"
        target_id = key.replace("discord_", "").replace("telegram_", "")
        
        to_delete =[]
        for track_num, info in list(tracks.items()):
            if info["carrier"] == "spx":
                res = scrape_spx(track_num)
                if res:
                    status = process_new_updates(target_id, platform, track_num, info, res)
                    if status == "DELETE":
                        to_delete.append(track_num)
                    elif status == True:
                        changed = True
                        
        for track_num in to_delete:
            del tracks[track_num]
            changed = True
            send_raw_message(target_id, platform, f"✅ Đơn hàng **{track_num}** đã giao thành công và được gỡ khỏi danh sách theo dõi.")
            
    if changed:
        save_data(data)

def check_jt_job():
    data = load_data()
    changed = False
    for key, tracks in list(data.get("tracking", {}).items()):
        platform = "discord" if key.startswith("discord_") else "telegram"
        target_id = key.replace("discord_", "").replace("telegram_", "")
        
        to_delete =[]
        for track_num, info in list(tracks.items()):
            if info["carrier"] == "jt":
                res = scrape_jt(track_num, info.get("phone", ""))
                if res:
                    status = process_new_updates(target_id, platform, track_num, info, res)
                    if status == "DELETE":
                        to_delete.append(track_num)
                    elif status == True:
                        changed = True
                        
        for track_num in to_delete:
            del tracks[track_num]
            changed = True
            send_raw_message(target_id, platform, f"✅ Đơn hàng **{track_num}** đã giao thành công và được gỡ khỏi danh sách theo dõi.")
            
    if changed:
        save_data(data)

cleanup_expired_tokens()
scheduler.add_job(cleanup_expired_tokens, 'cron', hour='0,12', minute='0')
scheduler.add_job(check_spx_job, 'cron', minute='*/15')
scheduler.add_job(check_jt_job, 'cron', minute='*/10')
scheduler.start()

class ResetViewDiscord(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=60)
        self.channel_id = channel_id

    @discord.ui.button(label="Thôi bỏ đi", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Đã hủy thao tác.", view=None)

    @discord.ui.button(label="Có chứ", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        key = f"discord_{self.channel_id}"
        if key in data["tracking"]:
            del data["tracking"][key]
            save_data(data)
        await interaction.response.edit_message(content="Đã xóa thành công toàn bộ tiến trình hiện tại, chạy lại lệnh /setup để thêm lại", view=None)

@discord_client.event
async def on_ready():
    global discord_loop
    discord_loop = asyncio.get_running_loop()
    await tree.sync()
    print(f"Discord bot logged in as {discord_client.user}")

@tree.command(name="setup", description="Bắt đầu setup theo dõi đơn hàng")
async def slash_setup(interaction: discord.Interaction):
    data = load_data()
    channel_id = str(interaction.channel_id)
    token = str(uuid.uuid4())
    
    data["setup_tokens"][token] = {
        "target_id": channel_id,
        "platform": "discord",
        "expires_at": time.time() + 300 
    }
    save_data(data)
    
    setup_link = f"{WEB_DOMAIN}/setup?token={token}"
    text = (
        "**Chào mừng bạn đến với HoyuTracking!**\n"
        "Vui lòng truy cập link bên dưới để bắt đầu setup và theo dõi!\n\n"
        "---\n"
        f"**👉 BẮT ĐẦU SETUP**\n{setup_link}\n"
        "---\n\n"
        "*Link có hạn sử dụng 5 phút*"
    )
    await interaction.response.send_message(text)

@tree.command(name="start", description="Bắt đầu setup theo dõi đơn hàng")
async def slash_start(interaction: discord.Interaction):
    data = load_data()
    channel_id = str(interaction.channel_id)
    token = str(uuid.uuid4())
    
    data["setup_tokens"][token] = {
        "target_id": channel_id,
        "platform": "discord",
        "expires_at": time.time() + 300 
    }
    save_data(data)
    
    setup_link = f"{WEB_DOMAIN}/setup?token={token}"
    text = (
        "**Chào mừng bạn đến với HoyuTracking!**\n"
        "Vui lòng truy cập link bên dưới để bắt đầu setup và theo dõi!\n\n"
        "---\n"
        f"**👉 BẮT ĐẦU SETUP**\n{setup_link}\n"
        "---\n\n"
        "*Link có hạn sử dụng 5 phút*"
    )
    await interaction.response.send_message(text)

@tree.command(name="reset", description="Xóa TOÀN BỘ tiến trình theo dõi hiện tại")
async def slash_reset(interaction: discord.Interaction):
    view = ResetViewDiscord(str(interaction.channel_id))
    await interaction.response.send_message("Bạn có chắc muốn xóa **TOÀN BỘ tiến trình theo dõi** hiện tại không?", view=view)

@discord_client.event
async def on_message(message):
    if message.author.bot:
        return
        
    if message.content.startswith('/setup') or message.content.startswith('/start'):
        data = load_data()
        channel_id = str(message.channel.id)
        token = str(uuid.uuid4())
        
        data["setup_tokens"][token] = {
            "target_id": channel_id,
            "platform": "discord",
            "expires_at": time.time() + 300 
        }
        save_data(data)
        
        setup_link = f"{WEB_DOMAIN}/setup?token={token}"
        text = (
            "**Chào mừng bạn đến với HoyuTracking!**\n"
            "Vui lòng truy cập link bên dưới để bắt đầu setup và theo dõi!\n\n"
            "---\n"
            f"**👉 BẮT ĐẦU SETUP**\n{setup_link}\n"
            "---\n\n"
            "*Link có hạn sử dụng 5 phút*"
        )
        await message.channel.send(text)
        
    elif message.content.startswith('/reset'):
        view = ResetViewDiscord(str(message.channel.id))
        await message.channel.send("Bạn có chắc muốn xóa **TOÀN BỘ tiến trình theo dõi** hiện tại không?", view=view)

@bot.message_handler(commands=['setup', 'start'])
def handle_setup(message):
    data = load_data()
    chat_id = str(message.chat.id)
    token = str(uuid.uuid4())
    
    data["setup_tokens"][token] = {
        "target_id": chat_id,
        "platform": "telegram",
        "expires_at": time.time() + 300 
    }
    save_data(data)
    
    setup_link = f"{WEB_DOMAIN}/setup?token={token}"
    text = (
        "**Chào mừng bạn đến với HoyuTracking!**\n"
        "Vui lòng truy cập link bên dưới để bắt đầu setup và theo dõi!\n\n"
        "---\n"
        f"**👉[BẮT ĐẦU SETUP]({setup_link})**\n"
        "---\n\n"
        "*Link có hạn sử dụng 5 phút*"
    )
    bot.reply_to(message, text, parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(commands=['reset'])
def handle_reset(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Thôi bỏ đi", callback_data="reset_cancel"),
        InlineKeyboardButton("Có chứ", callback_data="reset_confirm")
    )
    bot.reply_to(
        message, 
        "Bạn có chắc muốn xóa **TOÀN BỘ tiến trình theo dõi** hiện tại không?", 
        parse_mode="Markdown", 
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data in["reset_cancel", "reset_confirm"])
def callback_reset(call):
    if call.data == "reset_cancel":
        bot.edit_message_text("Đã hủy thao tác.", chat_id=call.message.chat.id, message_id=call.message.message_id)
    elif call.data == "reset_confirm":
        data = load_data()
        key = f"telegram_{call.message.chat.id}"
        legacy_key = str(call.message.chat.id)
        changed = False
        if key in data["tracking"]:
            del data["tracking"][key]
            changed = True
        if legacy_key in data["tracking"]:
            del data["tracking"][legacy_key]
            changed = True
            
        if changed:
            save_data(data)
            
        bot.edit_message_text(
            "Đã xóa thành công toàn bộ tiến trình hiện tại, chạy lại lệnh /setup để thêm lại", 
            chat_id=call.message.chat.id, 
            message_id=call.message.message_id
        )

def send_backlog_thread(target_id, platform, track_num, history, completed):
    send_raw_message(target_id, platform, f"📦 **BẮT ĐẦU THEO DÕI ĐƠN HÀNG: {track_num}** 📦")
    time.sleep(2)
    
    for h in history:
        send_update_message(target_id, platform, h['status'], h['time'])
        time.sleep(2)
        
    if completed:
        send_raw_message(target_id, platform, f"✅ Đơn hàng **{track_num}** đã giao thành công. Không thêm vào danh sách theo dõi.")

@app.route('/setup')
def setup_page():
    token = request.args.get('token')
    if not token:
        return "Missing token", 400
        
    data = load_data()
    token_info = data["setup_tokens"].get(token)
    
    if not token_info or time.time() > token_info.get("expires_at", 0):
        if token in data.get("setup_tokens", {}):
            del data["setup_tokens"][token]
            save_data(data)
        return "Link đã hết hạn hoặc không hợp lệ. Vui lòng gõ lại /setup trong bot.", 403
        
    with open("setup.html", "r", encoding="utf-8") as f:
        html = f.read()
    return render_template_string(html, token=token)

@app.route('/api/save_setup', methods=['POST'])
def save_setup():
    req_data = request.json
    print(f"\n[DEBUG API] Nhận request thêm đơn: {req_data}")
    
    token = req_data.get('token')
    carrier = req_data.get('carrier')
    tracking_number = req_data.get('tracking_number')
    phone = req_data.get('phone', '')

    data = load_data()
    token_info = data["setup_tokens"].get(token)
    
    if not token_info or time.time() > token_info.get("expires_at", 0):
        if token in data.get("setup_tokens", {}):
            del data["setup_tokens"][token]
            save_data(data)
        print(f"[DEBUG API] Token không hợp lệ hoặc hết hạn: {token}")
        return jsonify({"error": "Token hết hạn"}), 403

    target_id = token_info.get("target_id", token_info.get("chat_id"))
    platform = token_info.get("platform", "telegram")
    
    result = None
    if carrier == "spx":
        result = scrape_spx(tracking_number)
    elif carrier == "jt":
        result = scrape_jt(tracking_number, phone)
        
    print(f"[DEBUG API] Kết quả scrape trả về cho /api/save_setup: {result}")
        
    if not result or not result["history"]:
        return jsonify({"error": "Không tìm thấy thông tin đơn hàng này trên hệ thống."}), 404

    key = f"{platform}_{target_id}"
    if key not in data["tracking"]:
        data["tracking"][key] = {}
            
    latest_item = result["history"][-1]
    
    if not result["completed"]:
        data["tracking"][key][tracking_number] = {
            "carrier": carrier,
            "phone": phone,
            "last_status": latest_item["status"],
            "last_time": latest_item["time"],
            "completed": False
        }
        save_data(data)
    
    if token in data["setup_tokens"]:
        del data["setup_tokens"][token]
        save_data(data)
    
    threading.Thread(target=send_backlog_thread, args=(target_id, platform, tracking_number, result["history"], result["completed"]), daemon=True).start()
    
    return jsonify({"message": f"Tìm thấy đơn hàng! Trạng thái hiện tại: {latest_item['status']}"})

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

def run_telegram_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=run_telegram_bot, daemon=True).start()
    if DISCORD_BOT_TOKEN:
        discord_client.run(DISCORD_BOT_TOKEN)
    else:
        while True:
            time.sleep(1)