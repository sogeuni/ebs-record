import os
import datetime
import glob
import json
from xml.sax.saxutils import escape

def load_config():
    """Load configuration from config.json"""
    config_path = "config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Config Warning] Failed to load config.json: {e}")
    return {}

def generate_rss(program_name, base_url=None):
    """
    Generate podcast RSS feed for a specific program.
    
    Args:
        program_name (str): Program name (directory name)
        base_url (str): Base URL for the podcast files.
                        If None, reads from config.json, or defaults to localhost.
    """
    
    # Resolve base_url
    if base_url is None:
        config = load_config()
        base_url = config.get("base_url", "http://localhost:8080")
    
    # Define paths
    safe_program_name = program_name.replace(" ", "-")
    recordings_dir = os.path.join("recordings", safe_program_name)
    rss_path = os.path.join(recordings_dir, "feed.xml")
    
    if not os.path.exists(recordings_dir):
        print(f"[RSS Error] Directory not found: {recordings_dir}")
        return

    # 1. Generate Metadata for NEW files (locally present)
    # We essentially look for m4a files in the current directory.
    # In the GitHub Action context, this will likely only be the latest recording.
    local_files = glob.glob(os.path.join(recordings_dir, "*.m4a"))
    local_items = []
    
    for file_path in local_files:
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        # Parse timestamp from filename (KST expected now)
        try:
            timestamp_str = filename.split("_")[-1].replace(".m4a", "")
            if len(timestamp_str) > 15: 
                 parts = filename.replace(".m4a", "").split("_")
                 timestamp_str = f"{parts[-2]}_{parts[-1]}"

            dt = datetime.datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            # Assume timestamp is already KST from recorder.py
            # Format: 'Tue, 13 Jan 2026 17:30:00 +0900'
            pub_date = dt.strftime("%a, %d %b %Y %H:%M:%S +0900")
            desc_date = dt.strftime('%Y-%m-%d %H:%M')
        except Exception:
            dt = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
            pub_date = dt.strftime("%a, %d %b %Y %H:%M:%S +0900")
            desc_date = dt.strftime('%Y-%m-%d %H:%M')

        # Create item content
        from urllib.parse import quote
        file_url = f"{base_url}/{quote(safe_program_name)}/{quote(filename)}"
        
        item_block = f"""    <item>
      <title>{escape(filename)}</title>
      <description>Recorded on {desc_date}</description>
      <pubDate>{pub_date}</pubDate>
      <enclosure url="{file_url}" length="{file_size}" type="audio/mp4"/>
      <guid isPermaLink="false">{filename}</guid>
    </item>"""
        local_items.append((filename, item_block))

    # 2. Read EXISTING feed.xml to preserve history
    existing_items = []
    header = ""
    footer = """  </channel>
</rss>"""

    if os.path.exists(rss_path):
        try:
            with open(rss_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Naive parsing to extract items
            # We look for <item> ... </item> blocks
            import re
            # Split into Header / Items / Footer
            # Assumption: Items start after <itunes:image ... /> or <language> tag? 
            # Safer: Regex find all items
            item_pattern = re.compile(r'(<item>.*?</item>)', re.DOTALL)
            found_items = item_pattern.findall(content)
            
            # Identify header (everything before first item)
            first_item_match = item_pattern.search(content)
            if first_item_match:
                header = content[:first_item_match.start()]
            else:
                # No items found, try to find end of channel/image
                # Fallback to generating fresh header if ambiguous
                pass
            
            for item in found_items:
                # Extract guid to prevent duplicates
                guid_match = re.search(r'<guid.*?>(.*?)</guid>', item)
                guid = guid_match.group(1) if guid_match else ""
                existing_items.append((guid, item))
                
        except Exception as e:
            print(f"[RSS Warning] Failed to parse existing feed.xml: {e}. Regenerating.")

    # 3. Combine Items (New + Old, Deduplicated)
    final_items = []
    seen_guids = set()
    
    # Add Local New Items First (Reverse Chronological intent)
    # Sort local items by filename desc (newest first)
    local_items.sort(key=lambda x: x[0], reverse=True)
    
    for fname, block in local_items:
        if fname not in seen_guids:
            final_items.append(block)
            seen_guids.add(fname)
            
    # Add Existing Items
    for guid, block in existing_items:
        if guid not in seen_guids:
            final_items.append(block)
            seen_guids.add(guid)

    # 4. Generate Final Content
    if not header:
        # Generate Header if missing
        header = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{escape(program_name)}</title>
    <description>Podcast feed for {escape(program_name)}</description>
    <link>{base_url}</link>
    <language>ko-kr</language>
    <itunes:author>Record Stream</itunes:author>
    <itunes:image href="{base_url}/image.jpg"/>
"""

    rss_content = header.strip() + "\n\n" + "\n".join(final_items) + "\n" + footer

    # Write to file
    with open(rss_path, "w", encoding="utf-8") as f:
        f.write(rss_content)
    
    print(f"[RSS Success] Feed updated: {rss_path} (Total items: {len(final_items)})")

if __name__ == "__main__":
    # Test execution
    import sys
    if len(sys.argv) > 1:
        generate_rss(sys.argv[1])
    else:
        print("Usage: python rss_gen.py <program_name>")
