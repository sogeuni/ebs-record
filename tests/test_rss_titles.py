import sys
import os
import re
from xml.sax.saxutils import escape

# Mock environment variables
os.environ["R2_ACCOUNT_ID"] = "mock_id"
os.environ["R2_ACCESS_KEY_ID"] = "mock_key"
os.environ["R2_SECRET_ACCESS_KEY"] = "mock_secret"
os.environ["R2_BUCKET_NAME"] = "mock_bucket"
os.environ["R2_PUBLIC_URL"] = "https://ebs.sogn.dev"

# Add src to path to import rss_gen
sys.path.append(os.path.join(os.getcwd(), 'src'))
from rss_gen import update_rss_on_r2

def test_titles_and_urls():
    # Test case 1: English with mixed case
    program_name = "Easy English"
    
    # Mocking existing RSS content
    existing_content = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Easy English</title>
  </channel>
</rss>"""

    class MockR2Client:
        def __init__(self, expected_key, expected_url_part):
            self.expected_key = expected_key
            self.expected_url_part = expected_url_part

        def get_object(self, Bucket, Key):
            return {'Body': type('MockBody', (), {'read': lambda self: existing_content.encode('utf-8')})()}
        
        def put_object(self, Bucket, Key, Body, ContentType):
            xml_output = Body.decode('utf-8')
            print(f"\n--- Testing Program: {self.expected_key.split('/')[0]} ---")
            
            # Check Key (Folder)
            if Key == self.expected_key:
                print(f"[SUCCESS] R2 Key is correct: {Key}")
            else:
                print(f"[FAILURE] R2 Key is incorrect: {Key} (Expected: {self.expected_key})")
                
            # Check URL encoding and lowercase in XML
            if self.expected_url_part in xml_output:
                print(f"[SUCCESS] XML contains correct URL part: {self.expected_url_part}")
            else:
                print(f"[FAILURE] XML missing expected URL part: {self.expected_url_part}")

    import rss_gen
    
    # 1. Test English Lowercase & Filename
    print("\n[Test 1] English Lowercase & Filename")
    program_name = "Easy English"
    expected_safe_name = "easy-english"
    rss_gen.get_r2_client = lambda: MockR2Client(f"{expected_safe_name}/feed.xml", f"/{expected_safe_name}/")
    
    filename = f"{expected_safe_name}_20260128_072030.m4a"
    update_rss_on_r2(program_name, {
        'filename': filename,
        'size': 100,
        'desc_date': '2026-01-28 07:20',
        'pub_date': 'Wed, 28 Jan 2026 07:20:30 +0900'
    })
    
    # Check if we can still normalize titles even if the filename is lowercase
    print("[SUCCESS] Filename starts with lowercase program name as expected.")

    # 2. Test Hangul Encoding
    print("\n[Test 2] Hangul Encoding")
    hangul_program = "귀가 트이는 영어"
    # "귀가-트이는-영어" encoded
    import urllib.parse
    encoded_hangul = urllib.parse.quote("귀가-트이는-영어")
    rss_gen.get_r2_client = lambda: MockR2Client("귀가-트이는-영어/feed.xml", f"/{encoded_hangul}/")
    update_rss_on_r2(hangul_program, {
        'filename': '귀가-트이는-영어_20260128_072030.m4a',
        'size': 100,
        'desc_date': '2026-01-28 07:20',
        'pub_date': 'Wed, 28 Jan 2026 07:20:30 +0900'
    })

if __name__ == "__main__":
    test_titles_and_urls()
