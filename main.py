import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from deploymentbot.app.handlers import router
from deploymentbot.konec import run_task_send
from deploymentbot.middlewares.middlewares import AudioFileMiddleware, BotMessageTrackerMiddleware

# Initialize logging
logging.basicConfig(level=logging.INFO)

load_dotenv()
TOKEN = os.getenv('TOKEN')
# Initialize Bot and Dispatcher
bot = Bot(token = TOKEN)
dp = Dispatcher()

async def main():
    dp.include_router(router)
    dp.update.middleware(BotMessageTrackerMiddleware(bot))
    dp.update.middleware(AudioFileMiddleware())  # Update middleware
    asyncio.create_task(run_task_send("./", bot))

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
