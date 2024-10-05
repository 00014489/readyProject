import asyncio
import logging
import os
import shutil
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from app.handlers import router
from middlewares.middlewares import AudioFileMiddleware

# Initialize logging
logging.basicConfig(level=logging.INFO)

load_dotenv()
TOKEN = os.getenv('TOKEN')
# Initialize Bot and Dispatcher
bot = Bot(token = TOKEN)
dp = Dispatcher()

async def main():
    delete_input_songs_folders()
    # Include router with your handlers
    dp.include_router(router)
    dp.update.middleware(AudioFileMiddleware())  # update
    try:
        # Start polling
        await dp.start_polling(bot)
    finally:
        # Ensure the bot's session is closed on shutdown
        await bot.session.close()
        logging.info("Bot session closed.")

def delete_input_songs_folders():
    # Define the path where the folders are located
    base_path = '.'  # Change this to the desired base path if needed

    # Iterate over items in the base path
    for item in os.listdir(base_path):
        # Check if the item is a directory and starts with 'inputSongs'
        if os.path.isdir(item) and item.startswith('inputSongs'):
            try:
                # Remove the directory and all its contents
                shutil.rmtree(item)  # Delete the folder and its contents
                logging.info(f"Deleted folder: {item}")
            except Exception as e:
                logging.error(f"Failed to delete folder {item}: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
