import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from app.handlers import router
from middlewares.middlewares import AudioFileMiddleware

# Load environment variables from .env file
load_dotenv()

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Get the token
TOKEN = os.getenv('TOKEN')

# Check if the token is loaded
if TOKEN is None:
    raise ValueError("No token found. Please set the TOKEN environment variable.")

# Initialize Bot and Dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)  # Pass the bot instance to the Dispatcher

async def main():
    # Include router with your handlers
    dp.include_router(router)
    dp.update.middleware(AudioFileMiddleware())  # update
    try:
        # Start polling
        await dp.start_polling()
    finally:
        # Ensure the bot's session is closed on shutdown
        await bot.session.close()
        logging.info("Bot session closed.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
