# import os
import logging
from aiogram.types import Update, Message
from aiogram import BaseMiddleware, Bot
from aiogram.types import ContentType, Update, FSInputFile
import data.connection as dataPostgres
import re
import deploymentbot.app.keyboardInline as kbIn
from deploymentbot.app.handlers import forward_message_to_user
import os
import yt_dlp
# from pytube import YouTube
# import asyncio

def sanitize_title(title):
    """Sanitize the title for use in a filename."""
    return re.sub(r'[<>:"/\\|?*]', '_', title)  # Replace invalid characters with underscores

async def download_youtube_audio(bot: Bot, youtube_link: str, chat_id: int):
    """Download audio from a YouTube video link and send it to the user."""
    try:
        logging.info(f"Attempting to download audio from: {youtube_link}")

        # Extract video info to get the title before downloading
        with yt_dlp.YoutubeDL() as ydl:
            info_dict = ydl.extract_info(youtube_link, download=False)
            title = info_dict.get('title', None)
            duration = info_dict.get('duration', 0)  # Duration in seconds

            if duration > 421:
                logging.warning(f"Audio duration is {duration} seconds, which exceeds the limit of 7 minutes.")
                await bot.send_message(chat_id, "The audio duration must be no more than 7 minutes. Please choose a shorter video.")
                return

            if not title:
                logging.error("Error: Title not found for the YouTube video.")
                await bot.send_message(chat_id, "Error with the title of the YouTube video.")
                return

            # Sanitize the title for the filename
            sanitized_title = sanitize_title(title)
            logging.info(f"Sanitized title: {sanitized_title}")

        # Define the output file path format using the sanitized title
        output_path = f"downloads/{sanitized_title}.%(ext)s"  # Save as title.mp3 in 'downloads' folder

        # Set yt-dlp options
        ydl_opts = {
            'format': 'bestaudio/best',  # Select the best audio format
            'outtmpl': output_path,       # Save the file with the sanitized title
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',  # Use ffmpeg to extract audio
                'preferredcodec': 'mp3',      # Save as mp3
                'preferredquality': '192',    # Set the quality
            }],
            'noplaylist': True,             # Avoid downloading playlists
            'quiet': False,                 # Set to True to suppress output (optional)
            'cookies': '/home/minusGolosAdmin/readyProject/cookies.txt',             
        }

        # Download audio using yt-dlp with sanitized filename
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(youtube_link, download=True)

        # Build the full file path for the sanitized file
        audio_file_path = os.path.join("downloads", f"{sanitized_title}.mp3")

        # Check if file exists before sending
        if os.path.exists(audio_file_path):
            logging.info(f"File exists, preparing to send: {audio_file_path}")
            sentL = await bot.send_audio(chat_id=chat_id, audio=FSInputFile(audio_file_path))
            # print(f"needed id = {sentL}")
            await dataPostgres.insert_into_links(chat_id, youtube_link, sentL)
            logging.info(f"Successfully sent audio: {audio_file_path}")

            # Remove the file after sending
            os.remove(audio_file_path)
            logging.info(f"Deleted audio file: {audio_file_path}")
        else:
            logging.error(f"File not found: {audio_file_path}")
            # await bot.send_message(chat_id, "Error: Audio file not found after download.")
        
        return sanitized_title, 'mp3', audio_file_path  # Return title, file type, and path

    except Exception as e:
        logging.error(f"Error downloading audio: {e}")
        # await bot.send_message(chat_id, "There was an error processing the YouTube link. Please try again.")


class BotMessageTrackerMiddleware(BaseMiddleware):
    def __init__(self, bot: Bot):
        super().__init__()
        self.bot = bot  # Store the bot instance for later use

    async def __call__(self, handler, event: Update, data):
        if isinstance(event, Update) and event.message:
            message = event.message
            chat_id = message.chat.id
            message_id = message.message_id
            text = message.text

            if chat_id:
                logging.info(f"User ID {chat_id} sent Message ID {message_id}")

                # Check for YouTube link
                youtube_link = self.extract_youtube_link(text)
                if youtube_link:
                    try:
                        if await dataPostgres.link_exists(youtube_link):
                            user_id_from, message_id_from = await dataPostgres.get_user_id_and_message_id(youtube_link)
                            await forward_message_to_user(self.bot, user_id_from, message_id_from, chat_id)
                            logging.info(f"Forwarded message for existing link: {youtube_link} to user_id: {user_id_from}")
                        else:
                            waiting_message = await message.reply("Please wait...")
                            
                            # logging.info(f"Inserted new YouTube link: {youtube_link}")
                            sanitized_title, file_type, audio_file_path = await download_youtube_audio(self.bot, youtube_link, chat_id)

                            if audio_file_path:
                                # Delete the "Please wait" message after sending the audio file
                                await waiting_message.delete()
                                logging.info(f"Deleted waiting message: {waiting_message.message_id}")

                    except Exception as e:
                        logging.error(f"Error processing YouTube link: {youtube_link}, Error: {e}")
                        await waiting_message.delete()
                        # await message.answer("There was an error processing your request. Please try again.")
                                    
                else:
                    await message.reply("Please send a correct YouTube link or an audio file.")
            else:
                logging.warning("Cannot determine the sender ID.")

        # Always pass control to the next handler
        return await handler(event, data)

    def extract_youtube_link(self, text: str):
        """Extracts a YouTube link from the provided text."""
        youtube_regex = r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})'
        match = re.search(youtube_regex, text)
        return match.group(0) if match else None


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
                # user_id = message.from_user.id
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
                    # Get the file name without the extension
                    file_name_without_extension = os.path.splitext(file_name)[0]
                    
                    # Insert into the database with the file name without the extension
                    await dataPostgres.insert_into_input_file(file_id, format_column_namesForDatabase(file_name), file_name_without_extension)

                try:
                    await message.reply("Please select the vocal percentage...", reply_markup=await kbIn.percent_choose(file_id))
                except Exception as e:
                    logging.error(f"Error processing audio file: {e}", exc_info=True)
                    await message.reply(f"Failed to process {file_name} due to an error: {str(e)}")

        return await handler(event, data)