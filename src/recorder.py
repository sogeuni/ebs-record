import argparse
import subprocess
import datetime
import sys
import os
import time
from rss_gen import generate_rss

def wait_for_start_time():
    """
    Waits until the beginning of the next minute (second 00).
    Cloudflare triggers should be set to 1 minute early (e.g., 59).
    This function will then sleep until 00 seconds of the next minute for precise start.
    """
    now = datetime.datetime.now()
    # Target the next full minute? 
    # Actually, if we trigger at 58, we might want to wait for 00.
    # But for simplicity and robustness, let's just align to the next 00 seconds
    # UNLESS we are already currently at 00 (rare).
    
    # However, user wants SPECIFIC time. 
    # Let's simple wait until the seconds are 00.
    # If we are at 58:50, we wait 10s -> 59:00. 
    # If our goal is 00:00 (2 mins later), we might need an argument.
    # But wait, if we just wait for the next :00, we might record at 59:00 instead of 00:00.
    #
    # Revised strategy: receive `target_time` from arguments would be best,
    # but to keep it simple without changing yml schema too much:
    # Just wait until `datetime.datetime.now().second == 0`? 
    # If we trigger 2 mins early, we might Record 1 min early if we just wait for "next :00".
    
    # LET'S DO THIS:
    # We will pass an argument --wait-seconds if needed, OR:
    # Just print "Waiting for next minute start..." and wait for `second=0`.
    # And we rely on the Schedule to be `*-1 minute` or `*-2 minute`?
    # Actually, if we set cron to `58`, and we wait for `00`, we might hit `59:00`.
    # We need to hit `00:00`.
    
    # Better approach:
    # We assume the program starts at specific 10-minute intervals usually (or 5 min).
    # Let's add a robust wait:
    # Calculate seconds until next 5-minute mark? Or next 1-minute mark?
    # User said "5분마다... 5분 0초에 실행되길".
    # So if it runs at 4:53, we want to wait for 5:00. (7s wait)
    # If it runs at 3:53 (early trigger), we want to wait for 5:00 (67s wait).
    
    # Let's take an optional argument for "Wait until next X minute mark" or simply:
    # "Wait until the start of the next minute that is a multiple of 5?" -> Test only.
    # For real usage (Easy English 7:20), we need to wait for 7:20:00.
    
    # Simplest universal fix:
    # Add `--precise-start` flag.
    # If set, wait until `seconds == 0`.
    # AND, if we want to support 2-min early trigger, maybe we need to wait until `minute % 5 == 0`?
    # No, that breaks 7:20 (ok) but also 7:22 (if schedule changes).
    
    # PROPOSAL:
    # Just wait for the next `second==0`.
    # AND update Cloudflare to trigger at `XX:59` (1 min early).
    # Then we wait max 60 seconds. Usually we will be at `59:20` -> wait 40s -> `00:00`.
    # This is safe and simple.
    
    next_minute = (now + datetime.timedelta(minutes=1)).replace(second=0, microsecond=0)
    wait_seconds = (next_minute - now).total_seconds()
    
    print(f"Current time: {now.strftime('%H:%M:%S')}")
    print(f"Waiting {wait_seconds:.2f}s for precise start at {next_minute.strftime('%H:%M:%S')}...")
    
    time.sleep(wait_seconds)
    print(f"Resuming at: {datetime.datetime.now().strftime('%H:%M:%S')}")

def record_stream(url, duration, program_name):
    # ... (header same)
    
    # Wait for precise start
    wait_for_start_time(start_time)

    # Generate timestamp (YYYYMMDD_HHMMSS) in KST (UTC+9)
    kst_timezone = datetime.timezone(datetime.timedelta(hours=9))
    timestamp = datetime.datetime.now(kst_timezone).strftime("%Y%m%d_%H%M%S")
    
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
    
    record_stream(args.url, args.duration, args.program_name, args.start_time)
