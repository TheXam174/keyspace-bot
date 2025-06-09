import telebot
import json
import os
import requests
import time
import threading
import uuid
from telebot import types
from datetime import datetime

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
    bad = ["<html", "<!doctype", "<!DOCTYPE", "404", "not found", "error", "apache", "nginx", "server", "<script"]
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
    welcome = (
        "👋 Привет! Я бот-магазин цифровых ключей:\n\n"
        "🛍 *Разовая покупка ключа* — от 19₽\n"
        "📅 *Подписка с автодоставкой* — от 149₽/мес\n\n"
        "🔐 Категории:\n"
        "• VPN — 19₽ / 149₽/мес\n"
        "• VPN Premium — 39₽ / 199₽/мес\n"
        "• GPT — 49₽ / 299₽/мес\n\n"
        "Выберите ниже нужный вариант:"
    )
    bot.send_message(m.chat.id, welcome, reply_markup=kb, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text.startswith("🛍 Купить "))
def cmd_buy(m):
    text = m.text.split()
    cat = " ".join(text[2:-1]) if len(text) > 3 else text[2]
    if not goods.get(cat):
        return bot.send_message(m.chat.id, "🚫 Нет доступных ключей.")
    price = prices.get(cat)
    link = create_payment_link(price, f"Покупка {cat}", "https://t.me/ULBA_bot", m.from_user.id, cat)
    if link:
        bot.send_message(m.chat.id, f"🔸 Оплата за {cat} — {price}₽", reply_markup=get_payment_markup(link))
    else:
        bot.send_message(m.chat.id, "Ошибка, попробуйте позже.")

@bot.message_handler(func=lambda m: m.text.startswith("📅 Подписка "))
def cmd_sub(m):
    text = m.text.split()
    cat = " ".join(text[1:-1]) if len(text) > 3 else text[1]
    price = sub_prices.get(cat)
    link = create_payment_link(price, f"Подписка {cat}", "https://t.me/ULBA_bot", m.from_user.id, cat, subscription=True)
    if link:
        bot.send_message(m.chat.id, f"🔸 Подписка {cat} — {price}₽/мес", reply_markup=get_payment_markup(link))
    else:
        bot.send_message(m.chat.id, "Ошибка, попробуйте позже.")

@bot.message_handler(func=lambda m: m.text == "🔄 Обновить ключи" and m.from_user.id == ADMIN_ID)
def cmd_update(m):
    upd = update_keys()
    txt = "✅ Обновление завершено:\n" + "\n".join(f"{k}: +{v}" for k, v in upd.items())
    bot.send_message(m.chat.id, txt)

@bot.message_handler(func=lambda m: m.text == "📦 Остатки" and m.from_user.id == ADMIN_ID)
def cmd_stock(m):
    txt = "📦 Текущий остаток ключей:\n" + "\n".join(f"{k}: {len(goods.get(k, []))}" for k in goods)
    bot.send_message(m.chat.id, txt)

def check_payments():
    auth = ("1097837", "live_ae2ilIIqpXj4eE56lpQb8bLVIGkCIFbtlG7RO_RrO_k")
    while True:
        if not pending_payments:
            time.sleep(5)
            continue
        for pid, info in list(pending_payments.items()):
            r = requests.get(f"https://api.yookassa.ru/v3/payments/{pid}", auth=auth)
            if r.status_code == 200:
                data = r.json()
                status = data.get("status")
                uid, cat, tp = info["user_id"], info["category"], info["type"]
                if status == "succeeded":
                    if tp == "one_time":
                        if goods.get(cat):
                            key = goods[cat].pop(0); save_goods()
                            bot.send_message(uid, f"✅ Ваш ключ: `{key}`", parse_mode="Markdown")
                    else:
                        subscriptions.setdefault(str(uid), {})[cat] = {"last_time": time.time()}
                        save_subscriptions()
                        bot.send_message(uid, f"✅ Подписка на {cat} активирована.")
                    pending_payments.pop(pid, None)
                elif status in ("canceled", "failed"):
                    bot.send_message(uid, "❌ Платёж не прошёл.")
                    pending_payments.pop(pid, None)
        time.sleep(15)

def deliver_subs():
    while True:
        now = time.time()
        for uid, cats in subscriptions.items():
            for cat, data in cats.items():
                if now - data["last_time"] >= 30 * 86400:
                    if goods.get(cat):
                        key = goods[cat].pop(0); save_goods()
                        subscriptions[uid][cat]["last_time"] = now; save_subscriptions()
                        bot.send_message(int(uid), f"🆕 Новый ключ по подписке {cat}:\n`{key}`", parse_mode="Markdown")
        time.sleep(3600)

if __name__ == "__main__":
    threading.Thread(target=check_payments, daemon=True).start()
    threading.Thread(target=deliver_subs, daemon=True).start()
    bot.infinity_polling()