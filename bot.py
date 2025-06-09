import telebot
import json
import os
import requests
import time
import threading
import uuid
from telebot import types
from datetime import datetime

# 🔑 Токен, админ, username
TOKEN = "7584995126:AAFY5RMpeJW2pJzSy2ul6uaSslB5Jnyhxh4"
ADMIN_ID = 6668575839
bot = telebot.TeleBot(TOKEN)

# 🗂️ Файлы
goods_file = "goods.json"
subs_file = "subscriptions.json"

# 🔗 Источники
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

# 💵 Цены
prices = {"VPN": 19, "VPN Premium": 39, "GPT": 49}
sub_prices = {"VPN": 149, "VPN Premium": 199, "GPT": 299}

# 📦 Данные
goods = {k: [] for k in prices}
subscriptions = {}
pending_payments = {}

if os.path.exists(goods_file):
    with open(goods_file, "r", encoding="utf-8") as f:
        goods.update(json.load(f))

if os.path.exists(subs_file):
    with open(subs_file, "r", encoding="utf-8") as f:
        subscriptions = json.load(f)

def save_goods():
    with open(goods_file, "w", encoding="utf-8") as f:
        json.dump(goods, f, ensure_ascii=False, indent=2)

def save_subscriptions():
    with open(subs_file, "w", encoding="utf-8") as f:
        json.dump(subscriptions, f, ensure_ascii=False, indent=2)

# 🧼 Фильтрация
def is_valid_key(line):
    line = line.strip()
    if len(line) > 200:
        return False
    bad = ["<html", "<!doctype", "404", "not found", "error", "<script", "apache", "server", "nginx"]
    return not any(x in line.lower() for x in bad)

# 🔄 Обновление
def update_keys():
    updated = {}
    for cat, urls in sources.items():
        new_keys = []
        for url in urls:
            try:
                r = requests.get(url, timeout=10)
                for line in r.text.splitlines():
                    k = line.strip()
                    if is_valid_key(k) and k not in goods[cat]:
                        new_keys.append(k)
            except Exception as e:
                print(f"Ошибка при загрузке из {url}: {e}")
        goods[cat].extend(new_keys)
        updated[cat] = len(new_keys)
    save_goods()
    return updated

# 💳 YooKassa
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
        link = res.get("confirmation", {}).get("confirmation_url")
        pid = res.get("id")
        if link and pid:
            tp = "subscription" if subscription else "one_time"
            pending_payments[pid] = {"user_id": user_id, "category": category, "time": time.time(), "type": tp}
            return link
    return None

def get_payment_markup(link):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Оплатить", url=link))
    return markup

# 📲 Команды
@bot.message_handler(commands=["start"])
def cmd_start(m):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for cat in prices:
        kb.add(f"🛍 Купить: {cat} ({prices[cat]}₽)", f"📅 Подписка: {cat} ({sub_prices[cat]}₽/мес)")
    if m.from_user.id == ADMIN_ID:
        kb.add("🔄 Обновить ключи", "📦 Остатки")
    text = (
        "👋 Привет! Я бот-магазин цифровых ключей:\n\n"
        "🛍 *Разовая покупка ключа* — от 19₽\n"
        "📅 *Подписка с автодоставкой* — от 149₽/мес\n\n"
        "🔐 Категории:\n"
        "• VPN — 19₽ / 149₽/мес\n"
        "• VPN Premium — 39₽ / 199₽/мес\n"
        "• GPT — 49₽ / 299₽/мес\n\n"
        "Выберите ниже нужный вариант:"
    )
    bot.send_message(m.chat.id, text, reply_markup=kb)

