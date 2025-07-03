```python
# telegram_svo_news_bot.py
import os
import logging
from dotenv import load_dotenv
from telegram import Update, ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from newsapi import NewsApiClient

# Загрузка конфигурации из .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")    # ID канала/чата для публикаций
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")  # API ключ NewsAPI

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация клиента NewsAPI
newsapi = NewsApiClient(api_key=NEWSAPI_KEY)
# Список российских проверенных источников
RELIABLE_SOURCES = [
    'tass',        # TASS
    'interfax',    # Интерфакс
    'ria',         # РИА Новости
    'regnum',      # REGNUM
    'lenta',       # Лента.ру
    'kommersant',  # Коммерсантъ
    'vedomosti',   # Ведомости
    'gazeta'       # Газета.ru
]

# Функция получения последних новостей по запросу 'СВО' за последние 2 часа
def fetch_latest_svo_news():
    articles_data = newsapi.get_everything(
        q='специальная военная операция OR СВО',
        sources=','.join(RELIABLE_SOURCES),
        language='ru',
        sort_by='publishedAt',
        page_size=5,
        from_param=os.getenv('LAST_FETCH')
    )
    return articles_data.get('articles', [])

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я публикую только проверенные новости о СВО из российских источников."
    )

# Функция публикации новостей в канал
async def post_news(context: ContextTypes.DEFAULT_TYPE):
    articles = fetch_latest_svo_news()
    if not articles:
        logger.info("Новых статей не найдено.")
        return
    for article in articles:
        title = article.get('title')
        url = article.get('url')
        published = article.get('publishedAt')
        message = f"*{title}*\n[{published}]\n[Читать далее]({url})"
        try:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            # Сохраняем метку времени последнего запроса
            os.environ['LAST_FETCH'] = published
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {e}")

# Админ-команда /news — ручной запуск публикации
async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ищу и публикую свежие новости...")
    await post_news(context)

# Основная функция старта бота
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Планировщик: каждые 2 часа
    scheduler = AsyncIOScheduler()
    scheduler.add_job(post_news, 'interval', hours=2, args=[app.bot])
    scheduler.start()

    # Обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news_command))

    app.run_polling()

if __name__ == '__main__':
    main()
```
