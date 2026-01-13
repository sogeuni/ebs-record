import argparse
import subprocess
import datetime
import sys
import os
from rss_gen import generate_rss

def record_stream(url, duration, program_name):
    """
    Record audio stream using ffmpeg.
    
    Args:
        url (str): Stream URL
        duration (int): Duration in seconds
        program_name (str): Program name (used for filename)
    """
    
    # Generate timestamp (YYYYMMDD_HHMMSS)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Replace spaces in program name with hyphens
    safe_program_name = program_name.replace(" ", "-")
    
    # Define output directory: recordings/program-name/
    base_dir = "recordings"
    program_dir = os.path.join(base_dir, safe_program_name)
    
    # Create directory if it doesn't exist
    os.makedirs(program_dir, exist_ok=True)
    
    filename = f"{safe_program_name}_{timestamp}.m4a"
    output_path = os.path.join(program_dir, filename)
    
    # Target: < 10MB for 20 mins (1200s)
    # 10MB / 1200s ≈ 69kbps
    # Set to 48kbps for safety margin (Expected ~7.2MB)
    # 48k AAC provides decent quality for speech-based radio
    bitrate = "48k"

    command = [
        "ffmpeg",
        "-i", url,            # Input URL
        "-t", str(duration),  # Duration
        "-vn",                # No video (Audio only)
        "-c:a", "aac",        # Audio codec: AAC
        "-b:a", bitrate,      # Bitrate
        "-y",                 # Overwrite output file
        output_path           # Save to specific path
    ]

    print(f"=== Recording Started ===")
    print(f"Program: {program_name}")
    print(f"URL: {url}")
    print(f"Duration: {duration}s ({duration/60:.1f}min)")
    print(f"Target Quality: {bitrate} (Approx. 7~8MB for 20min)")
    print(f"Output Path: {output_path}")
    print("=========================\n")
    
    try:
        # Run ffmpeg
        subprocess.run(command, check=True)
        print(f"\n[Success] Recording completed: {output_path}")
        
        # Update RSS Feed
        print(f"Updating RSS feed for: {program_name}")
        generate_rss(program_name)
        
    except subprocess.CalledProcessError as e:
        print(f"\n[Error] Recording failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[Cancelled] Recording interrupted by user.")
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FFmpeg Stream Recorder")
    
    parser.add_argument("url", help="Streaming URL (e.g., m3u8)")
    parser.add_argument("duration", type=int, help="Recording duration (seconds)")
    parser.add_argument("program_name", help="Program name")

    args = parser.parse_args()
    
    record_stream(args.url, args.duration, args.program_name)
