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

def update_keys():
    updated = {}
    for category, urls in sources.items():
        if isinstance(urls, str):
            urls = [urls]
        new_keys = []
        for url in urls:
            try:
                r = requests.get(url, timeout=10)
                lines = r.text.splitlines()
                for line in lines:
                    key = line.strip()
                    if key and key not in goods.get(category, []):
                        new_keys.append(key)
            except Exception as e:
                print(f"Ошибка при загрузке из {url}: {e}")
        if category not in goods:
            goods[category] = []
        goods[category].extend(new_keys)
        updated[category] = len(new_keys)
    save_goods()
    return updated
def get_payment_markup(category, url=None):
    price = prices.get(category, 0)
    markup = types.InlineKeyboardMarkup()
    if url:
        markup.add(types.InlineKeyboardButton("💳 Оплатить", url=url))
    else:
        payment_url = f"https://yoomoney.ru/quickpay/shop-widget?writer=seller&targets=Покупка+{category}&default-sum={price}&button-text=11&account=4100119168683765"
        markup.add(types.InlineKeyboardButton("💳 Оплатить разово", url=payment_url))
    return markup

def get_subscription_markup(category):
    price = sub_prices.get(category, 0)
    markup = types.InlineKeyboardMarkup()
    payment_url = f"https://yoomoney.ru/quickpay/shop-widget?writer=seller&targets=Подписка+{category}&default-sum={price}&button-text=11&account=4100119168683765"
    markup.add(types.InlineKeyboardButton("📅 Оформить подписку", url=payment_url))
    return markup

