import os
import json
import time
import re
from datetime import datetime
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials # Modern Auth

print("\n\n" + "="*40)
print("🚀 RUNNING NEW CODE - VERSION 2.0 🚀")
print("="*40 + "\n\n")

# --- 1. SETUP ---
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GCP_CREDS_JSON = os.environ.get('GCP_CREDENTIALS')

if not GEMINI_KEY: print("❌ Error: GEMINI_API_KEY missing"); exit(1)
if not GCP_CREDS_JSON: print("❌ Error: GCP_CREDENTIALS missing"); exit(1)

genai.configure(api_key=GEMINI_KEY)

# --- 2. GENERATE CONTENT (Simplified) ---
# We will just generate 1 question to test the connection quickly
print("🦁 Beast Bot Target: IT (Test Run)")
model = genai.GenerativeModel("models/gemini-2.0-flash-exp")

try:
    resp = model.generate_content(
        "Generate 1 MCQ for IT officers. Return JSON: [{'Question':..., 'A':..., 'Correct':...}]",
        generation_config={"response_mime_type": "application/json"}
    )
    data = json.loads(resp.text)
    print("✅ Gemini AI Generation Success")
except Exception as e:
    print(f"❌ Gemini Error: {e}")
    # Create fake data just to test the Sheet connection
    data = [{"Question": "Test Connection", "A": "1", "Correct": "A", "Topic": "Test", "Explanation": "None"}]

# --- 3. SAVE TO SHEETS (The Fix) ---
try:
    print("📡 Connecting to Google Sheets...")
    
    # Load the JSON key
    creds_dict = json.loads(GCP_CREDS_JSON)
    
    # USE THE SIMPLEST SCOPES (These are the official IDs)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # Modern Authentication
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # Open Sheet
    now = datetime.now()
    sheet_name = f'Questions_{now.year}_{now.month:02d}'
    
    try:
        sh = client.open(sheet_name)
        print(f"✅ Found Sheet: {sheet_name}")
    except:
        print(f"🆕 Creating Sheet: {sheet_name}")
        sh = client.create(sheet_name)
        sh.share(creds_dict['client_email'], perm_type='user', role='writer')
        sh.get_worksheet(0).append_row(['ID','Date','Topic','Question','A','B','C','D','E','Correct','Explanation'])

    # Save Data
    ws = sh.get_worksheet(0)
    row = [f'TEST-{int(time.time())}', str(now), 'IT', data[0].get('Question'), 'A', 'B', 'C', 'D', 'E', 'A', 'Test']
    ws.append_row(row)
    print(f"✅ SUCCESS! Saved test row to {sheet_name}")

except Exception as e:
    print(f"❌ Database Error: {e}")
    exit(1)
