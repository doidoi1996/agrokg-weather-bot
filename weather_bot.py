import asyncio
import os
import logging
from datetime import datetime, time as dt_time, timezone, timedelta

import requests
import openai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# Настройки ключей
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7303047610:AAHraj24cjD94JTOGb-9ncD9RY0GG1QO-j4")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "@agrokg_msh")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "31f0e42c1bc0d2e6301f9d0452b75ad1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")

openai.api_key = OPENAI_API_KEY

CITIES = ["Бишкек", "Аламедин", "Чуй", "Сокулук"]
user_selected_city = {}  # запоминаем город пользователя по chat_id

# Получение погоды
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
    else:
        print(f"[!] Ошибка погоды ({city}): {response.status_code} - {response.text}")
    return None

# Получение рекомендаций от OpenAI
def get_farming_advice(weather_data, crop):
    prompt = (
        f"Я фермер. Погода сейчас: {weather_data['description']}, "
        f"температура {weather_data['temp']}°C, влажность {weather_data['humidity']}%. "
        f"Я выращиваю {crop}. Дай советы по уходу за этой культурой в текущих условиях."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты агроном-консультант. Дай практичные советы."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[!] Ошибка OpenAI: {e}")
        return "Не удалось получить рекомендации от ИИ."

# Форматирование сообщения
def format_weather_message(city, weather_data, advice, crop=None):
    base = (
        f"📍 Город: {city}\n"
        f"🌤️ Погода на {datetime.now().strftime('%d.%m.%Y')}:\n"
        f"Температура: {weather_data['temp']}°C (ощущается как {weather_data['feels_like']}°C)\n"
        f"Состояние: {weather_data['description']}\n"
        f"Влажность: {weather_data['humidity']}%\n"
        f"Ветер: {weather_data['wind_speed']} м/с\n"
        f"Осадки: {weather_data['precipitation']} мм\n\n"
    )
    if crop:
        base += f"🌾 Советы по культуре: *{crop}*\n{advice}"
    else:
        base += f"🌾 Общие рекомендации:\n{advice}"
    return base

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(city, callback_data=city)] for city in CITIES]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите ваш регион:", reply_markup=reply_markup)

# Кнопки выбора города
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data
    user_selected_city[query.from_user.id] = city
    await query.message.reply_text(f"Вы выбрали: {city}. Теперь напишите, какую культуру вы выращиваете.")

# Ответ на текст — культура
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    crop = update.message.text.strip()
    city = user_selected_city.get(user_id)

    if not city:
        await update.message.reply_text("Сначала выберите город с помощью команды /start.")
        return

    weather_data = get_weather(city)
    if weather_data:
        advice = get_farming_advice(weather_data, crop)
        message = format_weather_message(city, weather_data, advice, crop)
        await update.message.reply_text(message, parse_mode="Markdown")
    else:
        await update.message.reply_text(f"Не удалось получить прогноз погоды для {city}.")

# Ежедневная рассылка в канал
async def daily_weather(context: ContextTypes.DEFAULT_TYPE):
    for city in CITIES:
        weather_data = get_weather(city)
        if weather_data:
            advice = get_farming_advice(weather_data, "пшеница")
            message = format_weather_message(city, weather_data, advice)
            await context.bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=message)

# Основной запуск
async def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("Запуск бота...")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Периодическая задача
    KYRGYZ_TZ = timezone(timedelta(hours=6))
    app.job_queue.run_daily(daily_weather, time=dt_time(hour=7, tzinfo=KYRGYZ_TZ))

    await app.run_polling()

if __name__ == "__main__":
    import logging
    import nest_asyncio

    logging.basicConfig(level=logging.INFO)
    logging.info("Запуск бота...")

    nest_asyncio.apply()

    asyncio.get_event_loop().run_until_complete(main())


