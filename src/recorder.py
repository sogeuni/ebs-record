import argparse
import subprocess
import datetime
import sys
import os
import time
from rss_gen import generate_rss

def wait_for_start_time(scheduled_time_str=None):
    """
    Waits until the scheduled start time in KST (UTC+9).
    If scheduled_time_str (HH:MM) is provided:
      - Calculate target datetime in KST.
      - If current KST < target: Wait difference.
      - If current KST >= target: Return immediately (no wait).
    If not provided:
      - Implicit behavior: Wait for next minute :00 if close to minute end?
      - Or just return immediately (logic removed in previous step, implicitly).
      - Let's restore simple next-minute alignment if no time is given?
      - User said "If start_time is missing, behave as before?"
      - Actually, user just said "If before start_time, sleep; if after, run immediately".
      - So I will implement exactly that.
    """
    kst_timezone = datetime.timezone(datetime.timedelta(hours=9))
    now_kst = datetime.datetime.now(kst_timezone)
    
    if scheduled_time_str:
        try:
            # Parse HH:MM
            target_hm = datetime.datetime.strptime(scheduled_time_str, "%H:%M").time()
            target_time = now_kst.replace(hour=target_hm.hour, minute=target_hm.minute, second=0, microsecond=0)
            
            # If target is much earlier (e.g. yesterday's time?), handle wrapping?
            # Assuming broadcast is "today".
            # BUT: If we trigger at 23:59 UTC (08:59 KST) for a 09:00 KST show, it works.
            # If we trigger at 07:18 KST for 07:20 KST show.
            
            diff = (target_time - now_kst).total_seconds()
            
            if diff > 0:
                print(f"[Wait] Current KST: {now_kst.strftime('%H:%M:%S')}")
                print(f"[Wait] Scheduled KST: {target_time.strftime('%H:%M:%S')}")
                print(f"[Wait] Sleeping for {diff:.2f} seconds...")
                time.sleep(diff)
                print(f"[Wait] Resuming at {datetime.datetime.now(kst_timezone).strftime('%H:%M:%S')}")
            else:
                print(f"[Wait] Current KST ({now_kst.strftime('%H:%M:%S')}) is past scheduled time ({target_time.strftime('%H:%M:%S')}). Starting immediately.")
        except ValueError as e:
            print(f"[Wait Warning] Invalid scheduled_time format: {scheduled_time_str} ({e})")
            pass
    else:
        # Fallback: Just align to next second 00 if needed?
        # Or simple immediate start.
        # Given "Safe to run late", we can just return.
        pass

def record_stream(url, duration, program_name, scheduled_time=None):
    # Wait for precise start
    wait_for_start_time(scheduled_time)

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
    
    # Target: ~10MB for 20 mins
    # Increased from 48k to 64k for better quality
    bitrate = "64k"

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
    parser.add_argument("--scheduled_time", help="Scheduled start time (HH:MM KST)", default=None)

    args = parser.parse_args()
    
    record_stream(args.url, args.duration, args.program_name, args.scheduled_time)
