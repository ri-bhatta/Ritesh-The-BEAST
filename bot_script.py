import os
import json
import random
import time
from datetime import datetime
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. SETUP ---
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GCP_CREDS_JSON = os.environ.get('GCP_CREDENTIALS')

if not GEMINI_KEY: print("❌ Error: GEMINI_API_KEY missing"); exit(1)
if not GCP_CREDS_JSON: print("❌ Error: GCP_CREDENTIALS missing"); exit(1)

genai.configure(api_key=GEMINI_KEY)

# --- 2. DIAGNOSTIC CHECK (Run this if models fail) ---
def list_available_models():
    print("🔎 Checking available models for your API Key...")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f" - {m.name}")
    except Exception as e:
        print(f"❌ Could not list models: {e}")

# --- 3. GENERATION LOOP ---
# We try the newest model first, then fall back to older ones
models_to_try = ['gemini-1.5-flash', 'gemini-pro', 'models/gemini-1.5-flash-latest']
data = []
success_model = ""

sub = random.choice(['IT', 'Quant', 'Reasoning', 'English', 'Computer'])
print(f'🦁 Beast Bot Target: {sub}')

for model_name in models_to_try:
    try:
        print(f"👉 Attempting with model: {model_name}")
        model = genai.GenerativeModel(model_name)
        prompt = f"Generate 5 High-Quality MCQs for IBPS SO {sub}. JSON Array: Question, A, B, C, D, Correct, Explanation, Topic. Raw JSON only."
        
        resp = model.generate_content(prompt)
        clean_json = resp.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
        success_model = model_name
        break # It worked! Stop trying.
    except Exception as e:
        print(f"⚠️ Failed with {model_name}: {e}")

if not data:
    print("❌ ALL Models failed.")
    list_available_models() # This will print the valid names in the log
    exit(1)

print(f"✅ Success using {success_model}!")

# --- 4. SAVE TO SHEETS ---
try:
    GCP_CREDS_DICT = json.loads(GCP_CREDS_JSON)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
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
    print(f"✅ Saved to {sheet_name}")

except Exception as e:
    print(f"❌ Database Error: {e}")
    exit(1)
