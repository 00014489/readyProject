import os
import json
import signal
import re
import logging
import asyncio
from run import process_audio_file
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile, CallbackQuery
from aiogram.exceptions import TelegramAPIError
import data.connection as dataPostgres
import shutil  # For deleting directories and their content
from collections import deque

router = Router()
audio_queue = deque()
processing_semaphore = asyncio.Semaphore(1)  # Limit to 1 concurrent tasks
processing = False
QUEUE_FILE = 'audio_queue.json'

# Load the audio queue from a JSON file.
def load_audio_queue():
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, 'r') as f:
            data = json.load(f)
            for item in data:
                # Convert back to the original tuple format
                audio_queue.append(tuple(item))

# Save the current audio queue to a JSON file.
def save_audio_queue():
    with open(QUEUE_FILE, 'w') as f:
        json.dump(list(audio_queue), f)

# Handle shutdown signal
def shutdown_hook(loop):
    save_audio_queue()
    loop.stop()

# Register the shutdown hook
loop = asyncio.get_event_loop()
loop.add_signal_handler(signal.SIGINT, lambda: shutdown_hook(loop))
loop.add_signal_handler(signal.SIGTERM, lambda: shutdown_hook(loop))

# Load the audio queue when starting the bot
load_audio_queue()

async def track_message(message: Message, percentage: int = None):
    message_id = message.message_id
    chat_id = message.chat.id
    if chat_id:
        return await dataPostgres.insert_chat_and_message_id(chat_id, message_id, percentage)

def format_column_namesForDatabase(input_string: str):
    base_name, extension = os.path.splitext(input_string)
    cleaned_string = re.sub(r'[\'@()\-.]!#$%^&*', '', base_name)
    formatted_name = cleaned_string.replace(' ', '_').lower()
    return f"{formatted_name}{extension}"

async def forward_message_to_user(bot: Bot, from_chat_id: int, message_id: int, to_chat_id: int):
    try:
        await bot.forward_message(chat_id=to_chat_id, from_chat_id=from_chat_id, message_id=message_id)
        logging.info(f"Message with ID {message_id} forwarded to user {to_chat_id}.")
    except Exception as e:
        logging.error(f"Error forwarding message: {e}")

@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    userName = message.from_user.username
    await dataPostgres.insert_user_if_not_exists(user_id, userName)
    photo = FSInputFile("./images/photo_2024-09-13_10-23-12.jpg")
    await message.answer_photo(photo, caption=(
        "Welcome to MinusGolos bot\n\n"
        "This bot can get audio file and return minus of sended audio\n\n"
        f"U can choose returning with 0% vocal or 15% or 50%.\n\n"
        "Great point, Day by day the bot will become more faster"))

@router.callback_query(F.data.startswith("mix_vocals"))
async def handle_playlist_move(callback: CallbackQuery, bot: Bot):
    _, id_input, vocal_percentage = callback.data.split(":")
    vocal_percentage = int(vocal_percentage)
    file_id = await dataPostgres.get_file_id_by_id(int(id_input))
    chat_id = callback.from_user.id
    processing_message = await callback.message.edit_text("Please wait ...")

    if await dataPostgres.check_file_exists_with_percentage(file_id, vocal_percentage):
        id = await dataPostgres.get_output_id_for_percentage(file_id, vocal_percentage)
        from_chat_id, message_id = await dataPostgres.get_chat_and_message_id_by_id(id, vocal_percentage)
        await forward_message_to_user(bot, from_chat_id, message_id, chat_id)
    else:
        save_directory = f'./inputSongs{vocal_percentage}:{id_input}'
        os.makedirs(save_directory, exist_ok=True)

        file_name = await dataPostgres.get_name_by_id(file_id)
        file_path = os.path.join(save_directory, format_column_namesForDatabase(file_name))
        audio_queue.append((bot, callback.message, file_id, file_name, file_path, chat_id, vocal_percentage, id_input))
        await process_audio_queue()

    await bot.delete_message(chat_id, processing_message.message_id)

