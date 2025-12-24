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
print("🚀 Starting Beast Bot...")
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GCP_CREDS_JSON = os.environ.get('GCP_CREDENTIALS')

if not GEMINI_KEY: print("❌ Error: GEMINI_API_KEY missing"); exit(1)
if not GCP_CREDS_JSON: print("❌ Error: GCP_CREDENTIALS missing"); exit(1)

genai.configure(api_key=GEMINI_KEY)

# --- 2. SELECT MODEL ---
active_model_name = "models/gemini-2.0-flash-exp"
print(f"🤖 Target Model: {active_model_name}")

# --- 3. GENERATE CONTENT ---
sub = random.choice(['IT', 'Quant', 'Reasoning', 'English', 'Computer'])
print(f'🦁 Beast Bot Target: {sub}')

safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

try:
    print("⏳ Asking Gemini (Timeout set to 30s)...")
    model = genai.GenerativeModel(active_model_name)
    prompt = f"""
    You are an expert exam setter for IBPS SO.
    Generate 5 High-Level MCQs for the subject: {sub}.
    STRICT FORMATTING RULES:
    1. Output MUST be a raw JSON Array.
    2. Do not use markdown blocks.
    3. Keys: Question, A, B, C, D, Correct, Explanation, Topic.
    4. Ensure all text is single-line strings (no unescaped newlines).
    """
    
    resp = model.generate_content(
        prompt, 
        safety_settings=safety_settings,
        request_options={"timeout": 30}
    )
    
    # --- THE SANITIZER (Fixes Invalid Control Characters) ---
    raw_text = resp.text
    # 1. Extract JSON part
    match = re.search(r'\[.*\]', raw_text, re.DOTALL)
    if match:
        json_str = match.group(0)
        # 2. Fix bad control characters (newlines inside strings)
        # This replaces actual newlines with space, but keeps \n structure
        json_str = re.sub(r'(?<!\\)\n', ' ', json_str)
        # 3. Remove any lingering control characters (0x00-0x1f)
        json_str = re.sub(r'[\x00-\x1f]', '', json_str)
        
        try:
            data = json.loads(json_str)
            print(f"🧠 Generated {len(data)} questions.")
        except json.JSONDecodeError as e:
            # Fallback: Use Python's eval() which is more forgiving for single quotes/bad formatting
            # (Safe here because we trust the source is just our bot text)
            print(f"⚠️ Strict JSON failed ({e}), attempting flexible parse...")
            try:
                data = json.loads(json_str.replace("'", '"')) # Try swapping quotes
            except:
                print(f"❌ Critical JSON Fail. Dump: {json_str[:100]}...")
                exit(1)
    else:
        print("⚠️ No JSON brackets found.")
        exit(1)

except Exception as e:
    print(f"❌ AI Brain Fail: {e}")
    exit(1)

# --- 4. SAVE TO SHEETS ---
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
