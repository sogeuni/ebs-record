import argparse
import subprocess
import datetime
import sys
import os
import time
import json
import boto3
from botocore.exceptions import ClientError
from rss_gen import update_rss_on_r2

# Environment Variables for R2
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")

def get_r2_client():
    if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
        print("[Upload Error] Missing R2 Credentials")
        return None
        
    return boto3.client(
        's3',
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY
    )

def upload_to_r2(local_path, object_name):
    client = get_r2_client()
    if not client:
        return False

    try:
        print(f"[Upload] Uploading {local_path} to R2 ({R2_BUCKET_NAME}/{object_name})...")
        client.upload_file(local_path, R2_BUCKET_NAME, object_name)
        print(f"[Upload] Success!")
        return True
    except ClientError as e:
        print(f"[Upload Error] {e}")
        return False

def wait_for_start_time(scheduled_time_str=None):
    """
    Waits until the scheduled start time in KST (UTC+9).
    """
    kst_timezone = datetime.timezone(datetime.timedelta(hours=9))
    now_kst = datetime.datetime.now(kst_timezone)
    
    if scheduled_time_str:
        try:
            # Parse HH:MM or HH:MM:SS
            try:
                target_hm = datetime.datetime.strptime(scheduled_time_str, "%H:%M:%S").time()
            except ValueError:
                target_hm = datetime.datetime.strptime(scheduled_time_str, "%H:%M").time()
            
            target_time = now_kst.replace(hour=target_hm.hour, minute=target_hm.minute, second=target_hm.second, microsecond=0)
            
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

