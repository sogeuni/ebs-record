import os
import datetime
import json
import boto3
from botocore.exceptions import ClientError
from xml.sax.saxutils import escape

# Environment Variables
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")
R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL")

def get_r2_client():
    if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
        print("[RSS Error] Missing R2 Credentials")
        return None
        
    return boto3.client(
        's3',
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY
    )

def update_rss_on_r2(program_name, file_metadata):
    """
    Fetch existing feed.xml from R2, append new item, and upload back.
    
    Args:
        program_name (str): Program name (used for folder structure)
        file_metadata (dict): {
            'filename': '...',
            'size': 12345,
            'desc_date': 'YYYY-MM-DD HH:MM',
            'pub_date': 'Mon, ... +0900'
        }
    """
    client = get_r2_client()
    if not client:
        return

    safe_program_name = program_name.replace(" ", "-").lower()
    feed_key = f"{safe_program_name}/feed.xml"
    
    # 1. Fetch Existing Feed
    existing_content = ""
    try:
        response = client.get_object(Bucket=R2_BUCKET_NAME, Key=feed_key)
        existing_content = response['Body'].read().decode('utf-8')
        print(f"[RSS Info] Fetched existing feed.xml for {program_name}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print(f"[RSS Info] No existing feed.xml found. Creating new one.")
        else:
            print(f"[RSS Error] Failed to fetch feed: {e}")
            return

    # 2. Add New Item
    from urllib.parse import quote
    
    filename = file_metadata['filename']
    file_size = file_metadata['size']
    desc_date = file_metadata['desc_date']
    pub_date = file_metadata['pub_date']
    
    # New Format: Program Name (YYYY-MM-DD)
    # Extract date part from desc_date (YYYY-MM-DD HH:MM)
    date_only = desc_date.split(' ')[0]
    display_title = f"{program_name} ({date_only})"

    # R2 Public URL
    file_url = f"{R2_PUBLIC_URL}/{quote(safe_program_name)}/{quote(filename)}"

    new_item = f"""    <item>
      <title>{escape(display_title)}</title>
      <description>Recorded on {desc_date}</description>
      <pubDate>{pub_date}</pubDate>
      <enclosure url="{file_url}" length="{file_size}" type="audio/mp4"/>
      <guid isPermaLink="false">{filename}</guid>
    </item>"""

    # 3. Construct/Update XML
    header = ""
    footer = """  </channel>
</rss>"""
    body_items = []

    if existing_content:
        # Simple string manipulation to insert new item after <channel> or before footer?
        # A robust way: Parse items or simply prepend to existing items list?
        # Let's extract existing items using regex as before.
        import re
        item_pattern = re.compile(r'(<item>.*?</item>)', re.DOTALL)
        found_items = item_pattern.findall(existing_content)
        
        # Extract Header
        first_item_match = item_pattern.search(existing_content)
        if first_item_match:
            header = existing_content[:first_item_match.start()].strip()
        else:
            # If no items but file exists (header only), find </channel>
            split_idx = existing_content.find("</channel>")
            if split_idx != -1:
                header = existing_content[:split_idx].strip()
            else:
                # Fallback
                header = ""

        # Check dupes and Normalize existing titles
        seen_guids = set()
        for item in found_items:
            guid_match = re.search(r'<guid.*?>(.*?)</guid>', item)
            if guid_match:
                guid = guid_match.group(1)
                seen_guids.add(guid)
                
                # If title is in filename format, convert it
                # Example: Easy-English_20260128_072030.m4a -> Easy English (2026-01-28)
                title_match = re.search(r'<title>(.*?)</title>', item)
                if title_match:
                    current_title = title_match.group(1)
                    # Simple heuristic: if it ends with .m4a and contains _YYYYMMDD_
                    if current_title.endswith('.m4a') and '_' in current_title:
                        # Try to extract date
                        date_parts = re.search(r'_(\d{4})(\d{2})(\d{2})_', current_title)
                        if date_parts:
                            y, m, d = date_parts.groups()
                            new_title = f"{program_name} ({y}-{m}-{d})"
                            item = item.replace(f"<title>{current_title}</title>", f"<title>{escape(new_title)}</title>")
            
            body_items.append(item)
        
        if filename not in seen_guids:
            # Add NEW item to the TOP (Prepend)
            body_items.insert(0, new_item)
    else:
        # Create Header
        header = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{escape(program_name)}</title>
    <description>Podcast feed for {escape(program_name)}</description>
    <link>{R2_PUBLIC_URL}</link>
    <language>ko-kr</language>
    <itunes:author>Record Stream</itunes:author>
    <itunes:image href="{R2_PUBLIC_URL}/image.jpg"/>"""
        body_items.append(new_item)

    # 4. Upload Updated Feed
    final_xml = header + "\n\n" + "\n".join(body_items) + "\n" + footer
    
    try:
        client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=feed_key,
            Body=final_xml.encode('utf-8'),
            ContentType="application/xml",
            # ACL='public-read' # Not needed if bucket is public or behind worker
        )
        print(f"[RSS Success] Updated feed.xml on R2 for {program_name}")
    except Exception as e:
         print(f"[RSS Error] Failed to upload feed: {e}")

if __name__ == "__main__":
    pass
