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

# --- 2. SMART MODEL SELECTOR ---
def get_working_model():
    print("🔎 Scanning for available models...")
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Prefer Flash 1.5 (Most reliable free tier)
        for m in models:
            if 'flash' in m and '1.5' in m: return m
        return models[0] if models else "models/gemini-1.5-flash"
    except:
        return "models/gemini-1.5-flash"

active_model_name = get_working_model()
print(f"🤖 Selected Model: {active_model_name}")

# --- 3. GENERATION FUNCTION (With Self-Healing) ---
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

def generate_questions():
    # List of subjects. We try 'Reasoning' first, but if it fails, we swap.
    subjects = ['Reasoning', 'IT', 'Computer', 'English', 'Quant']
    
    for attempt in range(3):
        sub = random.choice(subjects)
        print(f"🦁 Attempt {attempt+1}: Targeting {sub}...")
        
        try:
            model = genai.GenerativeModel(active_model_name)
            prompt = f"""
            Generate 5 MCQs for IBPS SO exam on subject: {sub}.
            Return ONLY a raw JSON Array. Keys: Question, A, B, C, D, Correct, Explanation, Topic.
            No markdown. No extra text.
            """
            
            resp = model.generate_content(prompt, safety_settings=safety_settings)
            
            # CHECK: Did we get blocked?
            if not resp.parts:
                print(f"⚠️ Blocked/Empty response for {sub}. Retrying...")
                print(f"   Reason: {resp.prompt_feedback}")
                time.sleep(2)
                continue # Try next loop
                
            text = resp.text
            
            # CLEAN: Find the JSON brackets
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if not match:
                print(f"⚠️ No JSON found in response for {sub}.")
                continue
                
            json_str = match.group(0)
            # Remove bad characters
            json_str = re.sub(r'(?<!\\)\n', ' ', json_str) # remove newlines
            
            data = json.loads(json_str)
            return sub, data # SUCCESS! Return the subject and data
            
        except Exception as e:
            print(f"⚠️ Error generating {sub}: {e}")
            time.sleep(2)
    
    print("❌ All 3 attempts failed.")
    exit(1)

# Run the Generator
target_subject, data = generate_questions()
print(f"🧠 Successfully generated {len(data)} questions for {target_subject}")

# --- 4. SAVE TO SHEETS ---
try:
    print("📡 Connecting to Google Sheets...")
    creds_dict = json.loads(GCP_CREDS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)

    map_sub = {'IT': 'Questions', 'Quant': 'Quant', 'Reasoning': 'Reasoning', 'English': 'Eng', 'Computer': 'Comp'}
    prefix = map_sub.get(target_subject, 'Questions')
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
    rows = [[f'AUTO-{int(time.time())}', str(now), q.get('Topic', target_subject), q.get('Question'), q.get('A'), q.get('B'), q.get('C'), q.get('D'), '', q.get('Correct'), q.get('Explanation')] for q in data]
    ws.append_rows(rows)
    print(f"✅ SUCCESS! Saved to {sheet_name}")

except Exception as e:
    print(f"❌ Database Error: {e}")
    exit(1)
