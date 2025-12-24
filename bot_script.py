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
TARGET_SHEET = "IBPS_Master_Sheet"  # It will ONLY look for this.
RUNTIME_MINUTES = 5

print(f"🚀 STARTING BEAST BOT (Smart Radar Mode)...")

# --- 1. AUTHENTICATION ---
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GCP_CREDS_JSON = os.environ.get('GCP_CREDENTIALS')

if not GEMINI_KEY: print("❌ Error: GEMINI_API_KEY missing"); exit(1)
if not GCP_CREDS_JSON: print("❌ Error: GCP_CREDENTIALS missing"); exit(1)

genai.configure(api_key=GEMINI_KEY)

# --- 2. CONNECT TO DATABASE (The Critical Step) ---
print("📡 Connecting to Google Sheets...")
creds_dict = json.loads(GCP_CREDS_JSON)
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)

try:
    # TRY TO OPEN THE SHEET
    sh = client.open(TARGET_SHEET)
    print(f"✅ SUCCESS! Connected to '{TARGET_SHEET}'")
    print(f"🔗 Writing data to: {sh.url}")

except gspread.SpreadsheetNotFound:
    # IF FAILED: RUN RADAR SCAN
    print(f"❌ ERROR: Could not find '{TARGET_SHEET}'")
    print("🔎 SCANNING FOR WHAT I CAN SEE...")
    
    all_sheets = client.list_spreadsheet_files()
    if not all_sheets:
        print("   ⚠️ I cannot see ANY files.")
        print(f"   👉 Please share the sheet with: {creds_dict['client_email']}")
    else:
        print("   ⚠️ I see these files (check for typos!):")
        for s in all_sheets:
            print(f"   - '{s['name']}' (ID: {s['id']})")
            
    print("❌ Script stopped because Database is missing.")
    exit(1)

# --- 3. AUTO-DETECT MODEL ---
def get_model():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
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
            time.sleep(15) # Wait 15s
        else:
            print("   ⚠️ No JSON found.")
            time.sleep(5)

    except Exception as e:
        print(f"   ❌ Cycle Error: {e}")
        if "429" in str(e): time.sleep(60)
        else: time.sleep(5)

print("\n🏁 Beast Bot finished.")
