import telebot
import json
import os
import requests
import time
import threading
import uuid
from telebot import types
from datetime import datetime
import re

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

def clean_html(text):
    return re.sub(r"<[^>]+>", "", text)

def is_valid_key(line):
    line = clean_html(line.strip())
    if not line or len(line) > 200:
        return False
    bad_patterns = ["<html", "<!doctype", "not found", "error", "apache", "server at", "404"]
    return not any(x in line.lower() for x in bad_patterns)

def extract_keys_from_text(text):
    lines = re.split(r"[\r\n\t,]+", text)
    keys = [clean_html(l.strip()) for l in lines if is_valid_key(l.strip())]
    return list(filter(lambda x: len(x) >= 10, keys))

def update_keys():
    updated = {}
    for cat, urls in sources.items():
        new_keys = []
        for url in urls:
            try:
                r = requests.get(url, timeout=10)
                keys = extract_keys_from_text(r.text)
                for k in keys:
                    if k not in goods.get(cat, []):
                        new_keys.append(k)
            except Exception as e:
                print(f"Ошибка при загрузке из {url}: {e}")
        goods.setdefault(cat, [])
        goods[cat].extend(new_keys)
        goods[cat] = list(dict.fromkeys(goods[cat]))  # удаление дубликатов
        updated[cat] = len(new_keys)
    save_goods()
    return updated

def get_payment_markup(category, link):
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
    if r.status_code in (200,201):
        res = r.json()
        conf = res.get("confirmation", {})
        link = conf.get("confirmation_url")
        pid = res.get("id")
        if link and pid:
            tp = "subscription" if subscription else "one_time"
            pending_payments[pid] = {"user_id": user_id, "category": category, "time": time.time(), "type": tp}
            return link
    print("Ошибка создания оплаты:", r.status_code, r.text)
    return None

@bot.message_handler(commands=["start"])
def cmd_start(m):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for c in goods:
        kb.add(f"🛍 Купить {c} ({prices[c]}₽)", f"📅 Подписка {c} ({sub_prices[c]}₽/мес)")
    if m.from_user.id == ADMIN_ID:
        kb.add("🔄 Обновить ключи", "📦 Остатки")
    bot.send_message(m.chat.id, "Выберите:", reply_markup=kb)

@bot.message_handler(func=lambda v: v.text.startswith("🛍 Купить "))
def cmd_buy(m):
    cat = m.text.split()[2]
    valid_keys = [k for k in goods.get(cat, []) if is_valid_key(k)]
    if not valid_keys:
        return bot.reply_to(m, "Нет ключей сейчас.")
    link = create_payment_link(prices[cat], f"Покупка {cat}", "https://t.me/ULBA_bot", m.from_user.id, cat)
    if link:
        bot.send_message(m.chat.id, f"Купить {cat} за {prices[cat]}₽", reply_markup=get_payment_markup(cat, link))
    else:
        bot.send_message(m.chat.id, "Ошибка, попробуйте позже.")

@bot.message_handler(func=lambda v: v.text.startswith("📅 Подписка "))
def cmd_sub(m):
    cat = m.text.split()[1]
    link = create_payment_link(sub_prices[cat], f"Подписка {cat}", "https://t.me/ULBA_bot", m.from_user.id, cat, subscription=True)
    if link:
        bot.send_message(m.chat.id, f"Подписка {cat} за {sub_prices[cat]}₽/мес", reply_markup=get_payment_markup(cat, link))
    else:
        bot.send_message(m.chat.id, "Ошибка.")

@bot.message_handler(func=lambda v: v.text=="🔄 Обновить ключи" and v.from_user.id==ADMIN_ID)
def cmd_update(m):
    upd = update_keys()
    txt = "Обновлено:\n" + "\n".join(f"{c}: +{n}" for c,n in upd.items())
    bot.send_message(m.chat.id, txt)

@bot.message_handler(func=lambda v: v.text=="📦 Остатки" and v.from_user.id==ADMIN_ID)
def cmd_stock(m):
    txt = "Остатки:\n" + "\n".join(f"{c}: {len([k for k in goods.get(c, []) if is_valid_key(k)])}" for c in goods)
    bot.send_message(m.chat.id, txt)

def check_payments():
    auth = ("1097837", "live_ae2ilIIqpXj4eE56lpQb8bLVIGkCIFbtlG7RO_RrO_k")
    while True:
        if not pending_payments:
            time.sleep(5)
            continue
        for pid, info in list(pending_payments.items()):
            r = requests.get(f"https://api.yookassa.ru/v3/payments/{pid}", auth=auth)
            if r.status_code==200:
                st = r.json().get("status")
                uid, cat, tp = info["user_id"], info["category"], info["type"]
                if st=="succeeded":
                    valid_keys = [k for k in goods.get(cat, []) if is_valid_key(k)]
                    if tp=="one_time" and valid_keys:
                        key = valid_keys[0]
                        goods[cat].remove(key)
                        save_goods()
                        bot.send_message(uid, f"✅ Ваш ключ: `{key}`", parse_mode="Markdown")
                    elif tp == "subscription":
                        subscriptions.setdefault(str(uid), {})[cat] = {"last_time": time.time()}
                        save_subscriptions()
                        bot.send_message(uid, f"✅ Подписка на {cat} оформлена.")
                    pending_payments.pop(pid,None)
                elif st in ("canceled","failed"):
                    bot.send_message(uid, "❌ Платёж не прошёл.")
                    pending_payments.pop(pid,None)
        time.sleep(20)

def deliver_subs():
    while True:
        now = time.time()
        for uid, cats in subscriptions.items():
            for cat, data in cats.items():
                if now - data["last_time"] >= 30*86400:
                    valid_keys = [k for k in goods.get(cat, []) if is_valid_key(k)]
                    if valid_keys:
                        key = valid_keys[0]
                        goods[cat].remove(key)
                        save_goods()
                        subscriptions[uid][cat]["last_time"] = now
                        save_subscriptions()
                        bot.send_message(int(uid), f"🆕 Новый ключ по подписке {cat}:\n`{key}`", parse_mode="Markdown")
        time.sleep(3600)

if __name__ == "__main__":
    threading.Thread(target=check_payments, daemon=True).start()
    threading.Thread(target=deliver_subs, daemon=True).start()
    bot.infinity_polling()