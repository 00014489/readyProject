import os
import logging
from aiogram.types import Update, Message
from aiogram import BaseMiddleware
from aiogram.types import ContentType
import data.connection as dataPostgres
import re
import app.keyboardInline as kbIn
import app.handlers as hanf

# Format filename for database and file system
def format_column_namesForDatabase(input_string: str):
    base_name, extension = os.path.splitext(input_string)
    cleaned_string = re.sub(r'[\'@()\-.]', '', base_name)
    formatted_name = cleaned_string.replace(' ', '_').lower()
    return f"{formatted_name}{extension}"
class AudioFileMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data):
        if isinstance(event, Update) and event.message and isinstance(event.message, Message):
            message = event.message

            if message.content_type == ContentType.AUDIO:
                user_id = message.from_user.id
                file_id = message.audio.file_id
                file_name = message.audio.file_name or "Unknown_Song.mp3"
                file_size = message.audio.file_size / (1024 * 1024)  # Convert size to MB
                file_duration = message.audio.duration / 60  # Convert duration to minutes

                # Validation: Check if the file is larger than 15 MB or longer than 6 minutes
                if file_size > 15:
                    await message.reply(f"The song is too big ({file_size:.2f} MB). Please send a song smaller than 15 MB.")
                    return
                if file_duration > 6:
                    await message.reply(f"The song is too long ({file_duration:.2f} minutes). Please send a song shorter than 6 minutes.")
                    return

                if not await dataPostgres.check_file_exists(file_id):
                    await dataPostgres.insert_into_input_file(file_id, format_column_namesForDatabase(file_name))
                try:
                    await message.reply("Please select the vocal percentage...", reply_markup=await kbIn.percent_choose(file_id))
                except Exception as e:
                    logging.error(f"Error processing audio file: {e}", exc_info=True)
                    await message.reply(f"Failed to process {file_name} due to an error: {str(e)}")

        return await handler(event, data)