def create_payment_link(amount, description, return_url, user_id=None, category=None,
                        customer_email="customer@example.com", customer_phone="+79990001122"):
    url = "https://api.yookassa.ru/v3/payments"
    headers = {
        "Content-Type": "application/json",
        "Idempotence-Key": str(uuid.uuid4())
    }
    auth = ("1097837", "live_ae2ilIIqpXj4eE56lpQb8bLVIGkCIFbtlG7RO_RrO_k")

    data = {
        "amount": {"value": f"{amount:.2f}" if isinstance(amount, float) else str(amount), "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description,
        "receipt": {
            "customer": {
                "email": customer_email,
                "phone": customer_phone
            },
            "items": [
                {
                    "description": description,
                    "quantity": "1.00",
                    "amount": {"value": f"{amount:.2f}" if isinstance(amount, float) else str(amount), "currency": "RUB"},
                    "vat_code": 1
                }
            ]
        }
    }

    try:
        r = requests.post(url, headers=headers, json=data, auth=auth)
        if r.status_code in (200, 201):
            result = r.json()
            print("YooKassa API response:", result)
            payment_id = result.get("id")
            confirmation = result.get("confirmation")
            if confirmation and "confirmation_url" in confirmation:
                confirmation_url = confirmation["confirmation_url"]
                if user_id and category:
                    pending_payments[payment_id] = {"user_id": user_id, "category": category, "time": time.time(), "type": "one_time"}
                return confirmation_url
            else:
                print("Ошибка: В ответе отсутствует поле confirmation_url.")
                return None
        else:
            print(f"Ошибка при создании ссылки: {r.status_code} {r.text}")
            return None
    except Exception as e:
        print("Исключение при создании ссылки:", e)
        return None

def create_subscription_payment_link(amount, description, return_url, user_id, category,
                                    customer_email="customer@example.com", customer_phone="+79990001122"):
    url = "https://api.yookassa.ru/v3/payments"
    headers = {
        "Content-Type": "application/json",
        "Idempotence-Key": str(uuid.uuid4())
    }
    auth = ("1097837", "live_ae2ilIIqpXj4eE56lpQb8bLVIGkCIFbtlG7RO_RrO_k")

    data = {
        "amount": {"value": f"{amount:.2f}" if isinstance(amount, float) else str(amount), "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description,
        "receipt": {
            "customer": {
                "email": customer_email,
                "phone": customer_phone
            },
            "items": [
                {
                    "description": description,
                    "quantity": "1.00",
                    "amount": {"value": f"{amount:.2f}" if isinstance(amount, float) else str(amount), "currency": "RUB"},
                    "vat_code": 1
                }
            ]
        }
    }

    try:
        r = requests.post(url, headers=headers, json=data, auth=auth)
        if r.status_code in (200, 201):
            result = r.json()
            payment_id = result.get("id")
            confirmation = result.get("confirmation")
            if confirmation and "confirmation_url" in confirmation:
                confirmation_url = confirmation["confirmation_url"]
                if user_id and category:
                    pending_payments[payment_id] = {"user_id": user_id, "category": category, "type": "subscription", "time": time.time()}
                return confirmation_url
            else:
                print("Ошибка: В ответе отсутствует поле confirmation_url.")
                return None
        else:
            print(f"Ошибка при создании ссылки на подписку: {r.status_code} {r.text}")
            return None
    except Exception as e:
        print("Исключение при создании ссылки на подписку:", e)
        return None

@bot.message_handler(commands=["start"])
def start(msg):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for c in goods:
        kb.add(types.KeyboardButton(f"🛍 Купить {c} ({prices[c]}₽)"))
        kb.add(types.KeyboardButton(f"📅 Подписка {c} ({sub_prices[c]}₽/мес)"))
    if msg.from_user.id == ADMIN_ID:
        kb.add(types.KeyboardButton("🔄 Обновить ключи"))
        kb.add(types.KeyboardButton("📦 Остатки"))
    bot.send_message(msg.chat.id, "👋 Добро пожаловать в *KeySpace* — магазин цифровых ключей!\n\nВыберите нужную категорию:", parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text.startswith("🛍 Купить "))
def buy(msg):
    category = msg.text.replace("🛍 Купить ", "").split(" (")[0]
    if category not in goods:
        return bot.send_message(msg.chat.id, "❌ Категория не найдена.")
    if not goods[category]:
        return bot.send_message(msg.chat.id, f"😞 Нет ключей для {category}.")

    link = create_payment_link(
        prices[category],
        f"Покупка {category}",
        "https://t.me/ULBA_bot",
        msg.from_user.id,
        category,
        customer_email=f"user{msg.from_user.id}@example.com",
        customer_phone="+79990001122"
    )
    if link:
        bot.send_message(msg.chat.id, f"Вы выбрали *{category}*. Стоимость: *{prices[category]}₽*.\n\n🔗 Нажмите кнопку ниже для оплаты:", parse_mode="Markdown", reply_markup=get_payment_markup(category, link))
    else:
        bot.send_message(msg.chat.id, "⚠️ Не удалось создать ссылку.")

@bot.message_handler(func=lambda m: m.text.startswith("📅 Подписка "))
def subscribe(msg):
    category = msg.text.replace("📅 Подписка ", "").split(" (")[0]
    if category not in goods:
        return bot.send_message(msg.chat.id, "❌ Категория не найдена.")

    link = create_subscription_payment_link(
        sub_prices[category],
        f"Подписка на {category} (ежемесячно)",
        "https://t.me/ULBA_bot",
        msg.from_user.id,
        category,
        customer_email=f"user{msg.from_user.id}@example.com",
        customer_phone="+79990001122"
    )
    if link:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💳 Оплатить подписку", url=link))
        bot.send_message(msg.chat.id, f"Вы выбрали подписку на *{category}* за *{sub_prices[category]}₽/мес*.\n\nНажмите кнопку для оплаты:", parse_mode="Markdown", reply_markup=kb)
    else:
        bot.send_message(msg.chat.id, "⚠️ Не удалось создать ссылку на подписку.")

@bot.message_handler(func=lambda m: m.text == "🔄 Обновить ключи" and m.from_user.id == ADMIN_ID)
def admin_update(msg):
    updated = update_keys()
    text = "Обновление ключей завершено:\n"
    for c, n in updated.items():
        text += f"• {c}: добавлено {n} ключей\n"
    bot.send_message(msg.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "📦 Остатки" and m.from_user.id == ADMIN_ID)
def admin_stock(msg):
    text = "Остатки ключей:\n"
    for c, lst in goods.items():
        text += f"• {c}: {len(lst)} ключей\n"
    bot.send_message(msg.chat.id, text)

def check_pending_payments():
    auth = ("1097837", "live_ae2ilIIqpXj4eE56lpQb8bLVIGkCIFbtlG7RO_RrO_k")
    while True:
        if not pending_payments:
            time.sleep(10)
            continue
        to_delete = []
        for payment_id, info in list(pending_payments.items()):
            user_id = info["user_id"]
            category = info["category"]
            payment_type = info.get("type", "one_time")
            try:
                url = f"https://api.yookassa.ru/v3/payments/{payment_id}"
                r = requests.get(url, auth=auth)
                if r.status_code == 200:
                    result = r.json()
                    status = result.get("status")
                    if status == "succeeded":
                        if payment_type == "one_time":
                            if goods.get(category) and goods[category]:
                                key = goods[category].pop(0)
                                save_goods()
                                try:
                                    bot.send_message(user_id, f"✅ Оплата подтверждена! Ваш ключ для *{category}*:\n`{key}`", parse_mode="Markdown")
                                except Exception as e:
                                    print(f"Ошибка отправки ключа пользователю {user_id}: {e}")
                                to_delete.append(payment_id)
                            else:
                                try:
                                    bot.send_message(user_id, f"😞 Ключи для категории {category} закончились.")
                                except:
                                    pass
                                to_delete.append(payment_id)
                        elif payment_type == "subscription":
                            now = time.time()
                            if user_id not in subscriptions:
                                subscriptions[user_id] = {}
                            subscriptions[user_id][category] = {"last_time": now}
                            save_subscriptions()
                            try:
                                bot.send_message(user_id, f"✅ Подписка на *{category}* оформлена! Ключи будут выдаваться автоматически каждый месяц.", parse_mode="Markdown")
                            except:
                                pass
                            to_delete.append(payment_id)
                    elif status in ("canceled", "failed"):
                        try:
                            bot.send_message(user_id, f"❌ Платёж {category} не прошёл.")
                        except:
                            pass
                        to_delete.append(payment_id)
                else:
                    print(f"Ошибка проверки платежа {payment_id}: {r.status_code} {r.text}")
            except Exception as e:
                print(f"Ошибка запроса статуса платежа {payment_id}: {e}")
        for pid in to_delete:
            pending_payments.pop(pid, None)
        time.sleep(30)

def check_and_deliver_subscriptions():
    while True:
        now = time.time()
        for user_id in list(subscriptions.keys()):
            for category in list(subscriptions[user_id].keys()):
                last = subscriptions[user_id][category].get("last_time", 0)
                if now - last >= 30 * 86400:  # 30 дней
                    if goods.get(category) and goods[category]:
                        key = goods[category].pop(0)
                        subscriptions[user_id][category]["last_time"] = now
                        save_goods()
                        save_subscriptions()
                        try:
                            bot.send_message(user_id, f"🔄 Ваша подписка на *{category}* обновлена!\nВаш новый ключ:\n`{key}`", parse_mode="Markdown")
                        except Exception as e:
                            print(f"Ошибка отправки ключа по подписке пользователю {user_id}: {e}")
                    else:
                        try:
                            bot.send_message(user_id, f"😞 Ключи для подписки {category} закончились.")
                        except:
                            pass
        time.sleep(3600)

if __name__ == "__main__":
    threading.Thread(target=check_pending_payments, daemon=True).start()
    threading.Thread(target=check_and_deliver_subscriptions, daemon=True).start()
    bot.infinity_polling()