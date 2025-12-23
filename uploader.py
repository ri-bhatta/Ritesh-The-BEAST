import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
import json
import time
import re
from datetime import datetime
import pypdf

# --- ROBUST IMPORT FOR YOUTUBE ---
try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    st.error("⚠️ Library missing! Run: pip install youtube-transcript-api")
    st.stop()

# --- CONFIGURATION ---
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# --- CONNECT TO DATABASE ---
def get_db():
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], SCOPE)
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
        
    map_sub = {"IT": "Questions", "Quant": "Quant", "Reasoning": "Reasoning", "English": "Eng", "Finance": "Finance", "Computer": "Comp"}
    prefix = map_sub.get(subject, "Questions")
    sh_name = f"{prefix}_{datetime.now().year}_{datetime.now().month:02d}"
    
    try:
        try: sh = client.open(sh_name)
        except: 
            sh = client.create(sh_name)
            sh.get_worksheet(0).append_row(["ID","Date","Topic","Question","A","B","C","D","E","Correct","Explanation"])
        for r in rows: sh.get_worksheet(0).append_row(r)
        return True
    except Exception as e: 
        st.error(f"❌ Save Error: {e}")
        return False

# --- UI LAYOUT ---
st.title("📤 Admin Uploader (Content Generator)")
c1, c2 = st.columns(2)
with c1: sub = st.selectbox("Select Subject", ["IT", "Quant", "Reasoning", "English", "Finance", "Computer"])
with c2: src = st.radio("Select Source", ["YouTube", "PDF"])

# --- YOUTUBE LOGIC ---
if src == "YouTube":
    url = st.text_input("Paste YouTube URL")
    if st.button("🚀 Generate from Video") and url:
        try:
            with st.spinner("Extracting Transcript..."):
                # Regex to find Video ID
                vid_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
                if not vid_match:
                    st.error("Invalid YouTube URL")
                    st.stop()
                vid = vid_match.group(1)
                
                # --- THE FIX IS HERE ---
                # We call the static method directly
                transcript_list = YouTubeTranscriptApi.get_transcript(vid)
                txt = " ".join([i['text'] for i in transcript_list])
            
            with st.spinner("AI Generating Questions..."):
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                model = genai.GenerativeModel('gemini-1.5-flash')
                prompt = f"""
                Analyze this text and create 10 High-Quality MCQs for IBPS SO {sub}.
                Format as a JSON Array: [{{'question':'...','A':'...','B':'...','C':'...','D':'...','E':'...','correct':'A','explanation':'...','Topic':'...'}}]
                """
                resp = model.generate_content([txt, prompt])
                data = json.loads(resp.text.replace("```json","").replace("```","").strip())
                rows = [[f"AI-{int(time.time())}", str(datetime.now()), i.get('Topic', sub), i['question'], i['A'], i['B'], i['C'], i['D'], i.get('E',''), i['correct'], i['explanation']] for i in data]
                
                if save_qs(rows, sub): 
                    st.success(f"✅ Saved {len(rows)} questions!")
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
            with st.spinner("AI Generating..."):
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                model = genai.GenerativeModel('gemini-1.5-flash')
                prompt = f"Create 10 MCQs for {sub} from this text. JSON Array format."
                resp = model.generate_content([txt, prompt])
                data = json.loads(resp.text.replace("```json","").replace("```","").strip())
                rows = [[f"AI-{int(time.time())}", str(datetime.now()), i.get('Topic', sub), i['question'], i['A'], i['B'], i['C'], i['D'], i.get('E',''), i['correct'], i['explanation']] for i in data]
                if save_qs(rows, sub): st.success(f"✅ Saved {len(rows)} questions!")
        except Exception as e: 
            st.error(f"❌ Error: {e}")
