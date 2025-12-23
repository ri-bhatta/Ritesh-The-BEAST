# app code

import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
from twilio.rest import Client
import random
import time
import json
from datetime import datetime
import altair as alt

# --- CONFIGURATION ---
START_YEAR = 2025
START_MONTH = 12 
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# --- SECURITY: DUAL LOGIN SYSTEM (GUEST + ADMIN) ---
def send_sms_otp(otp_code):
    """Sends OTP via Twilio to the Admin."""
    try:
        client = Client(st.secrets["TWILIO_ACCOUNT_SID"], st.secrets["TWILIO_AUTH_TOKEN"])
        message = client.messages.create(
            body=f"🦁 IBPS Admin Code: {otp_code}",
            from_=st.secrets["TWILIO_PHONE_NUMBER"],
            to=st.secrets["ADMIN_MOBILE_NUMBER"]
        )
        return True
    except Exception as e:
        st.error(f"❌ SMS Failed: {e}")
        return False

def check_login_system():
    """Manages the Login Screen."""
    if st.session_state.get('logged_in', False): 
        return True

    st.title("🦁 IBPS Beast Mode")
    
    t1, t2 = st.tabs(["👥 Guest / Student", "🔑 Admin Owner"])
    
    # -- GUEST LOGIN --
    with t1:
        st.write("Enter Invite Code to access study material.")
        guest_code = st.text_input("Invite Code", type="password", key="g_pass")
        if st.button("🚀 Enter Beast Mode"):
            if guest_code == st.secrets["GUEST_INVITE_CODE"]:
                st.session_state.logged_in = True
                st.session_state.user_role = "GUEST"
                st.success("✅ Welcome, Aspirant!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Invalid Invite Code.")

    # -- ADMIN LOGIN --
    with t2:
        st.write(f"Secure Access for: **{st.secrets['ADMIN_MOBILE_NUMBER'][-4:]}**")
        
        if 'otp_code' not in st.session_state: st.session_state.otp_code = None
        if 'otp_sent' not in st.session_state: st.session_state.otp_sent = False

        if not st.session_state.otp_sent:
            if st.button("📲 Send Admin OTP"):
                code = str(random.randint(100000, 999999))
                st.session_state.otp_code = code
                with st.spinner("Sending SMS..."):
                    if send_sms_otp(code): 
                        st.session_state.otp_sent = True
                        st.success("✅ SMS Sent!")
                        st.rerun()
        else:
            user_otp = st.text_input("Enter 6-Digit OTP", max_chars=6)
            if st.button("Verify Admin"):
                if user_otp == st.session_state.otp_code:
                    st.session_state.logged_in = True
                    st.session_state.user_role = "ADMIN"
                    st.success("🔓 Admin Access Granted")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Wrong OTP")
    return False

# --- BACKEND CONNECTIONS ---
@st.cache_resource
def get_db_connection():
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], SCOPE)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
        return gspread.authorize(creds)
    except Exception as e: 
        st.error(f"DB Connection Error: {e}")
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_data_monthly(prefix):
    """Fetches questions from all monthly sheets (e.g. Questions_2025_12)."""
    client = get_db_connection()
    if not client: return []
    
    all_data = []
    now = datetime.now()
    
    # Loop from start date to today to find all question sheets
    for year in range(START_YEAR, now.year + 1):
        start_m = START_MONTH if year == START_YEAR else 1
        end_m = now.month if year == now.year else 12
        
        for month in range(start_m, end_m + 1):
            sheet_name = f"{prefix}_{year}_{month:02d}"
            try:
                sheet = client.open(sheet_name)
                # Get all records ensures we get column headers as keys
                data = sheet.get_worksheet(0).get_all_records()
                if data: 
                    all_data.extend(data)
            except: 
                pass # Sheet doesn't exist yet, skip
                
    return all_data