@bot.message_handler(func=lambda m: m.text and m.text.startswith("🛍 Купить: "))
def buy(m):
    try:
        cat = m.text.split(": ")[1].split(" (")[0]
        if not goods.get(cat):
            return bot.reply_to(m, "❌ Сейчас нет ключей в наличии.")
        link = create_payment_link(prices[cat], f"Покупка {cat}", "https://t.me/ULBA_bot", m.from_user.id, cat)
        if link:
            bot.send_message(m.chat.id, f"🔹 Купить {cat} за {prices[cat]}₽", reply_markup=get_payment_markup(link))
        else:
            bot.send_message(m.chat.id, "⚠️ Ошибка создания платежа.")
    except:
        bot.send_message(m.chat.id, "❌ Ошибка при определении категории.")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("📅 Подписка: "))
def sub(m):
    try:
        cat = m.text.split(": ")[1].split(" (")[0]
        link = create_payment_link(sub_prices[cat], f"Подписка {cat}", "https://t.me/ULBA_bot", m.from_user.id, cat, subscription=True)
        if link:
            bot.send_message(m.chat.id, f"📅 Подписка на {cat} за {sub_prices[cat]}₽/мес", reply_markup=get_payment_markup(link))
        else:
            bot.send_message(m.chat.id, "⚠️ Ошибка создания подписки.")
    except:
        bot.send_message(m.chat.id, "❌ Ошибка при определении категории.")

@bot.message_handler(func=lambda m: m.text == "🔄 Обновить ключи" and m.from_user.id == ADMIN_ID)
def cmd_update(m):
    upd = update_keys()
    txt = "✅ Обновление завершено:\n" + "\n".join(f"{c}: +{n}" for c,n in upd.items())
    bot.send_message(m.chat.id, txt)

@bot.message_handler(func=lambda m: m.text == "📦 Остатки" and m.from_user.id == ADMIN_ID)
def cmd_stock(m):
    txt = "📦 Остатки ключей:\n" + "\n".join(f"{c}: {len(goods.get(c,[]))}" for c in goods)
    bot.send_message(m.chat.id, txt)

# 🔁 Проверка платежей
def check_payments():
    auth = ("1097837", "live_ae2ilIIqpXj4eE56lpQb8bLVIGkCIFbtlG7RO_RrO_k")
    while True:
        for pid, info in list(pending_payments.items()):
            try:
                r = requests.get(f"https://api.yookassa.ru/v3/payments/{pid}", auth=auth)
                if r.status_code == 200:
                    status = r.json().get("status")
                    uid, cat, tp = info["user_id"], info["category"], info["type"]
                    if status == "succeeded":
                        if tp == "one_time":
                            if goods.get(cat):
                                key = goods[cat].pop(0)
                                save_goods()
                                bot.send_message(uid, f"✅ Ваш ключ:\n`{key}`", parse_mode="Markdown")
                        else:
                            subscriptions.setdefault(str(uid), {})[cat] = {"last_time": time.time()}
                            save_subscriptions()
                            bot.send_message(uid, f"✅ Подписка на {cat} успешно оформлена.")
                        pending_payments.pop(pid)
                    elif status in ("canceled", "failed"):
                        bot.send_message(uid, "❌ Платёж не прошёл.")
                        pending_payments.pop(pid)
            except: pass
        time.sleep(10)

# 📬 Доставка подписок
def deliver_subs():
    while True:
        now = time.time()
        for uid, cats in subscriptions.items():
            for cat, data in cats.items():
                if now - data["last_time"] >= 30 * 86400:
                    if goods.get(cat):
                        key = goods[cat].pop(0)
                        save_goods()
                        subscriptions[uid][cat]["last_time"] = now
                        save_subscriptions()
                        bot.send_message(int(uid), f"🆕 Новый ключ по подписке {cat}:\n`{key}`", parse_mode="Markdown")
        time.sleep(3600)

# ⏱️ Автообновление каждый час
def auto_update_loop():
    while True:
        update_keys()
        time.sleep(3600)

# ▶️ Запуск
if __name__ == "__main__":
    threading.Thread(target=check_payments, daemon=True).start()
    threading.Thread(target=deliver_subs, daemon=True).start()
    threading.Thread(target=auto_update_loop, daemon=True).start()
    bot.infinity_polling()
