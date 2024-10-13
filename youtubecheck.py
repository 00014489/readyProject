import yt_dlp

def download_youtube_audio(url, output_path='./downloads'):
    try:
        # Set up options for downloading only audio
        ydl_opts = {
            'format': 'bestaudio/best',  # Get the best audio quality
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',  # Download as mp3
                'preferredquality': '192',  # Quality: 192kbps
            }],
            'outtmpl': f'{output_path}/%(title)s.%(ext)s',  # Save to file with title as the filename
        }

        # Download the audio
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print("Download completed successfully")
    except Exception as e:
        print(f"Error downloading audio: {e}")

# Example usage
youtube_url = "https://www.youtube.com/watch?v=rvRBY7x66Hk"
download_youtube_audio(youtube_url)