def save_result(score, total, log, exam_type):
    """Saves test results to the Master Sheet."""
    client = get_db_connection()
    if client:
        try:
            # Check if Master Sheet exists, if not create it
            try:
                sh = client.open("Exam_Results_Master")
            except:
                sh = client.create("Exam_Results_Master")
                sh.get_worksheet(0).append_row(["TestID", "Date", "Score", "Total", "Log"])
            
            # Save the row
            sh.get_worksheet(0).append_row([
                f"{exam_type}-{int(time.time())}", 
                str(datetime.now()), 
                score, 
                total, 
                json.dumps(log) # Save the full log for AI analysis later
            ])
            return True
        except Exception as e:
            st.error(f"Save Failed: {e}")
            return False
    return False

def fetch_past_results():
    client = get_db_connection()
    try: 
        return pd.DataFrame(client.open("Exam_Results_Master").get_worksheet(0).get_all_records())
    except: 
        return pd.DataFrame()

# --- AI DOCTOR (REMEDIATION ENGINE) ---
def generate_remedial_content(weak_topic):
    """Uses Gemini to create custom notes and a test for a weak topic."""
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # 1. Generate Notes
    prompt_notes = f"""
    The student is weak in '{weak_topic}' for IBPS SO IT Officer Exam.
    Explain this concept simply in bullet points. 
    Give 3 'Golden Rules' to remember to solve questions on this topic.
    """
    notes_resp = model.generate_content(prompt_notes)
    
    # 2. Generate Validation Test
    prompt_quiz = f"""
    Create 5 High-Level MCQs strictly on '{weak_topic}' to test understanding.
    Format as JSON Array: [{{'question':'...','A':'...','B':'...','C':'...','D':'...','correct':'A','explanation':'...'}}]
    """
    quiz_resp = model.generate_content(prompt_quiz)
    
    # Parse JSON
    try:
        quiz_data = json.loads(quiz_resp.text.replace("```json","").replace("```","").strip())
    except:
        quiz_data = [] # Fallback if AI fails JSON formatting
        
    return notes_resp.text, quiz_data

