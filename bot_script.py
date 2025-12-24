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

# --- 1. SETUP ---
print("🚀 Starting Beast Bot (DEBUG MODE)...")
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GCP_CREDS_JSON = os.environ.get('GCP_CREDENTIALS')

if not GEMINI_KEY: print("❌ Error: GEMINI_API_KEY missing"); exit(1)
if not GCP_CREDS_JSON: print("❌ Error: GCP_CREDENTIALS missing"); exit(1)

genai.configure(api_key=GEMINI_KEY)

# --- 2. ROBUST MODEL SELECTION ---
# We force 1.5-flash because it is the most stable for JSON
active_model_name = "models/gemini-1.5-flash"
print(f"🤖 Target Model: {active_model_name}")

# --- 3. GENERATION WITH DEBUGGING ---
sub = random.choice(['IT', 'Quant', 'Reasoning', 'English', 'Computer'])
print(f'🦁 Beast Bot Target: {sub}')

safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

data = [] # Store questions here

try:
    print("⏳ Asking Gemini...")
    model = genai.GenerativeModel(active_model_name)
    prompt = f"""
    Generate 5 MCQs for IBPS SO exam on subject: {sub}.
    STRICT JSON ONLY. No markdown. No "Here is the JSON".
    Format: [{{"Question": "...", "A": "...", "B": "...", "C": "...", "D": "...", "Correct": "A", "Explanation": "...", "Topic": "..."}}]
    """
    
    # 30s Timeout
    resp = model.generate_content(
        prompt, 
        safety_settings=safety_settings,
        request_options={"timeout": 30}
    )
    
    # --- CRITICAL DEBUG STEP ---
    # This prints EXACTLY what the AI sent back. Look at this in your logs!
    print(f"\n📝 RAW AI RESPONSE START:\n{resp.text}\n📝 RAW AI RESPONSE END\n")
    
    # Clean and Parse
    raw_text = resp.text
    match = re.search(r'\[.*\]', raw_text, re.DOTALL)
    
    if match:
        json_str = match.group(0)
        # Fix common JSON breaks
        json_str = re.sub(r'(?<!\\)\n', ' ', json_str)
        try:
            data = json.loads(json_str)
            print(f"🧠 Successfully parsed {len(data)} questions.")
        except:
            print("⚠️ Parsing failed even after finding brackets.")
    else:
        print("⚠️ No JSON brackets [] found in response.")

except Exception as e:
    print(f"❌ AI Generation Error: {e}")

# --- 4. BACKUP PLAN (The Fail-Safe) ---
# If AI failed (data is empty), we create a dummy question so the script DOES NOT CRASH.
if not data:
    print("⚠️ AI Failed to provide valid JSON. Using BACKUP QUESTION to keep pipeline alive.")
    data = [{
        "Question": f"⚠️ AI ERROR on {sub}. This is a test row to prove Database works.",
        "A": "Ignore", "B": "Ignore", "C": "Ignore", "D": "Ignore",
        "Correct": "A", "Explanation": "Check GitHub Logs for 'RAW AI RESPONSE'",
        "Topic": "Debug"
    }]

# --- 5. SAVE TO SHEETS ---
try:
    print("📡 Connecting to Google Sheets...")
    creds_dict = json.loads(GCP_CREDS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)

    map_sub = {'IT': 'Questions', 'Quant': 'Quant', 'Reasoning': 'Reasoning', 'English': 'Eng', 'Computer': 'Comp'}
    prefix = map_sub.get(sub, 'Questions')
    now = datetime.now()
    sheet_name = f'{prefix}_{now.year}_{now.month:02d}'

    try: 
        sh = client.open(sheet_name)
    except: 
        print(f"🆕 Creating Sheet: {sheet_name}")
        sh = client.create(sheet_name)
        sh.share(creds_dict['client_email'], perm_type='user', role='writer')
        sh.get_worksheet(0).append_row(['ID','Date','Topic','Question','A','B','C','D','E','Correct','Explanation'])

    ws = sh.get_worksheet(0)
    rows = [[f'AUTO-{int(time.time())}', str(now), q.get('Topic', sub), q.get('Question'), q.get('A'), q.get('B'), q.get('C'), q.get('D'), '', q.get('Correct'), q.get('Explanation')] for q in data]
    ws.append_rows(rows)
    print(f"✅ SUCCESS! Saved {len(data)} rows to {sheet_name}")

except Exception as e:
    print(f"❌ Database Error: {e}")
    exit(1)
