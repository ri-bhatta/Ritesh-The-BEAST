# upload code

import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
import json
import time
import re
from datetime import datetime
import pypdf
from youtube_transcript_api import YouTubeTranscriptApi

# --- CONFIGURATION ---
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# --- CONNECT TO DATABASE ---
def get_db():
    try:
        # Tries to load from secrets.toml first (Best for Cloud)
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], SCOPE)
        # Fallback to local file (Best for Laptop)
        else: 
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
        return gspread.authorize(creds)
    except Exception as e:
        return None

# --- SAVE TO GOOGLE SHEETS ---
def save_qs(rows, subject):
    client = get_db()
    if not client:
        st.error("❌ Database Connection Failed. Check credentials.")
        return False
        
    # Map Subjects to Sheet Prefixes
    map_sub = {"IT": "Questions", "Quant": "Quant", "Reasoning": "Reasoning", "English": "Eng", "Finance": "Finance", "Computer": "Comp"}
    prefix = map_sub.get(subject, "Questions")
    
    # Create Dynamic Sheet Name (e.g., Questions_2025_12)
    sh_name = f"{prefix}_{datetime.now().year}_{datetime.now().month:02d}"
    
    try:
        try: 
            sh = client.open(sh_name)
        except: 
            # If sheet doesn't exist, create it and add headers
            sh = client.create(sh_name)
            sh.get_worksheet(0).append_row(["ID","Date","Topic","Question","A","B","C","D","E","Correct","Explanation"])
            
        # Add new rows
        for r in rows: 
            sh.get_worksheet(0).append_row(r)
        return True
    except Exception as e: 
        st.error(f"❌ Save Error: {e}")
        return False

# --- UI LAYOUT ---
st.title("📤 Admin Uploader (Content Generator)")
st.caption("Feed the Beast with YouTube Videos or PDF Books")

c1, c2 = st.columns(2)
with c1:
    sub = st.selectbox("Select Subject", ["IT", "Quant", "Reasoning", "English", "Finance", "Computer"])
with c2:
    src = st.radio("Select Source", ["YouTube", "PDF"])

# --- YOUTUBE LOGIC ---
if src == "YouTube":
    url = st.text_input("Paste YouTube URL")
    if st.button("🚀 Generate from Video") and url:
        try:
            with st.spinner("Extracting Transcript..."):
                vid = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url).group(1)
                txt = " ".join([i['text'] for i in YouTubeTranscriptApi.get_transcript(vid)])
            
            with st.spinner("AI Generating Questions..."):
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # Prompt to ensure we get the 'Topic' for Micro-Analysis
                prompt = f"""
                Analyze this text and create 10 High-Quality MCQs for IBPS SO {sub}.
                Format as a JSON Array: [{{'question':'...','A':'...','B':'...','C':'...','D':'...','E':'...','correct':'A','explanation':'...','Topic':'...'}}]
                Ensure 'Topic' is specific (e.g. 'Data Structures' not just 'IT').
                """
                resp = model.generate_content([txt, prompt])
                
                # Clean and Parse JSON
                data = json.loads(resp.text.replace("```json","").replace("```","").strip())
                
                # Format for Sheets
                rows = [[f"AI-{int(time.time())}", str(datetime.now()), i.get('Topic', sub), i['question'], i['A'], i['B'], i['C'], i['D'], i.get('E',''), i['correct'], i['explanation']] for i in data]
                
                if save_qs(rows, sub): 
                    st.success(f"✅ Successfully saved {len(rows)} questions to DB!")
                    st.balloons()
                    
        except Exception as e: 
            st.error(f"❌ Error: {e}")

# --- PDF LOGIC ---
elif src == "PDF":
    up = st.file_uploader("Upload PDF File", type="pdf")
    if st.button("🚀 Generate from PDF") and up:
        try:
            with st.spinner("Reading PDF..."):
                txt = "".join([p.extract_text() for p in pypdf.PdfReader(up).pages])
            
            with st.spinner("AI Scanning & Generating..."):
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                prompt = f"""
                Analyze this PDF content and create 10 High-Quality MCQs for IBPS SO {sub}.
                Format as a JSON Array: [{{'question':'...','A':'...','B':'...','C':'...','D':'...','E':'...','correct':'A','explanation':'...','Topic':'...'}}]
                """
                resp = model.generate_content([txt, prompt])
                
                data = json.loads(resp.text.replace("```json","").replace("```","").strip())
                rows = [[f"AI-{int(time.time())}", str(datetime.now()), i.get('Topic', sub), i['question'], i['A'], i['B'], i['C'], i['D'], i.get('E',''), i['correct'], i['explanation']] for i in data]
                
                if save_qs(rows, sub): 
                    st.success(f"✅ Successfully saved {len(rows)} questions to DB!")
                    st.balloons()
                    
        except Exception as e: 
            st.error(f"❌ Error: {e}")

