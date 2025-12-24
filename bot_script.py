import os
import json
import random
import time
from datetime import datetime
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. SETUP & AUTH ---
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GCP_CREDS_JSON = os.environ.get('GCP_CREDENTIALS')

if not GEMINI_KEY: 
    print("❌ Error: GEMINI_API_KEY not found.")
    exit(1)
if not GCP_CREDS_JSON: 
    print("❌ Error: GCP_CREDENTIALS not found.")
    exit(1)

# --- 2. CONFIGURE AI ---
genai.configure(api_key=GEMINI_KEY)

# --- CHANGE: USE THE STABLE MODEL ---
MODEL_NAME = 'gemini-pro' 

# --- 3. PICK SUBJECT ---
subjects = ['IT', 'Quant', 'Reasoning', 'English', 'Computer']
sub = random.choice(subjects)
print(f'🦁 Beast Bot waking up... Target Subject: {sub}')

# --- 4. GENERATE CONTENT ---
try:
    model = genai.GenerativeModel(MODEL_NAME)
    prompt = f"""
    Generate 5 High-Quality MCQs for IBPS SO Exam on the topic: {sub}.
    Strictly output a JSON Array.
    Keys: Question, A, B, C, D, Correct, Explanation, Topic.
    Do not use Markdown formatting. Just raw JSON.
    """
    
    resp = model.generate_content(prompt)
    
    # Clean the response
    clean_text = resp.text.replace("```json", "").replace("```", "").strip()
    
    # Parse JSON
    data = json.loads(clean_text)
    print(f"✅ AI Generation Successful! Created {len(data)} questions using {MODEL_NAME}.")

except Exception as e:
    print(f"❌ AI Brain Error: {e}")
    exit(1)

# --- 5. SAVE TO DATABASE ---
try:
    GCP_CREDS_DICT = json.loads(GCP_CREDS_JSON)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(GCP_CREDS_DICT, scope)
    client = gspread.authorize(creds)

    # Calculate Sheet Name
    map_sub = {'IT': 'Questions', 'Quant': 'Quant', 'Reasoning': 'Reasoning', 'English': 'Eng', 'Computer': 'Comp'}
    prefix = map_sub.get(sub, 'Questions')
    now = datetime.now()
    sheet_name = f'{prefix}_{now.year}_{now.month:02d}'

    # Open or Create Sheet
    try:
        sh = client.open(sheet_name)
    except:
        print(f"ℹ️ Sheet {sheet_name} not found. Creating it...")
        sh = client.create(sheet_name)
        sh.get_worksheet(0).append_row(['ID','Date','Topic','Question','A','B','C','D','E','Correct','Explanation'])
        sh.share(GCP_CREDS_DICT['client_email'], perm_type='user', role='writer')

    ws = sh.get_worksheet(0)
    
    # Append Rows
    rows = []
    for q in data:
        rows.append([
            f'AUTO-{int(time.time())}', 
            str(now), 
            q.get('Topic', sub), 
            q.get('Question'), 
            q.get('A'), q.get('B'), q.get('C'), q.get('D'), '', 
            q.get('Correct'), 
            q.get('Explanation')
        ])
    
    ws.append_rows(rows)
    print(f"✅ Success! Saved to {sheet_name}.")

except Exception as e:
    print(f"❌ Database Error: {e}")
    exit(1)
