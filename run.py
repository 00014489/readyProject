import os
import logging
# import uuid
import time
from spleeter.separator import Separator
import asyncio
# import subprocess
import tensorflow as tf
# import psutil
# import gc

# TensorFlow configuration
try:
    gpus = tf.config.experimental.list_physical_devices('GPU')
    if gpus:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
except RuntimeError as e:
    logging.error(f"Error setting TensorFlow memory growth: {e}")


async def convert_to_wav(input_file, new_folder, base_name):
    """Convert the input file to WAV format asynchronously."""
    wav_input_file = os.path.join(new_folder, f'{base_name}.wav')
    process = await asyncio.create_subprocess_exec(
        'ffmpeg', '-i', input_file, wav_input_file,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg conversion error: {stderr.decode()}")
    return wav_input_file


async def run_spleeter(wav_input_file, new_folder):
    """Separate the audio using Spleeter."""
    separator = Separator('spleeter:2stems')
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, separator.separate_to_file, wav_input_file, new_folder)


async def convert_accompaniment_to_mp3(accompaniment_file, new_folder, base_name, output_format='mp3'):
    """Convert the accompaniment (without vocals) to MP3 format asynchronously."""
    output_file = os.path.join(new_folder, f'{base_name}_minus_320k.{output_format}')
    process = await asyncio.create_subprocess_exec(
        'ffmpeg', '-i', accompaniment_file, '-c:a', 'libmp3lame', '-b:a', '320k', output_file,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg conversion error: {stderr.decode()}")
    return output_file

async def mix_vocals_and_accompaniment(accompaniment_file, vocals_file, vocal_percentage, new_folder, base_name, output_format='mp3'):
    """
    Mix vocals into the accompaniment file based on the vocal percentage and convert to MP3 format.
    - The accompaniment file will remain at full volume.
    - The vocals file volume will be reduced according to the vocal_percentage.
    - The overall output volume will match the original accompaniment file.
    - High-quality output is ensured by using the highest variable bitrate for MP3.
    """
    # Define the output file path
    output_file = os.path.join(new_folder, f'{base_name}_accompaniment_{vocal_percentage}percent_320k.{output_format}')

    # Convert the vocal percentage to a decimal (0.0 - 1.0 scale)
    vocal_volume = vocal_percentage / 100.0
    accompaniment_volume = 1  # Full volume for accompaniment

    # FFmpeg filter complex to adjust vocal volume and retain full accompaniment volume
    filter_complex = (
        f"[0:a]volume={accompaniment_volume}[a];"  # Full volume for accompaniment
        f"[1:a]volume={vocal_volume}[v];"          # Adjusted vocal volume
        f"[a][v]amix=inputs=2:duration=longest"     # Mix accompaniment and vocals, keeping the longest duration
    )

    # Asynchronous subprocess call to run FFmpeg with higher quality audio output
    process = await asyncio.create_subprocess_exec(
        'ffmpeg', '-i', accompaniment_file, '-i', vocals_file,  # Input files
        '-filter_complex', filter_complex,                      # Apply filter complex
        '-c:a', 'libmp3lame', '-q:a', '0',                      # Highest quality VBR for MP3 output
        output_file,                                             # Output file path
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    # Await the completion of the FFmpeg process
    stdout, stderr = await process.communicate()

    # Check for errors and raise an exception if the process failed
    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg mixing error: {stderr.decode()}")

    # Return the path to the mixed output file
    return output_file


async def process_audio_file(input_name: str, vocal_percentage: int, output_format='mp3'):
    """Process audio file with specified vocal percentage mixed into accompaniment."""
    start_time = time.time()
    logging.info(f"Starting to process audio file: {input_name} with vocal percentage: {vocal_percentage}%")


    try:
        # Extract the directory and base name from the input name
        input_dir = os.path.dirname(input_name)
        base_name, input_ext = os.path.splitext(os.path.basename(input_name))

        # List of common audio file extensions
        extensions = ['.mp3', '.wav', '.flac', '.aac', '.m4a']

        # Find the actual file based on the input name and known extensions
        input_file = None
        if input_ext in extensions and os.path.exists(input_name):
            input_file = input_name
        else:
            for ext in extensions:
                possible_file = os.path.join(input_dir, f"{base_name}{ext}")
                if os.path.exists(possible_file):
                    input_file = possible_file
                    break
        
        if input_file is None:
            raise FileNotFoundError(f"No audio file found for base name: {base_name}")

        # Define output directory based on vocal percentage
        output_directory = f'./inputSongs{vocal_percentage}'
        os.makedirs(output_directory, exist_ok=True)

        # Step 1: Convert to WAV format if needed
        if not input_file.endswith('.wav'):
            wav_input_file = await convert_to_wav(input_file, output_directory, base_name)
        else:
            wav_input_file = input_file

        # Step 2: Separate vocals and accompaniment using Spleeter
        logging.info(f"Starting Spleeter separation for {wav_input_file}")
        await run_spleeter(wav_input_file, output_directory)
        logging.info(f"Completed Spleeter separation for {wav_input_file}")

        # Step 3: Extract accompaniment and vocal files
        accompaniment_file = os.path.join(output_directory, base_name, 'accompaniment.wav')
        vocals_file = os.path.join(output_directory, base_name, 'vocals.wav')

        # Check if the files exist before proceeding
        # Check if the files exist before proceeding
        if not os.path.exists(accompaniment_file):
            raise FileNotFoundError(f"Accompaniment file {accompaniment_file} does not exist.")
        if vocal_percentage > 0 and not os.path.exists(vocals_file):
            raise FileNotFoundError(f"Vocal file {vocals_file} does not exist.")

        # Log the vocal percentage before processing
        logging.info(f"Mixing with vocal percentage: {vocal_percentage}%")

        # Step 4: Convert accompaniment and mix with vocals based on vocal_percentage
        if vocal_percentage == 0:
            # No vocals, return the pure accompaniment file
            combined_output_file = await convert_accompaniment_to_mp3(accompaniment_file, output_directory, base_name, output_format)
        else:
            # Mix the specified percentage of vocals into the accompaniment
            combined_output_file = await mix_vocals_and_accompaniment(accompaniment_file, vocals_file, vocal_percentage, output_directory, base_name, output_format)

        # Clean up intermediate WAV files
        os.remove(accompaniment_file)
        if input_file != wav_input_file:
            os.remove(wav_input_file)

        # Clean memory after processing
        elapsed_time = time.time() - start_time
        logging.info(f"Processing completed in {elapsed_time:.2f} seconds.")
        
        return combined_output_file, output_directory

    except Exception as e:
        logging.error(f"Failed to process {input_name} due to an error: {e}", exc_info=True)
        return None, None