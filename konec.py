import logging
import os
import re
import shutil
from aiogram import Bot
import psutil
from concurrent.futures import ThreadPoolExecutor
import asyncio
import data.connection as dataPostgres
from aiogram.types import Message, FSInputFile
from aiogram.exceptions import TelegramBadRequest

# Initialize task_starting as True or False based on your requirements
task_starting = True

async def track_message(message: Message, percentage: int = None):
    message_id = message.message_id
    chat_id = message.chat.id

    if chat_id:
        return await dataPostgres.insert_chat_and_message_id(chat_id, message_id, percentage)

async def run_task_send(base_dir, bot: Bot):
    global task_starting  # Change this to the new variable name
    while task_starting:  # Update this line to use the new variable name
        logging.info("Running the scheduled task...")
        
        # Check and match input song folders
        await check_and_match_song_folders(base_dir, bot)

        # Sleep for 10 seconds before the next run
        await asyncio.sleep(10)  # Use asyncio.sleep instead of time.sleep

async def check_and_match_song_folders(base_dir, bot: Bot):
    folder_pattern = r"^sendSongs(\d+):(\d+):(\d+)$"
    found_matching_folders = []

    with ThreadPoolExecutor() as pool:
        # Get the list of folders in the base directory
        folder_list = await asyncio.get_event_loop().run_in_executor(pool, os.listdir, base_dir)

        for folder_name in folder_list:
            folder_path = os.path.join(base_dir, folder_name)  # Construct full folder path
            is_dir = await asyncio.get_event_loop().run_in_executor(pool, os.path.isdir, folder_path)

            # Proceed only if it's a directory and matches the naming pattern
            if is_dir and folder_name.startswith("sendSongs"):
                match = re.match(folder_pattern, folder_name)

                if match:
                    vocal_percentage = match.group(1)  # Extract vocal percentage
                    song_id = match.group(2)  # Extract song ID
                    user_id = match.group(3)  # Extract user ID

                    # Get expected audio file name from the database
                    expected_audio_file_name = await asyncio.get_event_loop().run_in_executor(pool, dataPostgres.get_name_by_songId, song_id)

                    # Determine the new audio file name based on vocal percentage
                    if int(vocal_percentage) == 0:
                        new_audio_file_name = f"{os.path.splitext(expected_audio_file_name)[0]}_minus_320k.mp3"
                    else:
                        new_audio_file_name = f"{os.path.splitext(expected_audio_file_name)[0]}_accompaniment_{vocal_percentage}percent_320k.mp3"

                    # Construct the full expected audio file path inside the folder
                    expected_audio_file_path = os.path.join(folder_path, new_audio_file_name)

                    # Check if the expected audio file exists in the folder
                    if os.path.isfile(expected_audio_file_path):
                        found_matching_folders.append((vocal_percentage, song_id, user_id, expected_audio_file_path, folder_path))
                    else:
                        logging.warning(f"Expected audio file not found: {expected_audio_file_path}")

    # Process the found matching folders
    if found_matching_folders:
        for vocal_percentage, song_id, user_id, audio_file_path, folder_path in found_matching_folders:
            logging.info(f"Starting to send the audio")
            await asyncio.sleep(3)

            await send_chosen_audio(vocal_percentage, song_id, user_id, audio_file_path, bot)

            # Delete the folder after sending the audio file
            try:
                shutil.rmtree(folder_path)
                logging.info(f"Deleted folder: {folder_path}")
            except Exception as e:
                logging.error(f"Failed to delete folder {folder_path}: {e}")
    else:
        logging.info("No matching folders found for sending.")

async def send_chosen_audio(vocal_percentage, song_id, user_id, audio_file_path, bot: Bot):
    try:
        # Get the original file name from the database
        original_file_name = await dataPostgres.get_file_name_original_by_id(song_id)
        
        # Extract the directory and extension from the original audio file path
        file_dir = os.path.dirname(audio_file_path)
        file_extension = os.path.splitext(original_file_name)[1]  # Get the file extension

        # Construct the new file name by adding vocal_percentage and "byMinusGolos" to the original name
        new_file_name = f"{os.path.splitext(original_file_name)[0]}_{vocal_percentage}percent_byMinusGolos{file_extension}"

        # Form the full path for the new file name
        new_audio_file_path = os.path.join(file_dir, new_file_name)

        # Perform the renaming operation
        os.rename(audio_file_path, new_audio_file_path)

        # Send the renamed audio file
        sendFile = await bot.send_audio(chat_id=user_id, audio=FSInputFile(new_audio_file_path))
        id = await track_message(sendFile, vocal_percentage)
        logging.info(f"Message ID is {sendFile.message_id}")

        # Update the database
        file_id = await dataPostgres.get_file_id_by_id(song_id)
        await dataPostgres.update_out_id_by_percent(file_id, id, vocal_percentage)

    except TelegramBadRequest as e:
        logging.error(f"Failed to send audio for song_id {song_id}: {e}")
        # If the sending process fails with BadRequest, notify the user
        await bot.send_message(chat_id=user_id, text="Please try again.")
    except Exception as e:
        logging.error(f"Unexpected error for song_id {song_id}: {e}")