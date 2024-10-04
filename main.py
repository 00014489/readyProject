import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from app.handlers import router
from config.config import TOKEN
from middlewares.middlewares import AudioFileMiddleware

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Initialize Bot and Dispatcher
bot = Bot(token=os.getenv('TOKEN'))
dp = Dispatcher()

async def main():
    # Include router with your handlers
    load_dotenv()
    dp.include_router(router)
    dp.update.middleware(AudioFileMiddleware())  # update
    try:
        # Start polling
        await dp.start_polling(bot)
    finally:
        # Ensure the bot's session is closed on shutdown
        await bot.session.close()
        logging.info("Bot session closed.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
