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
# We force a new sheet to avoid "Ghost File" confusion
MASTER_SHEET_NAME = "Beast_Bot_Final"

print(f"🚀 STARTING BEAST BOT (Universal Fix)...")

# --- 1. AUTHENTICATION ---
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GCP_CREDS_JSON = os.environ.get('GCP_CREDENTIALS')

if not GEMINI_KEY: print("❌ Error: GEMINI_API_KEY missing"); exit(1)
if not GCP_CREDS_JSON: print("❌ Error: GCP_CREDENTIALS missing"); exit(1)

genai.configure(api_key=GEMINI_KEY)

# --- 2. INTELLIGENT MODEL SCANNER ---
# This fixes the 404 Error by asking Google: "What models do I have?"
def get_working_model():
    print("🔎 Scanning your API Key for available models...")
    try:
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        print(f"   📋 You have access to: {available_models}")
        
        # Priority: Flash -> Pro -> 1.0 -> Any
        if 'models/gemini-1.5-flash' in available_models: return 'models/gemini-1.5-flash'
        if 'models/gemini-1.5-pro' in available_models: return 'models/gemini-1.5-pro'
        if 'models/gemini-pro' in available_models: return 'models/gemini-pro'
        
        return available_models[0] if available_models else None
    except Exception as e:
        print(f"⚠️ Scan failed: {e}")
        return "models/gemini-pro" # Last resort fallback

MODEL_NAME = get_working_model()
if not MODEL_NAME:
    print("❌ FATAL: Your API Key has NO access to any text generation models.")
    print("👉 ACTION: Go to aistudio.google.com and create a new FREE API Key.")
    exit(1)

print(f"🤖 BOT LOCKED ONTO: {MODEL_NAME}")

# --- 3. CONNECT TO DATABASE ---
try:
    print("📡 Connecting to Google Sheets...")
    creds_dict = json.loads(GCP_CREDS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    try:
        sh = client.open(MASTER_SHEET_NAME)
        print(f"✅ Found existing sheet: {MASTER_SHEET_NAME}")
    except gspread.SpreadsheetNotFound:
        print(f"🆕 Creating NEW sheet: {MASTER_SHEET_NAME}")
        sh = client.create(MASTER_SHEET_NAME)
        sh.share(creds_dict['client_email'], perm_type='user', role='writer')
        sh.get_worksheet(0).append_row(['ID','Date','Subject','Question','A','B','C','D','Correct','Explanation'])

    print("-" * 50)
    print(f"🔗 CLICK THIS LINK TO SEE DATA: {sh.url}")
    print("-" * 50)

except Exception as e:
    print(f"❌ FATAL DATABASE ERROR: {e}")
    exit(1)

# --- 4. GENERATE AND SAVE ---
try:
    print(f"⏳ Asking Gemini...")
    model = genai.GenerativeModel(MODEL_NAME)
    
    sub = random.choice(['IT', 'Computer', 'Reasoning'])
    prompt = f"""
    Generate 1 MCQ for IBPS SO exam on subject: {sub}.
    STRICT JSON. Keys: Question, A, B, C, D, Correct, Explanation.
    """
    
    resp = model.generate_content(prompt)
    
    # Parse
    match = re.search(r'\{.*\}', resp.text, re.DOTALL) # Look for object
    if not match: match = re.search(r'\[.*\]', resp.text, re.DOTALL) # Look for array
    
    if match:
        json_str = match.group(0)
        if json_str.startswith('{'): json_str = f"[{json_str}]"
        data = json.loads(json_str)
        
        # Save
        ws = sh.get_worksheet(0)
        q = data[0]
        now = str(datetime.now())
        
        ws.append_row([
            f'AUTO-{int(time.time())}', 
            now, 
            sub, 
            q.get('Question'), 
            q.get('A'), q.get('B'), q.get('C'), q.get('D'), 
            q.get('Correct'), 
            q.get('Explanation')
        ])
        print(f"✅ SUCCESS! Question saved to {MASTER_SHEET_NAME}")
    else:
        print("⚠️ AI replied but no JSON found.")

except Exception as e:
    print(f"❌ AI ERROR: {e}")