async def process_audio_queue():
    global processing
    if processing:
        return  # Prevent multiple simultaneous process executions

    processing = True

    while audio_queue:
        task = audio_queue.popleft()
        bot, message, file_id, file_name, file_path, user_id, vocal_percentage, id_input = task

        async with processing_semaphore:
            try:
                file = await bot.get_file(file_id)
                await asyncio.wait_for(bot.download_file(file.file_path, destination=file_path), timeout=600)
                logging.info(f"File {file_name} downloaded successfully to {file_path}")
                logging.info(f"Processing audio file with vocal percentage: {vocal_percentage}%")

                processed_audio_file, output_folder = await process_audio_file(file_path, vocal_percentage, id_input)
                if processed_audio_file is None:
                    raise ValueError("Processed audio file is None. Ensure the processing function returns a valid file path.")

                sendFile = await asyncio.wait_for(bot.send_audio(chat_id=user_id, audio=FSInputFile(processed_audio_file)), timeout=240)
                id = await track_message(sendFile, vocal_percentage)
                await dataPostgres.update_out_id_by_percent(file_id, id, vocal_percentage)

                try:
                    if os.path.exists(output_folder):
                        shutil.rmtree(output_folder)
                        logging.info(f"Deleted output folder: {output_folder}")
                    logging.info("Garbage collection executed.")
                except Exception as cleanup_error:
                    logging.error(f"Error cleaning up files: {cleanup_error}")

            except asyncio.TimeoutError:
                logging.error("Processing the file took too long.")
                await message.reply("Processing the file took too long. Please try again later.")
            except Exception as process_error:
                logging.error(f"Error processing audio file: {process_error}", exc_info=True)
                fail_add_message = f"Failed to process {file_name} due to an error: {str(process_error)}"
                await message.reply(fail_add_message)

    processing = False

@router.message(Command("help"))
async def cmd_help(message: Message):
    photo = FSInputFile("./images/help.jpg")
    await message.answer_photo(
        photo,
        caption=(
            f"Send song and get a minus of song\n\n"
            f"0% button - it is button for getting the 0% vocal audio file\n"
            f"15% button - it is button for getting the audio with 15% vocal volume for better quality\n"
            f"50% button - it is button for getting the audio with 50% vocal volume for better melody\n"
            "If u get error that process is too long please try again\n\n"
            "Do not forget. Day by day the bot will become more and more faster\n"
            "U can check it by practicing ...\n\n"
            "If u have technical problems. U can contact admin"))

ADMIN_ID = 1031267509
forwarding_enabled = False

@router.message()
async def handle_message_reklama(message: Message):
    global forwarding_enabled
    if message.from_user and message.from_user.id != ADMIN_ID:
        return  # Exit early if the user is not the admin

    if forwarding_enabled:
        await forward_message_to_users(from_chat_id=message.chat.id, message_id=message.message_id, bot=message.bot)
    else:
        await message.answer("Message forwarding is currently disabled.")

async def forward_message_to_users(from_chat_id: int, message_id: int, bot: Bot):
    global forwarding_enabled
    users = await dataPostgres.get_user_ids()
    if not forwarding_enabled or not users:
        print("Message forwarding is disabled or no users to forward to. Skipping...")
        return

    for user_id in users:
        try:
            await bot.forward_message(chat_id=user_id, from_chat_id=from_chat_id, message_id=message_id)
            print(f"Message forwarded to user: {user_id}")
        except TelegramAPIError as e:
            print(f"Failed to forward message to user {user_id}: {e}")
        await asyncio.sleep(0.03)  # 30 milliseconds delay to respect Telegram API limits

@router.message(Command("turn_on"))
async def turn_on_forwarding(message: Message):
    global forwarding_enabled
    if message.from_user.id == ADMIN_ID:
        forwarding_enabled = True
        await message.answer("Message forwarding has been turned ON.")
    else:
        await message.answer("You don't have permission to use this command.")

@router.message(Command("turn_off"))
async def turn_off_forwarding(message: Message):
    global forwarding_enabled
    if message.from_user.id == ADMIN_ID:
        forwarding_enabled = False
        await message.answer("Message forwarding has been turned OFF.")
    else:
        await message.answer("You don't have permission to use this command.")
