import asyncio
import os
from datetime import datetime, time as dt_time, timezone, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

import requests

# === Конфигурация ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
XAI_API_KEY = os.getenv("XAI_API_KEY")

# === Города для кнопок ===
CITIES = ["Бишкек", "Аламедин", "Чуй", "Сокулук"]

# === Получение прогноза погоды ===
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

# === Рекомендации от xAI ===
def get_farming_advice(weather_data):
    prompt = (
        f"Погода: температура {weather_data['temp']}°C, {weather_data['description']}, "
        f"влажность {weather_data['humidity']}%. Дай краткие рекомендации для фермеров."
    )
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post("https://api.x.ai/v1/grok", json={"prompt": prompt}, headers=headers)
        if response.status_code == 200:
            return response.json().get("response", "Следите за погодой и поливайте культуры.")
    except Exception as e:
        print(f"Ошибка при обращении к XAI API: {e}")
    return "Следите за погодой и поливайте культуры."

# === Форматирование сообщения о погоде ===
def format_weather_message(city, weather_data, advice):
    return (
        f"🌤️ Прогноз погоды в {city} на {datetime.now().strftime('%d.%m.%Y')}:\n"
        f"Температура: {weather_data['temp']}°C (ощущается как {weather_data['feels_like']}°C)\n"
        f"Погода: {weather_data['description']}\n"
        f"Влажность: {weather_data['humidity']}%\n"
        f"Ветер: {weather_data['wind_speed']} м/с\n"
        f"Осадки: {weather_data['precipitation']} мм\n\n"
        f"🌾 Рекомендации для фермеров:\n{advice}"
    )

# === Команда /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[InlineKeyboardButton(city, callback_data=city)] for city in CITIES]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите город:", reply_markup=reply_markup)

# === Обработка текстовых сообщений ===
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    city = update.message.text.strip()
    weather_data = get_weather(city)
    if weather_data:
        advice = get_farming_advice(weather_data)
        message = format_weather_message(city, weather_data, advice)
        await update.message.reply_text(message)
    else:
        await update.message.reply_text(f"Не удалось получить прогноз для {city}. Проверьте название города.")

# === Обработка кнопок ===
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    city = query.data
    weather_data = get_weather(city)
    if weather_data:
        advice = get_farming_advice(weather_data)
        message = format_weather_message(city, weather_data, advice)
        await query.message.reply_text(message)
    else:
        await query.message.reply_text(f"Не удалось получить прогноз для {city}.")

# === Ежедневная рассылка в канал ===
async def daily_weather(context: ContextTypes.DEFAULT_TYPE) -> None:
    for city in CITIES:
        weather_data = get_weather(city)
        if weather_data:
            advice = get_farming_advice(weather_data)
            message = format_weather_message(city, weather_data, advice)
            await context.bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=message)

# === Основная функция запуска бота ===
async def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Добавление обработчиков
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button))

    # Планирование ежедневных сообщений (с учетом часового пояса Кыргызстана)
    KYRGYZSTAN_TZ = timezone(timedelta(hours=6))
    app.job_queue.run_daily(daily_weather, time=dt_time(hour at 7, minute=0, tzinfo=KYRGYZSTAN_TZ))

    # Запуск бота
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
