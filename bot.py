import telebot
import json
import os
import requests
import time
import threading
import uuid
from telebot import types

TOKEN = "7584995126:AAFY5RMpeJW2pJzSy2ul6uaSslB5Jnyhxh4"
ADMIN_ID = 6668575839
bot = telebot.TeleBot(TOKEN)

goods_file = "goods.json"
subs_file = "subscriptions.json"

sources = {
    "VPN": [
        "https://raw.githubusercontent.com/dan1471/FREE-VPN/main/vpn.txt",
        "https://outlinekeys.com/api/vpn",
        "https://openkeys.net/api/vpn"
    ],
    "VPN Premium": [
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        "https://outlinekeys.com/api/premium",
        "https://openkeys.net/api/premium"
    ],
    "GPT": [
        "https://raw.githubusercontent.com/dan1471/FREE-openai-api-keys/main/keys.txt",
        "https://raw.githubusercontent.com/0xk1h0/OpenAI-API/main/key.txt",
        "https://outlinekeys.com/api/gpt",
        "https://openkeys.net/api/gpt"
    ]
}

prices = {"VPN": 19, "VPN Premium": 39, "GPT": 49}
sub_prices = {"VPN": 149, "VPN Premium": 199, "GPT": 299}

goods = {}
subscriptions = {}
pending_payments = {}

if os.path.exists(goods_file):
    with open(goods_file, "r", encoding="utf-8") as f:
        goods = json.load(f)
else:
    goods = {k: [] for k in prices}

if os.path.exists(subs_file):
    with open(subs_file, "r", encoding="utf-8") as f:
        subscriptions = json.load(f)
else:
    subscriptions = {}

def save_goods():
    with open(goods_file, "w", encoding="utf-8") as f:
        json.dump(goods, f, ensure_ascii=False, indent=2)

def save_subscriptions():
    with open(subs_file, "w", encoding="utf-8") as f:
        json.dump(subscriptions, f, ensure_ascii=False, indent=2)

def is_valid_key(line):
    line = line.strip()
    if not line or len(line) > 200:
        return False
    bad = ["<html", "<!doctype", "404", "not found", "error", "<script", "Apache/", "nginx/", "Server at", "DOCTYPE"]
    return not any(x in line.lower() for x in bad)

def update_keys():
    updated = {}
    for cat, urls in sources.items():
        new_keys = []
        for url in urls:
            try:
                r = requests.get(url, timeout=10)
                for line in r.text.splitlines():
                    k = line.strip()
                    if is_valid_key(k) and k not in goods.get(cat, []):
                        new_keys.append(k)
            except Exception as e:
                print(f"Ошибка при загрузке из {url}: {e}")
        goods.setdefault(cat, [])
        goods[cat].extend(new_keys)
        updated[cat] = len(new_keys)
    save_goods()
    return updated

def get_payment_markup(link):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Оплатить", url=link))
    return markup

def create_payment_link(amount, desc, return_url, user_id, category, subscription=False):
    url = "https://api.yookassa.ru/v3/payments"
    auth = ("1097837", "live_ae2ilIIqpXj4eE56lpQb8bLVIGkCIFbtlG7RO_RrO_k")
    headers = {"Content-Type": "application/json", "Idempotence-Key": str(uuid.uuid4())}
    data = {
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": desc,
        "receipt": {
            "customer": {"email": f"user{user_id}@example.com", "phone": "+70000000000"},
            "items": [{"description": desc, "quantity": "1.00", "amount": {"value": f"{amount:.2f}", "currency": "RUB"}, "vat_code": 1}]
        }
    }
    r = requests.post(url, headers=headers, json=data, auth=auth)
    if r.status_code in (200, 201):
        res = r.json()
        link = res.get("confirmation", {}).get("confirmation_url")
        pid = res.get("id")
        if link and pid:
            pending_payments[pid] = {
                "user_id": user_id,
                "category": category,
                "time": time.time(),
                "type": "subscription" if subscription else "one_time"
            }
            return link
    print("Ошибка оплаты:", r.status_code, r.text)
    return None

@bot.message_handler(commands=["start"])
def cmd_start(m):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for c in prices:
        kb.add(f"🛍 Купить: {c}", f"📅 Подписка: {c}")
    if m.from_user.id == ADMIN_ID:
        kb.add("🔄 Обновить ключи", "📦 Остатки")
    bot.send_message(m.chat.id, "Выберите:", reply_markup=kb)

