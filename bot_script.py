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
RUNTIME_MINUTES = 5       # Run for 5 minutes
RETRY_DELAY = 10          # Wait 10s if it fails
SUCCESS_DELAY = 15        # Wait 15s after success (to save quota)
MASTER_SHEET_NAME = "IBPS_Bot_Data"

print(f"🚀 STARTING BEAST BOT LOOP (Running for {RUNTIME_MINUTES} mins)...")

# --- 1. AUTHENTICATION (Do this once) ---
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GCP_CREDS_JSON = os.environ.get('GCP_CREDENTIALS')

if not GEMINI_KEY: print("❌ Error: GEMINI_API_KEY missing"); exit(1)
if not GCP_CREDS_JSON: print("❌ Error: GCP_CREDENTIALS missing"); exit(1)

genai.configure(api_key=GEMINI_KEY)

# Smart Model Selector
def get_valid_model():
    try:
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-1.0-pro']
        for p in priority:
            for m in all_models:
                if p in m: return m
        return all_models[0]
    except:
        return "models/gemini-1.5-flash"

active_model_name = get_valid_model()
print(f"🤖 Engine Selected: {active_model_name}")

# --- 2. CONNECT TO DATABASE (Do this once) ---
try:
    print("📡 Connecting to Google Sheets...")
    creds_dict = json.loads(GCP_CREDS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # Verify Sheet Exists
    try:
        sh = client.open(MASTER_SHEET_NAME)
        print(f"✅ Connection Established: {MASTER_SHEET_NAME}")
    except gspread.SpreadsheetNotFound:
        print(f"❌ FATAL ERROR: Sheet '{MASTER_SHEET_NAME}' not found.")
        print("👉 Please create 'IBPS_Bot_Data' in Google Drive and share it with the bot.")
        exit(1)
except Exception as e:
    print(f"❌ FATAL AUTH ERROR: {e}")
    exit(1)

# --- 3. THE LOOP (Running for 5 Minutes) ---
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

        model = genai.GenerativeModel(active_model_name)
        prompt = f"""
        Generate 3 MCQs for IBPS SO exam on subject: {sub}.
        STRICT JSON ONLY. No markdown.
        Format: [{{"Question": "...", "A": "...", "B": "...", "C": "...", "D": "...", "Correct": "A", "Explanation": "..."}}]
        """
        
        # Timeout set to 30s to prevent hanging
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
        
        # Sleep to be nice to Google API
        print(f"   💤 Resting for {SUCCESS_DELAY}s...")
        time.sleep(SUCCESS_DELAY)

    except Exception as e:
        print(f"   ❌ ERROR this cycle: {e}")
        print(f"   🔄 Retrying in {RETRY_DELAY}s...")
        time.sleep(RETRY_DELAY)

print("\n🏁 TIMEOUT REACHED. Beast Bot going to sleep.")