def resolve_schedule(schedule_file, time_slot):
    """
    Load schedule.json and find the program for the given time slot (HH:MM UTC).
    Handles day-specific logic for arrays.
    """
    try:
        with open(schedule_file, 'r', encoding='utf-8') as f:
            schedule_map = json.load(f)
    except FileNotFoundError:
        print(f"[Schedule Error] Schedule file not found: {schedule_file}")
        return None
    except json.JSONDecodeError as e:
        print(f"[Schedule Error] Invalid JSON in {schedule_file}: {e}")
        return None

    entry = schedule_map.get(time_slot)
    if not entry:
        print(f"[Schedule Error] No entry found for time slot: {time_slot}")
        return None

    # Determine current UTC Day (0=Monday ... 6=Sunday for Python datetime.weekday())
    # BUT Cloudflare Crons & JS getUTCDay() use 0=Sunday, 6=Saturday.
    # We must match the JSON 'days' array which uses JS convention (0,1,2 for Sun,Mon,Tue).
    # Python weekday(): 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun.
    # Conversion: (weekday + 1) % 7 => 0=Sun, 1=Mon, 2=Tue...
    
    python_weekday = datetime.datetime.utcnow().weekday()
    current_utc_day = (python_weekday + 1) % 7
    
    print(f"[Schedule] Resolving for Time Slot: {time_slot} (UTC), Day: {current_utc_day} (Sun=0)")

    task = None
    if isinstance(entry, list):
        # Array: Find matching day
        for t in entry:
            if 'days' not in t or current_utc_day in t['days']:
                task = t
                break
    else:
        # Object: Check days if present
        if 'days' not in entry or current_utc_day in entry['days']:
            task = entry

    if not task:
        print(f"[Schedule] No valid task found for today (Day {current_utc_day}).")
        return None
        
    print(f"[Schedule] Matched Program: {task['program_name']}")
    return task

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
    
    # Target: Optimize for language learning (Voice)
    # Strategy: Downmix to Mono (-ac 1) + 56k Bitrate
    # 56k provides a quality boost over 48k while remaining efficient.
    # File size: ~8.4MB for 20 mins.
    bitrate = "56k"

    # Prepare Metadata
    date_str = datetime.datetime.now(kst_timezone).strftime("%Y-%m-%d")
    year_str = datetime.datetime.now(kst_timezone).strftime("%Y")
    display_title = f"{program_name} ({date_str})"
    
    command = [
        "ffmpeg",
        "-i", url,            # Input URL
        "-t", str(duration),  # Duration
        "-vn",                # No video (Audio only)
        "-c:a", "aac",        # Audio codec: Native AAC
        "-ac", "1",           # Downmix to Mono (Efficient for speech)
        "-b:a", bitrate,      # Bitrate
        "-metadata", f"title={display_title}",
        "-metadata", "artist=EBS",
        "-metadata", f"album={program_name}",
        "-metadata", f"year={year_str}",
        "-metadata", "genre=Podcast",
        "-metadata", "comment=Recorded by EBS-Record",
        "-y",                 # Overwrite output file
        output_path           # Save to specific path
    ]

    print(f"=== Recording Started ===")
    print(f"Program: {program_name}")
    print(f"URL: {url}")
    print(f"Duration: {duration}s ({duration/60:.1f}min)")
    print(f"Target Quality: {bitrate} Mono")
    print(f"Output Path: {output_path}")
    print("=========================\n")
    
    try:
        # Run ffmpeg
        subprocess.run(command, check=True)
        print(f"\n[Success] Recording completed: {output_path}")
        
        # Upload to R2
        file_size = os.path.getsize(output_path)
        object_name = f"{safe_program_name}/{filename}"
        
        if upload_to_r2(output_path, object_name):
            # Update RSS Feed on R2
            print(f"Updating RSS feed on R2 for: {program_name}")
            
            # Prepare metadata for RSS
            # Timestamps
            dt = datetime.datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
            pub_date = dt.strftime("%a, %d %b %Y %H:%M:%S +0900")
            desc_date = dt.strftime('%Y-%m-%d %H:%M')
            
            metadata = {
                'filename': filename,
                'size': file_size,
                'desc_date': desc_date,
                'pub_date': pub_date
            }
            
            update_rss_on_r2(program_name, metadata)
            
            # Cleanup Local File
            print(f"[Cleanup] Removing local file: {output_path}")
            os.remove(output_path)
        else:
            print("[Error] Failed to upload to R2. Keeping local file.")
            sys.exit(1) # Fail workflow to notify user
        
    except subprocess.CalledProcessError as e:
        print(f"\n[Error] Recording failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[Cancelled] Recording interrupted by user.")
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FFmpeg Stream Recorder")
    
    # Arguments
    parser.add_argument("--url", help="Streaming URL (e.g., m3u8). Defaults to STREAM_URL env var.")
    parser.add_argument("--program_name", help="Program name (Manual override)")
    parser.add_argument("--duration", type=int, help="Recording duration (seconds)", default=10)
    parser.add_argument("--scheduled_time", help="Scheduled start time (HH:MM KST)", default=None)
    
    # New Arguments for Schedule-Based Execution
    parser.add_argument("--schedule_file", help="Path to schedule.json", default="schedule.json")
    parser.add_argument("--time_slot", help="Time slot key (HH:MM) to verify against schedule")

    args = parser.parse_args()
    
    # Resolve Schedule if time_slot is provided
    final_program_name = args.program_name
    final_duration = args.duration
    final_scheduled_time = args.scheduled_time
    
    if args.time_slot:
        print(f"[Info] Running in Schedule Mode for Time Slot: {args.time_slot}")
        task = resolve_schedule(args.schedule_file, args.time_slot)
        if task:
            final_program_name = task.get('program_name')
            final_duration = task.get('duration', args.duration)
            final_scheduled_time = task.get('scheduled_time', args.scheduled_time)
        else:
            print(f"[Info] No task skipped or not found. Exiting gracefully.")
            sys.exit(0)
            
    if not final_program_name:
        print("[Error] program_name is required (either via --program_name or --time_slot match).")
        sys.exit(1)

    # Resolve URL: Argument > Environment Variable
    final_url = args.url or os.environ.get("STREAM_URL")
    if not final_url:
        print("[Error] No stream URL provided via --url or STREAM_URL environment variable.")
        sys.exit(1)

    record_stream(final_url, final_duration, final_program_name, final_scheduled_time)
