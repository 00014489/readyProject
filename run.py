import os
import logging
import time
import asyncio
from spleeter.separator import Separator
import tensorflow as tf

# Configure logging
logging.basicConfig(level=logging.INFO)

# TensorFlow configuration
try:
    gpus = tf.config.experimental.list_physical_devices('GPU')
    if gpus:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
except RuntimeError as e:
    logging.error(f"Error setting TensorFlow memory growth: {e}")

# Enable eager execution for TensorFlow
tf.config.run_functions_eagerly(True)

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
    
    # Clear the previous session to avoid any conflicts
    tf.keras.backend.clear_session()

    # Run Spleeter's TensorFlow-based operation in an executor
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
    """Mix vocals into the accompaniment file based on the vocal percentage and convert to MP3 format."""
    output_file = os.path.join(new_folder, f'{base_name}_accompaniment_{vocal_percentage}percent_320k.{output_format}')

    vocal_volume = vocal_percentage / 100.0
    accompaniment_volume = 1  # Full volume for accompaniment

    filter_complex = (
        f"[0:a]volume={accompaniment_volume}[a];"
        f"[1:a]volume={vocal_volume}[v];"
        f"[a][v]amix=inputs=2:duration=longest"
    )

    process = await asyncio.create_subprocess_exec(
        'ffmpeg', '-i', accompaniment_file, '-i', vocals_file,
        '-filter_complex', filter_complex,
        '-c:a', 'libmp3lame', '-q:a', '0',
        output_file,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg mixing error: {stderr.decode()}")

    return output_file

async def process_audio_file(input_name: str, vocal_percentage: int, id_input: int, output_format='mp3'):
    """Process audio file with specified vocal percentage mixed into accompaniment."""
    start_time = time.time()
    logging.info(f"Starting to process audio file: {input_name} with vocal percentage: {vocal_percentage}%")


    input_dir = os.path.dirname(input_name)
    base_name, input_ext = os.path.splitext(os.path.basename(input_name))

    extensions = ['.mp3', '.wav', '.flac', '.aac', '.m4a']
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

    output_directory = f'./inputSongs{vocal_percentage}:{id_input}'
    os.makedirs(output_directory, exist_ok=True)

    if not input_file.endswith('.wav'):
        wav_input_file = await convert_to_wav(input_file, output_directory, base_name)
    else:
        wav_input_file = input_file

    logging.info(f"Starting Spleeter separation for {wav_input_file}")
    await run_spleeter(wav_input_file, output_directory)
    logging.info(f"Completed Spleeter separation for {wav_input_file}")

    accompaniment_file = os.path.join(output_directory, base_name, 'accompaniment.wav')
    vocals_file = os.path.join(output_directory, base_name, 'vocals.wav')

    if not os.path.exists(accompaniment_file):
        raise FileNotFoundError(f"Accompaniment file {accompaniment_file} does not exist.")
    if vocal_percentage > 0 and not os.path.exists(vocals_file):
        raise FileNotFoundError(f"Vocal file {vocals_file} does not exist.")

    logging.info(f"Mixing with vocal percentage: {vocal_percentage}%")

    if vocal_percentage == 0:
        combined_output_file = await convert_accompaniment_to_mp3(accompaniment_file, output_directory, base_name, output_format)
    else:
        combined_output_file = await mix_vocals_and_accompaniment(accompaniment_file, vocals_file, vocal_percentage, output_directory, base_name, output_format)

    os.remove(accompaniment_file)
    if input_file != wav_input_file:
        os.remove(wav_input_file)

    elapsed_time = time.time() - start_time
    logging.info(f"Processing completed in {elapsed_time:.2f} seconds.")
    
    return combined_output_file, output_directory