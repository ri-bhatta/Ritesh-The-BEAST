import os
import json
import random
import time
import re
from datetime import datetime
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. SETUP ---
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GCP_CREDS_JSON = os.environ.get('GCP_CREDENTIALS')

if not GEMINI_KEY: print("❌ Error: GEMINI_API_KEY missing"); exit(1)
if not GCP_CREDS_JSON: print("❌ Error: GCP_CREDENTIALS missing"); exit(1)

genai.configure(api_key=GEMINI_KEY)

# --- 2. FIND WORKING MODEL ---
print("🔎 Scanning for available models...")
active_model_name = None
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            active_model_name = m.name
            print(f"✅ Found working model: {active_model_name}")
            break
except Exception as e:
    print(f"❌ Error listing models: {e}")
    exit(1)

if not active_model_name:
    print("❌ Critical: No available models found.")
    exit(1)

# --- 3. GENERATE CONTENT ---
sub = random.choice(['IT', 'Quant', 'Reasoning', 'English', 'Computer'])
print(f'🦁 Beast Bot Target: {sub}')

# SAFETY SETTINGS: Turn off the filters that block content randomly
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
    2. Do not include markdown formatting (like ```json).
    3. Keys: Question, A, B, C, D, Correct, Explanation, Topic.
    
    Example:
    [
        {{"Question": "What is 2+2?", "A": "1", "B": "2", "C": "4", "D": "5", "Correct": "C", "Explanation": "Math", "Topic": "Algebra"}}
    ]
    """
    
    # Pass safety settings to prevent empty responses
    resp = model.generate_content(prompt, safety_settings=safety_settings)
    
    # --- ROBUST CLEANING (The Fix) ---
    raw_text = resp.text
    # Use Regex to find the JSON array [...] inside the text
    match = re.search(r'\[.*\]', raw_text, re.DOTALL)
    
    if match:
        clean_json = match.group(0)
        data = json.loads(clean_json)
    else:
        print(f"⚠️ Debug Raw Text: {raw_text}")
        raise ValueError("Could not find JSON brackets in response.")

except Exception as e:
    print(f"❌ Generation Failed: {e}")
    # Print the full error to help debug
    if 'resp' in locals():
        print(f"Dump: {resp.prompt_feedback}")
    exit(1)

# --- 4. SAVE TO SHEETS ---
try:
    GCP_CREDS_DICT = json.loads(GCP_CREDS_JSON)
    scope = ['[https://spreadsheets.google.com/feeds](https://spreadsheets.google.com/feeds)', '[https://www.googleapis.com/auth/drive](https://www.googleapis.com/auth/drive)']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(GCP_CREDS_DICT, scope)
    client = gspread.authorize(creds)

    map_sub = {'IT': 'Questions', 'Quant': 'Quant', 'Reasoning': 'Reasoning', 'English': 'Eng', 'Computer': 'Comp'}
    prefix = map_sub.get(sub, 'Questions')
    now = datetime.now()
    sheet_name = f'{prefix}_{now.year}_{now.month:02d}'

    try: sh = client.open(sheet_name)
    except: 
        sh = client.create(sheet_name)
        sh.get_worksheet(0).append_row(['ID','Date','Topic','Question','A','B','C','D','E','Correct','Explanation'])
        sh.share(GCP_CREDS_DICT['client_email'], perm_type='user', role='writer')

    ws = sh.get_worksheet(0)
    rows = [[f'AUTO-{int(time.time())}', str(now), q.get('Topic', sub), q.get('Question'), q.get('A'), q.get('B'), q.get('C'), q.get('D'), '', q.get('Correct'), q.get('Explanation')] for q in data]
    ws.append_rows(rows)
    print(f"✅ Success! Saved {len(data)} questions to {sheet_name}")

except Exception as e:
    print(f"❌ Database Error: {e}")
    exit(1)
