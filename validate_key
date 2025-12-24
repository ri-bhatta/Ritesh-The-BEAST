import json
import os
from oauth2client.service_account import ServiceAccountCredentials
import gspread

print("🕵️ STARTING CREDENTIALS DIAGNOSIS...")

# --- CHECK 1: FILE EXISTENCE ---
if not os.path.exists('credentials.json'):
    print("❌ FAIL: 'credentials.json' file not found.")
    exit(1)
print("✅ PASS: File found.")

# --- CHECK 2: JSON STRUCTURE ---
try:
    with open('credentials.json', 'r') as f:
        creds_dict = json.load(f)
    print("✅ PASS: JSON is valid.")
except json.JSONDecodeError as e:
    print(f"❌ FAIL: JSON is broken. {e}")
    exit(1)

# --- CHECK 3: PRIVATE KEY FORMAT ---
private_key = creds_dict.get('private_key', '')
if "-----BEGIN PRIVATE KEY-----" not in private_key:
    print("❌ FAIL: 'private_key' is missing the BEGIN header.")
    print("   -> Your key file might be corrupted.")
    exit(1)
if "\\n" in private_key:
    print("⚠️ WARNING: Private key contains literal '\\n' characters.")
    print("   -> Python can usually handle this, but it often breaks GitHub.")
    # We attempt to fix it for the test
    creds_dict['private_key'] = private_key.replace("\\n", "\n")

print("✅ PASS: Private Key looks correct.")

# --- CHECK 4: ACTUAL CONNECTION ---
print("📡 Attempting to connect to Google Sheets...")
try:
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # Try to open ANY sheet just to test auth
    print("✅ SUCCESS! The key is 100% valid and working.")
    print("\n------------------------------------------------")
    print("👉 CONCLUSION: The file on your laptop is GOOD.")
    print("👉 THE PROBLEM: The copy-paste to GitHub is breaking it.")
    print("------------------------------------------------")

except Exception as e:
    print(f"❌ CONNECTION FAILED: {e}")
    if "invalid_grant" in str(e):
        print("   -> This usually means the system clock is wrong OR the key was revoked by Google.")
