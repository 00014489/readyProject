import logging
import os
import psutil
import shutil
import re
from concurrent.futures import ThreadPoolExecutor
import data.connection as dataPostgres
from run import process_audio_file
import time

# Configure logging
logging.basicConfig(level=logging.INFO)

# Global variable to control task execution
task_running = True

def run_task(base_dir):
    global task_running
    
    delete_send_songs_folders(base_dir)
    while task_running:
        logging.info("Running the scheduled task...")

        # First, delete all folders starting with "sendSongs"

        # Check and match input song folders
        check_and_match_input_song_folders(base_dir)
        # Check RAM usage
        ram_usage = psutil.virtual_memory()
        used_ram_percentage = ram_usage.percent  # Get the percentage of used RAM
        logging.info(f"Now RAM usage is {used_ram_percentage}")

        if used_ram_percentage > 55:
            logging.warning("RAM usage exceeds 55%. Stopping the current task.")
            global task_running
            task_running = False  # Stop the task loop
            return  # Exit the function to avoid processing audio files
        # Sleep for 10 seconds before the next run
        time.sleep(10)

def delete_send_songs_folders(base_dir):
    """Delete all folders in the base directory that start with 'sendSongs'."""
    for folder_name in os.listdir(base_dir):
        if folder_name.startswith("sendSongs"):
            folder_path = os.path.join(base_dir, folder_name)
            if os.path.isdir(folder_path):
                shutil.rmtree(folder_path)  # Remove the folder and its contents
                logging.info(f"Deleted folder: {folder_path}")

def check_and_match_input_song_folders(base_dir):
    # Define the regex pattern for the folder names.
    folder_pattern = r"^inputSongs(\d+):(\d+):(\d+)$"

    found_matching_folders = []

    # Use ThreadPoolExecutor for I/O bound tasks
    with ThreadPoolExecutor() as pool:
        # List all the folders in the base directory
        folder_list = pool.submit(os.listdir, base_dir).result()

        for folder_name in folder_list:
            folder_path = os.path.join(base_dir, folder_name)
            is_dir = pool.submit(os.path.isdir, folder_path).result()

            # Check if it's a directory and starts with "inputSongs"
            if is_dir and folder_name.startswith("inputSongs"):
                match = re.match(folder_pattern, folder_name)

                if match:
                    vocal_percentage = match.group(1)
                    song_id = match.group(2)
                    user_id = match.group(3)

                    # Get the expected audio file name based on song_id
                    expected_audio_file_name = dataPostgres.get_name_by_songId(song_id)

                    if expected_audio_file_name:
                        # Construct the full path to the expected audio file
                        expected_audio_file_path = os.path.join(folder_path, expected_audio_file_name)

                        # Delete all files in the folder except for the expected audio file
                        for file_name in os.listdir(folder_path):
                            file_path = os.path.join(folder_path, file_name)
                            # If the file is not the expected one, delete it
                            if file_path != expected_audio_file_path and os.path.isfile(file_path):
                                os.remove(file_path)  # Permanently delete the file
                                logging.info(f"Deleted file: {file_path}")

                        # After deleting unnecessary files, check if the folder is now empty
                        remaining_files = os.listdir(folder_path)
                        if len(remaining_files) == 1 and remaining_files[0] == expected_audio_file_name:
                            # If the only file left is the expected audio file, add to processing list
                            found_matching_folders.append((vocal_percentage, song_id, user_id, expected_audio_file_path))
                        elif not remaining_files:
                            # If the folder is completely empty, delete the folder
                            # shutil.rmtree(folder_path)
                            logging.info(f"there are nothing in this folder {folder_path}")

            

    # Process and send the audio files if any valid ones were found
    if found_matching_folders:
        for vocal_percentage, song_id, user_id, audio_file_path in found_matching_folders:
            time.sleep(10)
            process_and_send_audio(vocal_percentage, song_id, user_id, audio_file_path)
    else:
        logging.info("No matching folders found for processing.")

def process_and_send_audio(vocal_percentage, song_id, user_id, audio_file_path):
    print(f"song_id - {song_id}")

    file_name = dataPostgres.get_file_name_by_id(song_id)
    print(f"song_name - {file_name}")
    process_audio_file(vocal_percentage, song_id, user_id)

def main(base_dir):
    run_task(base_dir)

# Entry point for the program
if __name__ == "__main__":
    base_dir = "./"  # Change to your base directory
    try:
        main(base_dir)
    except KeyboardInterrupt:
        logging.info("Program interrupted. Exiting...")
