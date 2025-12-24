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
DELAY_SECONDS = 30  # Increased to 30s to prevent 429 Errors

print(f"🚀 STARTING BEAST BOT v5.0 (Printing enabled)...")

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
    
    # Check/Add Headers
    ws = sh.get_worksheet(0)
    if not ws.row_values(1):
        ws.append_row(['ID','Date','Subject','Question','A','B','C','D','Correct','Explanation'])

except gspread.SpreadsheetNotFound:
    print(f"❌ ERROR: Could not find '{TARGET_SHEET}'. Check permissions.")
    exit(1)

# --- 3. AUTO-DETECT MODEL ---
def get_model():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Prioritize 1.5-flash for best free tier limits
        if 'models/gemini-1.5-flash' in models: return 'models/gemini-1.5-flash'
        return models[0] if models else "models/gemini-pro"
    except: return "models/gemini-pro"

MODEL_NAME = get_model()
print(f"🤖 Engine: {MODEL_NAME}")

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
            q = data[0]

            # --- PRINT TO SCREEN ---
            print("\n" + "="*40)
            print(f"🦁 Subject: {sub}")
            print(f"❓ Question: {q.get('Question')}")
            print(f"   A) {q.get('A')}")
            print(f"   B) {q.get('B')}")
            print(f"   C) {q.get('C')}")
            print(f"   D) {q.get('D')}")
            print(f"✅ Correct: {q.get('Correct')}")
            print("="*40 + "\n")
            
            # Save to Sheet
            ws = sh.get_worksheet(0)
            ws.append_row([
                f'AUTO-{int(time.time())}', 
                str(datetime.now()), 
                sub, 
                q.get('Question'), 
                q.get('A'), q.get('B'), q.get('C'), q.get('D'), 
                q.get('Correct'), 
                q.get('Explanation')
            ])
            print(f"   ✅ SAVED to Google Sheet. Sleeping {DELAY_SECONDS}s...")
            time.sleep(DELAY_SECONDS) 
        else:
            print("   ⚠️ No JSON found.")
            time.sleep(10)

    except Exception as e:
        # If Quota Exceeded, wait a full minute
        if "429" in str(e): 
            print(f"   🛑 Quota Limit Hit (429). Pausing for 60s...")
            time.sleep(60)
        else:
            print(f"   ❌ Cycle Error: {e}")
            time.sleep(10)

print("\n🏁 Beast Bot finished.")
 