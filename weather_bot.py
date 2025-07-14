import requests
import telegram
import asyncio
import schedule
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Настройки
TELEGRAM_BOT_TOKEN = '7303047610:AAHraj24cjD94JTOGb-9ncD9RY0GG1QO-j4'  # Ваш токен Telegram
TELEGRAM_CHANNEL_ID = '@agrokg_msh'  # Ваш канал
OPENWEATHER_API_KEY = '31f0e42c1bc0d2e6301f9d0452b75ad1'  # Ваш OpenWeatherMap ключ
XAI_API_KEY = 'xai-I7OLtQjEl3G2WUeEVmevXucGwByarxvvxWdcKXtr6N7DJFxnGLpIwepVDLc59gJuE34L47n7XWCECdx5'  # Ваш xAI ключ

# Районы Бишкека и окрестностей
REGIONS = {
    'Бишкек': {'lat': 42.8746, 'lon': 74.5698},
    'Аламедин': {'lat': 42.8800, 'lon': 74.6300},
    'Чуй': {'lat': 42.8167, 'lon': 73.9833},
    'Сокулук': {'lat': 42.8500, 'lon': 74.3000}
}

async def get_weather(lat, lon, region_name):
    try:
        # Запрос погоды
        url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
        response = requests.get(url)
        data = response.json()
        
        if data['cod'] != 200:
            return f"Ошибка получения данных о погоде для {region_name}: {data['message']}"
        
        temp = data['main']['temp']
        feels_like = data['main']['feels_like']
        humidity = data['main']['humidity']
        weather_desc = data['weather'][0]['description']
        wind_speed = data['wind']['speed']
        rain = data.get('rain', {}).get('1h', 0)  # Осадки за последний час (мм)
        
        # Запрос к xAI API для рекомендаций
        xai_response = requests.post(
            'https://api.x.ai/v1/grok',
            headers={'Authorization': f'Bearer {XAI_API_KEY}'},
            json={
                'prompt': (
                    f"На основе погоды в {region_name}: температура {temp}°C, влажность {humidity}%, "
                    f"ветер {wind_speed} м/с, осадки {rain} мм, описание: {weather_desc}. "
                    f"Сгенерируй рекомендации для фермеров на русском языке (максимум 100 слов), "
                    f"учитывая сельскохозяйственные нужды в регионе Бишкек."
                )
            }
        )
        recommendations = xai_response.json().get('response', "Рекомендации недоступны. Поддерживайте стандартный уход.")
        
        message = (
            f"🌤️ Прогноз погоды в {region_name} на {datetime.now().strftime('%d.%m.%Y')}:\n"
            f"Температура: {temp}°C (ощущается как {feels_like}°C)\n"
            f"Погода: {weather_desc}\n"
            f"Влажность: {humidity}%\n"
            f"Ветер: {wind_speed} м/с\n"
            f"Осадки: {rain} мм\n\n"
            f"🌾 Рекомендации для фермеров:\n{recommendations}"
        )
        return message
    except Exception as e:
        return f"Ошибка: {str(e)}"

async def send_daily_forecast(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    for region, coords in REGIONS.items():
        message = await get_weather(coords['lat'], coords['lon'], region)
        await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=message, parse_mode='Markdown')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(region, callback_data=region)] for region in REGIONS]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Выберите район для получения прогноза погоды и рекомендаций:",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    region = query.data
    if region in REGIONS:
        coords = REGIONS[region]
        message = await get_weather(coords['lat'], coords['lon'], region)
        await query.message.reply_text(message, parse_mode='Markdown')
    else:
        await query.message.reply_text("Район не найден. Попробуйте выбрать другой.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    for region in REGIONS:
        if region.lower() in text:
            coords = REGIONS[region]
            message = await get_weather(coords['lat'], coords['lon'], region)
            await update.message.reply_text(message, parse_mode='Markdown')
            return
    await update.message.reply_text(
        "Пожалуйста, укажите район (например, 'Бишкек' или 'Аламедин') или используйте /start для выбора."
    )

def schedule_task():
    schedule.every().day.at("07:00").do(lambda: asyncio.run(send_daily_forecast(app)))

async def main():
    global app
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await app.run_polling()

if __name__ == "__main__":
    import platform
    if platform.system() == "Emscripten":
        asyncio.ensure_future(main())
    else:
        import threading
        threading.Thread(target=schedule_task, daemon=True).start()
        asyncio.run(main())