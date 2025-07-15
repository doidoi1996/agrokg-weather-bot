import asyncio
import logging
import os
from datetime import datetime, time as dt_time, timezone, timedelta

import requests
import openai
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# API Keys and Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "YOUR_OPENWEATHER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# States for conversation
ASK_CITY, ASK_CROP = range(2)

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory user state
user_data = {}

# Weather fetching

def get_weather(city):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city},KG&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return {
            "temp": data["main"]["temp"],
            "feels_like": data["main"]["feels_like"],
            "description": data["weather"][0]["description"],
            "humidity": data["main"]["humidity"],
            "wind_speed": data["wind"]["speed"],
            "precipitation": data.get("rain", {}).get("1h", 0)
        }
    return None

# Farming advice from OpenAI

def get_farming_advice(weather_data, crop):
    prompt = (
        f"Я фермер. Погода сейчас: {weather_data['description']}, температура {weather_data['temp']}°C, "
        f"влажность {weather_data['humidity']}%. Я выращиваю {crop}. Дай советы по уходу."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты агроном-консультант. Дай практичные советы."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Ошибка OpenAI: {e}")
        return "Не удалось получить рекомендации от ИИ."

# Formatting message

def format_weather_message(city, weather_data, advice, crop):
    return (
        f"📍 Город: {city}\n"
        f"🌤️ Погода: {weather_data['description']}, {weather_data['temp']}°C (ощущается как {weather_data['feels_like']}°C)\n"
        f"💧 Влажность: {weather_data['humidity']}% | 🌬️ Ветер: {weather_data['wind_speed']} м/с | 🌧️ Осадки: {weather_data['precipitation']} мм\n\n"
        f"🌾 Культура: *{crop}*\n🧠 Советы: {advice}"
    )

# /start handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Здравствуйте! Введите название вашего населенного пункта:")
    return ASK_CITY

async def ask_crop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip()
    weather = get_weather(city)
    if not weather:
        await update.message.reply_text("❌ Город не найден. Попробуйте снова:")
        return ASK_CITY
    user_data[update.message.chat_id] = {"city": city, "weather": weather}
    await update.message.reply_text("Какую культуру вы выращиваете?")
    return ASK_CROP

async def send_advice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    crop = update.message.text.strip()
    data = user_data.get(update.message.chat_id)
    if not data:
        await update.message.reply_text("Сначала введите команду /start")
        return ConversationHandler.END
    advice = get_farming_advice(data["weather"], crop)
    message = format_weather_message(data["city"], data["weather"], advice, crop)
    await update.message.reply_text(message, parse_mode="Markdown")
    return ConversationHandler.END

# Cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Диалог отменён.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# App init
async def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_crop)],
            ASK_CROP: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_advice)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)

    # Запускаем бота
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