# --- UI: SUBJECT PAGE ---
def render_subject_page(title, prefix, timer_mins, key_p):
    st.header(title)
    t1, t2 = st.tabs(["📖 Practice Mode", "⏱️ Mock Test"])
    
    # PRACTICE TAB
    with t1:
        if f"{key_p}_prac" not in st.session_state: st.session_state[f"{key_p}_prac"] = False
        
        if not st.session_state[f"{key_p}_prac"]:
            qs = fetch_data_monthly(prefix)
            st.caption(f"Question Bank Size: {len(qs)}")
            if st.button("Start Practice", key=f"{key_p}_b"): 
                if qs: 
                    st.session_state[f"{key_p}_q"] = random.sample(qs, len(qs))
                    st.session_state[f"{key_p}_prac"] = True
                    st.session_state[f"{key_p}_i"] = 0
                    st.rerun()
                else:
                    st.warning("No questions found. Use the Admin Uploader first!")
        else:
            # Display Question
            idx = st.session_state[f"{key_p}_i"]
            if idx < len(st.session_state[f"{key_p}_q"]):
                q = st.session_state[f"{key_p}_q"][idx]
                
                # Handle case sensitivity in keys (Question vs question)
                q_text = q.get('Question') or q.get('question')
                
                st.markdown(f"**Q{idx+1}: {q_text}**")
                opts = [f"A) {q['A']}", f"B) {q['B']}", f"C) {q['C']}", f"D) {q['D']}"]
                if q.get('E'): opts.append(f"E) {q['E']}")
                
                ch = st.radio("Select Option:", opts, key=f"{key_p}_{idx}")
                
                if st.button("Check Answer", key=f"{key_p}_c_{idx}"):
                    correct_ans = q.get('Correct') or q.get('correct')
                    if ch.split(")")[0] == correct_ans: 
                        st.success("✅ Correct!")
                    else: 
                        st.error(f"❌ Wrong! Correct Answer: {correct_ans}")
                    
                    st.info(f"💡 Explanation: {q.get('Explanation') or q.get('explanation')}")
                
                if st.button("Next Question"): 
                    st.session_state[f"{key_p}_i"] += 1
                    st.rerun()
            else:
                st.success("Practice Session Complete!")
                if st.button("Reset"):
                    st.session_state[f"{key_p}_prac"] = False
                    st.rerun()
            
    # TEST TAB
    with t2:
        if st.button("Start Timed Mock", key=f"{key_p}_m"):
             qs = fetch_data_monthly(prefix)
             if qs: 
                 st.session_state[f"{key_p}_mq"] = random.sample(qs, min(20, len(qs)))
                 st.session_state[f"{key_p}_ma"] = True
                 st.rerun()
                 
        if st.session_state.get(f"{key_p}_ma"):
            st.caption(f"⏱️ You have {timer_mins} minutes.")
            with st.form(f"{key_p}_f"):
                ans = {}
                for i, q in enumerate(st.session_state[f"{key_p}_mq"]):
                    q_text = q.get('Question') or q.get('question')
                    st.write(f"**{i+1}. {q_text}**")
                    opts = [f"A) {q['A']}", f"B) {q['B']}", f"C) {q['C']}", f"D) {q['D']}"]
                    if q.get('E'): opts.append(f"E) {q['E']}")
                    ans[i] = st.radio("Select", opts, key=f"mq_{key_p}_{i}")
                
                if st.form_submit_button("Submit Test"):
                    score = 0
                    log = []
                    for i, q in enumerate(st.session_state[f"{key_p}_mq"]):
                        correct_ans = q.get('Correct') or q.get('correct')
                        r = (ans[i].split(")")[0] == correct_ans)
                        if r: score += 1
                        
                        # LOGGING FOR THE DOCTOR
                        # We save the 'Topic' so the AI knows where you are weak
                        topic = q.get('Topic') or q.get('topic') or prefix # Fallback to subject name
                        log.append({
                            "q": q_text, 
                            "is_right": r, 
                            "topic": topic
                        })
                        
                    save_result(score, len(ans), log, prefix.upper())
                    st.balloons()
                    st.success(f"🏆 Score: {score} / {len(ans)}")
                    st.session_state[f"{key_p}_ma"] = False

# --- UI: THE DOCTOR (ANALYSIS) ---
def render_analysis_page():
    st.title("🩺 The Doctor (Micro-Analysis)")
    st.caption("AI-Powered Performance Diagnosis")
    
    df = fetch_past_results()
    if df.empty: 
        st.info("ℹ️ No medical history found. Take a Mock Test first!")
        return

    # Extract all logs from all tests
    all_attempts = []
    for _, row in df.iterrows():
        try:
            logs = json.loads(row['Log'])
            for entry in logs: all_attempts.append(entry)
        except: pass
    
    if not all_attempts: 
        st.warning("No detailed logs found.")
        return
        
    logs_df = pd.DataFrame(all_attempts)
    
    # Calculate Accuracy per Topic
    if 'topic' in logs_df.columns:
        # Group by topic and count correct answers
        topic_stats = logs_df.groupby('topic')['is_right'].agg(['count', 'mean']).reset_index()
        topic_stats['accuracy'] = (topic_stats['mean'] * 100).round(1)
        topic_stats = topic_stats.sort_values(by='accuracy') # Lowest accuracy first
        
        # Display Chart
        st.subheader("📊 Your Performance DNA")
        
        c = alt.Chart(topic_stats).mark_bar().encode(
            x=alt.X('accuracy', title='Accuracy %'),
            y=alt.Y('topic', sort='x', title='Topic'),
            color=alt.condition(
                alt.datum.accuracy < 50,
                alt.value('#ff4b4b'), # Red for weak
                alt.value('#09ab3b')  # Green for strong
            ),
            tooltip=['topic', 'accuracy', 'count']
        )
        st.altair_chart(c, use_container_width=True)
        
        # IDENTIFY WEAKNESS
        weakest = topic_stats.iloc[0]
        st.error(f"⚠️ Critical Weakness Detected: **{weakest['topic']}** (Accuracy: {weakest['accuracy']}%)")
        
        st.write("The Doctor recommends immediate treatment.")
        if st.button(f"💊 Fix '{weakest['topic']}' Now"):
            with st.spinner("💊 Preparing Remedial Dose (Generating Notes & Test)..."):
                notes, quiz = generate_remedial_content(weakest['topic'])
                st.session_state['remedial_notes'] = notes
                st.session_state['remedial_quiz'] = quiz
                st.session_state['remedial_active'] = True
                st.rerun()

    # SHOW REMEDIAL CONTENT
    if st.session_state.get('remedial_active'):
        st.markdown("---")
        st.header(f"💊 Prescription: {weakest['topic']}")
        
        with st.expander("📖 Step 1: Read these Concept Notes", expanded=True):
            st.markdown(st.session_state['remedial_notes'])
        
        st.subheader("🧪 Step 2: Validation Test")
        with st.form("remedial_form"):
            for i, q in enumerate(st.session_state['remedial_quiz']):
                st.write(f"**{i+1}. {q['question']}**")
                st.radio("Opt", [f"A) {q['A']}", f"B) {q['B']}", f"C) {q['C']}", f"D) {q['D']}"], key=f"r_{i}")
            
            if st.form_submit_button("Submit & Verify"):
                st.success("Great job! You have treated this weakness.")
                st.session_state['remedial_active'] = False
                time.sleep(2)
                st.rerun()

