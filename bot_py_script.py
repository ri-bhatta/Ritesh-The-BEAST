import os
import json
import random
import time
import re
from datetime import datetime
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION ---
TARGET_SHEET = "IBPS_Bot_Data" 
RUNTIME_MINUTES = 5

print(f"🚀 STARTING BEAST BOT (Target: {TARGET_SHEET})...")

# --- 1. AUTHENTICATION ---
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GCP_CREDS_JSON = os.environ.get('GCP_CREDENTIALS')

if not GEMINI_KEY: print("❌ Error: GEMINI_API_KEY missing"); exit(1)
if not GCP_CREDS_JSON: print("❌ Error: GCP_CREDENTIALS missing"); exit(1)

genai.configure(api_key=GEMINI_KEY)

# --- 2. CONNECT TO DATABASE ---
print("📡 Connecting to Google Sheets...")
creds_dict = json.loads(GCP_CREDS_JSON)
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)

try:
    sh = client.open(TARGET_SHEET)
    print(f"✅ SUCCESS! Connected to '{TARGET_SHEET}'")
    print(f"🔗 Writing data to: {sh.url}")
    
    # Check/Add Headers
    ws = sh.get_worksheet(0)
    if not ws.row_values(1):
        ws.append_row(['ID','Date','Subject','Question','A','B','C','D','Correct','Explanation'])

except gspread.SpreadsheetNotFound:
    print(f"❌ ERROR: Cannot find '{TARGET_SHEET}'. Check permissions.")
    exit(1)

# --- 3. FORCE STABLE MODEL ---
# We are NOT guessing anymore. We are forcing the high-quota model.
MODEL_NAME = "models/gemini-1.5-flash"
print(f"🤖 Engine Locked: {MODEL_NAME}")

# --- 4. THE LOOP ---
start_time = time.time()
end_time = start_time + (RUNTIME_MINUTES * 60)

while time.time() < end_time:
    remaining = int(end_time - time.time())
    print(f"\n⏰ Time Remaining: {remaining}s | Generating Question...")

    try:
        sub = random.choice(['IT', 'Quant', 'Reasoning', 'English'])
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"""
        Generate 1 MCQ for IBPS SO exam on subject: {sub}.
        STRICT JSON. Keys: Question, A, B, C, D, Correct, Explanation.
        """
        
        resp = model.generate_content(prompt, request_options={"timeout": 30})
        
        # Parse
        match = re.search(r'\[.*\]|{.*}', resp.text.replace('\n', ' '), re.DOTALL)
        if match:
            json_str = match.group(0)
            if json_str.startswith('{'): json_str = f"[{json_str}]"
            data = json.loads(json_str)
            
            # Save
            ws = sh.get_worksheet(0)
            q = data[0]
            ws.append_row([
                f'AUTO-{int(time.time())}', 
                str(datetime.now()), 
                sub, 
                q.get('Question'), 
                q.get('A'), q.get('B'), q.get('C'), q.get('D'), 
                q.get('Correct'), 
                q.get('Explanation')
            ])
            print(f"   ✅ SUCCESS! Saved new question.")
            time.sleep(15) 
        else:
            print("   ⚠️ No JSON found.")
            time.sleep(5)

    except Exception as e:
        print(f"   ❌ Cycle Error: {e}")
        
        # If 1.5 Flash fails (404), switch to backup automatically
        if "404" in str(e):
            print("   ⚠️ 1.5 Flash not found. Switching to Gemini Pro...")
            MODEL_NAME = "models/gemini-pro"
            time.sleep(2)
        elif "429" in str(e): 
            print("   🛑 Quota hit. Waiting 60s...")
            time.sleep(60)
        else: 
            time.sleep(5)

print("\n🏁 Beast Bot finished.")
