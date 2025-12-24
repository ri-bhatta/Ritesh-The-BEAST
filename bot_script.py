import os
import json
import random
import time
import re
from datetime import datetime
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION ---
RUNTIME_MINUTES = 5        # Run for 5 minutes
RETRY_DELAY = 60           # If 429 error, wait 60s (Google requirement)
MASTER_SHEET_NAME = "IBPS_Bot_Data"

# FORCE THE STABLE MODEL (No more auto-guessing)
MODEL_NAME = "models/gemini-1.5-flash" 

print(f"🚀 STARTING BEAST BOT LOOP (Model: {MODEL_NAME})...")

# --- 1. AUTHENTICATION ---
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GCP_CREDS_JSON = os.environ.get('GCP_CREDENTIALS')

if not GEMINI_KEY: print("❌ Error: GEMINI_API_KEY missing"); exit(1)
if not GCP_CREDS_JSON: print("❌ Error: GCP_CREDENTIALS missing"); exit(1)

genai.configure(api_key=GEMINI_KEY)

# --- 2. CONNECT TO DATABASE ---
try:
    print("📡 Connecting to Google Sheets...")
    creds_dict = json.loads(GCP_CREDS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    try:
        sh = client.open(MASTER_SHEET_NAME)
        print(f"✅ Connection Established: {MASTER_SHEET_NAME}")
    except gspread.SpreadsheetNotFound:
        print(f"❌ FATAL ERROR: Sheet '{MASTER_SHEET_NAME}' not found.")
        print("👉 ACTION: Create a blank Google Sheet named 'IBPS_Bot_Data' and share it with the bot email.")
        exit(1)
except Exception as e:
    print(f"❌ FATAL AUTH ERROR: {e}")
    exit(1)

# --- 3. THE LOOP ---
start_time = time.time()
end_time = start_time + (RUNTIME_MINUTES * 60)

while time.time() < end_time:
    remaining = int(end_time - time.time())
    print(f"\n⏰ Time Remaining: {remaining}s | Starting new cycle...")

    try:
        # --- A. GENERATE CONTENT ---
        sub = random.choice(['IT', 'Quant', 'Reasoning', 'English', 'Computer'])
        print(f"   🦁 Hunting for: {sub}")

        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"""
        Generate 3 MCQs for IBPS SO exam on subject: {sub}.
        STRICT JSON ONLY. No markdown.
        Format: [{{"Question": "...", "A": "...", "B": "...", "C": "...", "D": "...", "Correct": "A", "Explanation": "..."}}]
        """
        
        # Timeout set to 30s
        resp = model.generate_content(prompt, safety_settings=safety_settings, request_options={"timeout": 30})
        
        # --- B. PARSE JSON ---
        match = re.search(r'\[.*\]', resp.text, re.DOTALL)
        if not match:
            print("   ⚠️ No JSON found. Skipping this turn.")
            time.sleep(5)
            continue

        json_str = match.group(0)
        json_str = re.sub(r'(?<!\\)\n', ' ', json_str)
        data = json.loads(json_str)

        # --- C. SAVE TO SHEET ---
        ws = sh.get_worksheet(0)
        now = str(datetime.now())
        rows = []
        for q in data:
            rows.append([
                f'AUTO-{int(time.time())}', 
                now, 
                sub, 
                q.get('Question'), 
                q.get('A'), q.get('B'), q.get('C'), q.get('D'), 
                q.get('Correct'), 
                q.get('Explanation')
            ])
        
        ws.append_rows(rows)
        print(f"   ✅ SUCCESS! Added {len(data)} questions.")
        
        # Sleep 10s to be nice
        time.sleep(10)

    except Exception as e:
        # --- D. ERROR HANDLING (NO CRASHING) ---
        print(f"   ❌ ERROR this cycle: {e}")
        
        if "429" in str(e):
            print(f"   🛑 Quota Limit Hit. Sleeping for {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
        else:
            print("   🔄 Retrying quickly...")
            time.sleep(5)

print("\n🏁 TIMEOUT REACHED. Beast Bot finished.")