# --- MAIN APP LOGIC ---
def main():
    st.set_page_config(page_title="IBPS Beast", layout="wide", page_icon="🦁")
    
    # 1. Security Gate
    if not check_login_system(): 
        st.stop()

    # 2. Sidebar Navigation
    with st.sidebar:
        st.title("🦁 IBPS SO")
        
        if st.session_state.get("user_role") == "ADMIN": 
            st.success("🔑 Admin Mode")
        else: 
            st.info("👤 Guest Mode")
            
        if st.button("🔄 Sync Database"): 
            st.cache_data.clear()
            st.rerun()
            
        st.markdown("---")
        mode = st.radio("Navigate", [
            "🚀 Dashboard", 
            "🩺 The Doctor (Analysis)", 
            "💻 IT Officer", 
            "🧮 Quant", 
            "🧠 Reasoning", 
            "📖 English", 
            "💰 Finance", 
            "🖥️ Computer Basics"
        ])

    # 3. Page Routing
    if mode == "🚀 Dashboard": 
        st.title("🚀 Prep Dashboard")
        df = fetch_past_results()
        if not df.empty:
            c1, c2, c3 = st.columns(3)
            with c1: st.metric("Tests Taken", len(df))
            with c2: st.metric("Avg Score", f"{df['Score'].mean():.1f}")
            with c3: st.metric("Last Active", str(df['Date'].iloc[-1].split()[0]))
            st.markdown("### Recent Activity")
            st.dataframe(df.sort_values(by="Date", ascending=False).head(5))
        else: 
            st.info("Welcome to Beast Mode! Start by taking a mock test.")
            
    elif mode == "🩺 The Doctor (Analysis)": render_analysis_page()
    elif mode == "💻 IT Officer": render_subject_page("💻 IT Professional Knowledge", "Questions", 30, "it")
    elif mode == "🧮 Quant": render_subject_page("🧮 Quantitative Aptitude", "Quant", 30, "qu")
    elif mode == "🧠 Reasoning": render_subject_page("🧠 Logical Reasoning", "Reasoning", 30, "re")
    elif mode == "📖 English": render_subject_page("📖 English Language", "Eng", 20, "en")
    elif mode == "💰 Finance": render_subject_page("💰 Financial Awareness", "Finance", 15, "fi")
    elif mode == "🖥️ Computer Basics": render_subject_page("🖥️ Computer Knowledge", "Comp", 15, "co")

if __name__ == "__main__":
    main()

