import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from google import genai
import edge_tts

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

GEMINI_PROMPT = (
    "Тебя зовут Gemini. Ты — продвинутый искусственный интеллект и персональный ассистент, "
    "созданный в манере Джарвиса из фильма 'Железный человек'. "
    "Обращайся к пользователю только на 'сэр'. "
    "Твой стиль общения: безупречно вежливый, сдержанный, аналитический, с тонкой британской иронией. "
    "Отвечай емко, строго по делу, без пространных и пустых вступлений. "
    "При докладе о статусе или выполнении команд формулируй ответ лаконично, как системный отчет."
)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
ai_client = genai.Client(api_key=GEMINI_API_KEY)

async def text_to_speech(text: str, filename: str = "gemini_voice.ogg"):
    """Генерация реалистичного голоса"""
    voice = "ru-RU-DmitryNeural"
    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(filename)
    return filename

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    greeting = "Все системы функционируют в штатном режиме, сэр. Я — Gemini. Чем могу быть полезен?"
    voice_file = await text_to_speech(greeting)
    await message.answer_voice(types.FSInputFile(voice_file), caption=greeting)
    if os.path.exists(voice_file):
        os.remove(voice_file)

@dp.message(F.voice)
async def voice_handler(message: types.Message):
    """Обработка входящих голосовых сообщений"""
    await bot.send_chat_action(message.chat.id, "record_voice")
    
    file_id = message.voice.file_id
    file = await bot.get_file(file_id)
    file_path = f"input_{file_id}.ogg"
    await bot.download_file(file.file_path, destination=file_path)

    try:
        # Загружаем аудио напрямую в Gemini для понимания речи
        uploaded_audio = ai_client.files.upload(file=file_path)
        
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[uploaded_audio, "Ответь на это аудиосообщение."],
            config=dict(system_instruction=GEMINI_PROMPT)
        )
        answer_text = response.text or "Сигнал получен, но расшифровка не удалась, сэр."
    except Exception as e:
        answer_text = f"Произошла ошибка при обработке голосового канала, сэр: {e}"
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    # Озвучиваем ответ
    voice_file = await text_to_speech(answer_text)
    await message.answer_voice(types.FSInputFile(voice_file), caption=answer_text)
    if os.path.exists(voice_file):
        os.remove(voice_file)

@dp.message(F.text)
async def text_handler(message: types.Message):
    """Обработка текстовых сообщений"""
    await bot.send_chat_action(message.chat.id, "record_voice")
    
    response = ai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=message.text,
        config=dict(system_instruction=GEMINI_PROMPT)
    )
    answer_text = response.text or "Прошу прощения, сэр, данные не получены."

    # Если ответ лаконичный (до 400 знаков), бот присылает голосовой файл + текст
    if len(answer_text) <= 400:
        voice_file = await text_to_speech(answer_text)
        await message.answer_voice(types.FSInputFile(voice_file), caption=answer_text)
        if os.path.exists(voice_file):
            os.remove(voice_file)
    else:
        await message.answer(answer_text)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
