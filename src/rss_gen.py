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

    # Find all m4a files
    files = glob.glob(os.path.join(recordings_dir, "*.m4a"))
    files.sort(reverse=True) # Newest first

    # RSS Header
    rss_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{escape(program_name)}</title>
    <description>Podcast feed for {escape(program_name)}</description>
    <link>{base_url}</link>
    <language>ko-kr</language>
    <itunes:author>Record Stream</itunes:author>
    <itunes:image href="{base_url}/image.jpg"/>
"""

    # Add items
    for file_path in files:
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        # Parse timestamp from filename (assuming format: name_YYYYMMDD_HHMMSS.m4a)
        try:
            timestamp_str = filename.split("_")[-1].replace(".m4a", "")
            # If timestamp has extra parts (e.g. from multiple underscores), take the last two
            if len(timestamp_str) > 15: # simple check
                 parts = filename.replace(".m4a", "").split("_")
                 timestamp_str = f"{parts[-2]}_{parts[-1]}"

            dt = datetime.datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            pub_date = dt.strftime("%a, %d %b %Y %H:%M:%S +0900")
        except Exception:
            # Fallback to file modification time if parsing fails
            dt = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
            pub_date = dt.strftime("%a, %d %b %Y %H:%M:%S +0900")

        # Create item entry
        # URL encoding for filename
        from urllib.parse import quote
        file_url = f"{base_url}/{safe_program_name}/{quote(filename)}"

        rss_content += f"""
    <item>
      <title>{escape(filename)}</title>
      <description>Recorded on {dt.strftime('%Y-%m-%d %H:%M')}</description>
      <pubDate>{pub_date}</pubDate>
      <enclosure url="{file_url}" length="{file_size}" type="audio/mp4"/>
      <guid isPermaLink="false">{filename}</guid>
    </item>"""

    # RSS Footer
    rss_content += """
  </channel>
</rss>
"""

    # Write to file
    with open(rss_path, "w", encoding="utf-8") as f:
        f.write(rss_content)
    
    print(f"[RSS Success] Feed updated: {rss_path}")

if __name__ == "__main__":
    # Test execution
    import sys
    if len(sys.argv) > 1:
        generate_rss(sys.argv[1])
    else:
        print("Usage: python rss_gen.py <program_name>")