def extract_category(text):
    for cat in prices:
        if cat in text:
            return cat
    return None

@bot.message_handler(func=lambda m: m.text.startswith("🛍 Купить"))
def buy_handler(m):
    cat = extract_category(m.text)
    if not cat:
        return bot.reply_to(m, "Категория не найдена.")
    if not goods.get(cat):
        return bot.reply_to(m, "Нет ключей в наличии.")
    amount = prices[cat]
    link = create_payment_link(amount, f"Покупка {cat}", "https://t.me/ULBA_bot", m.from_user.id, cat)
    if link:
        bot.send_message(m.chat.id, f"Купить {cat} за {amount}₽", reply_markup=get_payment_markup(link))
    else:
        bot.send_message(m.chat.id, "Ошибка создания оплаты.")

@bot.message_handler(func=lambda m: m.text.startswith("📅 Подписка"))
def sub_handler(m):
    cat = extract_category(m.text)
    if not cat:
        return bot.reply_to(m, "Категория не найдена.")
    amount = sub_prices[cat]
    link = create_payment_link(amount, f"Подписка {cat}", "https://t.me/ULBA_bot", m.from_user.id, cat, subscription=True)
    if link:
        bot.send_message(m.chat.id, f"Подписка на {cat} за {amount}₽/мес", reply_markup=get_payment_markup(link))
    else:
        bot.send_message(m.chat.id, "Ошибка создания оплаты.")

@bot.message_handler(func=lambda m: m.text == "🔄 Обновить ключи" and m.from_user.id == ADMIN_ID)
def update_handler(m):
    result = update_keys()
    msg = "Обновлено:\n" + "\n".join([f"{k}: +{v}" for k, v in result.items()])
    bot.send_message(m.chat.id, msg)

@bot.message_handler(func=lambda m: m.text == "📦 Остатки" and m.from_user.id == ADMIN_ID)
def stock_handler(m):
    msg = "Остатки:\n" + "\n".join([f"{k}: {len(goods.get(k, []))}" for k in prices])
    bot.send_message(m.chat.id, msg)

def check_payments():
    auth = ("1097837", "live_ae2ilIIqpXj4eE56lpQb8bLVIGkCIFbtlG7RO_RrO_k")
    while True:
        for pid in list(pending_payments.keys()):
            try:
                r = requests.get(f"https://api.yookassa.ru/v3/payments/{pid}", auth=auth)
                if r.status_code == 200:
                    data = r.json()
                    if data["status"] == "succeeded":
                        info = pending_payments.pop(pid)
                        uid, cat, typ = info["user_id"], info["category"], info["type"]
                        if typ == "one_time":
                            if goods.get(cat):
                                key = goods[cat].pop(0)
                                save_goods()
                                bot.send_message(uid, f"✅ Ваш ключ:\n`{key}`", parse_mode="Markdown")
                            else:
                                bot.send_message(uid, "❌ Нет ключей.")
                        else:
                            subscriptions.setdefault(str(uid), {})[cat] = {"last_time": time.time()}
                            save_subscriptions()
                            bot.send_message(uid, f"✅ Подписка на {cat} оформлена.")
                    elif data["status"] in ["canceled", "failed"]:
                        pending_payments.pop(pid)
            except Exception as e:
                print("Ошибка проверки платежа:", e)
        time.sleep(15)

def deliver_subscriptions():
    while True:
        now = time.time()
        for uid, user_subs in subscriptions.items():
            for cat, sub_data in user_subs.items():
                if now - sub_data.get("last_time", 0) >= 30 * 86400:
                    if goods.get(cat):
                        key = goods[cat].pop(0)
                        save_goods()
                        subscriptions[uid][cat]["last_time"] = now
                        save_subscriptions()
                        bot.send_message(int(uid), f"🔄 Новый ключ по подписке {cat}:\n`{key}`", parse_mode="Markdown")
        time.sleep(3600)

if __name__ == "__main__":
    threading.Thread(target=check_payments, daemon=True).start()
    threading.Thread(target=deliver_subscriptions, daemon=True).start()
    bot.infinity_polling()