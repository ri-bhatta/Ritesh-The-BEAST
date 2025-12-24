import os
import json
import random
import time
import re
from datetime import datetime
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import gspread
from google.oauth2.service_account import Credentials # <--- The Working Library

# --- 1. SETUP ---
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GCP_CREDS_JSON = os.environ.get('GCP_CREDENTIALS')

if not GEMINI_KEY: print("❌ Error: GEMINI_API_KEY missing"); exit(1)
if not GCP_CREDS_JSON: print("❌ Error: GCP_CREDENTIALS missing"); exit(1)

genai.configure(api_key=GEMINI_KEY)

# --- 2. FIND WORKING MODEL ---
# We try to find a valid model, defaulting to the latest flash model
active_model_name = "models/gemini-2.0-flash-exp"
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            if 'flash' in m.name: # Prefer faster models
                active_model_name = m.name
                break
except:
    pass
print(f"🤖 Using Model: {active_model_name}")

# --- 3. GENERATE CONTENT ---
sub = random.choice(['IT', 'Quant', 'Reasoning', 'English', 'Computer'])
print(f'🦁 Beast Bot Target: {sub}')

# SAFETY SETTINGS: This prevents the "Empty Response" error
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

try:
    model = genai.GenerativeModel(active_model_name)
    prompt = f"""
    You are an expert exam setter for IBPS SO.
    Generate 5 High-Level MCQs for the subject: {sub}.
    
    STRICT FORMATTING RULES:
    1. Output MUST be a raw JSON Array.
    2. Do not use markdown blocks (no ```json).
    3. Keys: Question, A, B, C, D, Correct, Explanation, Topic.
    """
    
    # Generate with safety settings
    resp = model.generate_content(prompt, safety_settings=safety_settings)
    
    # --- ROBUST CLEANING (Regex) ---
    # This finds the JSON array even if the bot adds extra text
    match = re.search(r'\[.*\]', resp.text, re.DOTALL)
    
    if match:
        data = json.loads(match.group(0))
    else:
        # Fallback: simple cleanup
        clean_text = resp.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_text)

    print(f"🧠 Generated {len(data)} questions.")

except Exception as e:
    print(f"❌ AI Brain Fail: {e}")
    # If AI fails, we exit so we don't crash the database
    exit(1)

# --- 4. SAVE TO SHEETS (The Code That Worked!) ---
try:
    print("📡 Connecting to Google Sheets...")
    creds_dict = json.loads(GCP_CREDS_JSON)
    
    # Universal Scopes
    scopes = [
        "[https://www.googleapis.com/auth/spreadsheets](https://www.googleapis.com/auth/spreadsheets)",
        "[https://www.googleapis.com/auth/drive](https://www.googleapis.com/auth/drive)"
    ]
    
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
    print(f"✅ SUCCESS! Saved to {sheet_name}")

except Exception as e:
    print(f"❌ Database Error: {e}")
    exit(1)
