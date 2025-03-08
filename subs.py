import sys
import os
import json
import subprocess
import logging
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        return False

def get_subtitle_streams(video_file):
    try:
        # Get video file information in JSON format
        process = subprocess.Popen([
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-select_streams", "s",
            video_file
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False)
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            logging.error(f"FFprobe error: {stderr.decode('utf-8', errors='replace')}")
            return []
            
        # Decode the output using utf-8 with error handling
        try:
            output = stdout.decode('utf-8', errors='replace')
            info = json.loads(output)
            return info.get("streams", [])
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON: {e}")
            return []
            
    except Exception as e:
        logging.error(f"Error getting subtitle information: {str(e)}")
        return []

def extract_subtitles(video_file):
    logging.info(f"Starting subtitle extraction for: {video_file}")

    # Get the file name without extension and the directory
    file_name = os.path.splitext(video_file)[0]
    directory = os.path.dirname(video_file)

    # Get subtitle streams
    subtitle_streams = get_subtitle_streams(video_file)
    logging.info(f"Found {len(subtitle_streams)} subtitle stream(s).")

    if not subtitle_streams:
        logging.warning("No subtitle streams found in the video file.")
        return

    # Dictionary to keep track of the number of streams per language
    lang_count = defaultdict(int)

    for index, stream in enumerate(subtitle_streams):
        # Get language tag or use 'und' with stream index if not available
        lang = stream.get("tags", {}).get("language", f"und_{index}")
        
        # Increment the count for this language
        lang_count[lang] += 1
        count = lang_count[lang]

        # Determine suffix for filename if multiple streams share the same language
        if count > 1:
            suffix = f"_{count}"
        else:
            suffix = ""

        # Output SRT file path with unique filename
        srt_file = os.path.join(directory, f"{file_name}.{lang}{suffix}.srt")

        logging.info(f"Processing subtitle stream {index}: Language='{lang}', Output='{srt_file}'")

        try:
            # Extract subtitles using ffmpeg with specified format and without capturing output
            subprocess.run([
                "ffmpeg",
                "-i", video_file,
                "-map", f"0:s:{index}",
                "-f", "srt",
                srt_file
            ], check=True)
            logging.info(f"Subtitles extracted successfully: {srt_file}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error extracting subtitles for stream {index}: {e}")

if __name__ == "__main__":
    if not check_ffmpeg():
        logging.error("FFmpeg is not installed or not in your system PATH.")
        logging.info("Please install FFmpeg and ensure it's accessible from the command line.")
        sys.exit(1)

    if len(sys.argv) != 2:
        logging.error("Usage: python subs.py <video_file>")
        sys.exit(1)

    video_file = sys.argv[1]
    if not os.path.exists(video_file):
        logging.error(f"Error: File '{video_file}' not found.")
        sys.exit(1)

    extract_subtitles(video_file)