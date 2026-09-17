import os
import json
import base64
import smtplib
import urllib.request
import urllib.parse
import streamlit as st
import streamlit.components.v1 as components
import sqlite3
import uuid
import re
from datetime import datetime, timedelta
from email.message import EmailMessage
import pandas as pd
import plotly.express as px

DB_NAME = "justiceconnect.db"

st.set_page_config(
    page_title="JusticeConnect",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_setting(name, default=None):
    value = os.getenv(name)
    if value is not None and str(value).strip() != "":
        return value

    try:
        secrets = st.secrets
        if name in secrets and str(secrets[name]).strip() != "":
            return secrets[name]
        app_secrets = secrets.get("app", {})
        if name in app_secrets and str(app_secrets[name]).strip() != "":
            return app_secrets[name]
    except Exception:
        pass

    return default


DEPARTMENT_EMAILS = {
    "Municipal Administration": get_setting("DEPT_MUNICIPAL_EMAIL", "municipal@justiceconnect.gov"),
    "Police Department": get_setting("DEPT_POLICE_EMAIL", "police@justiceconnect.gov"),
    "Electricity Department": get_setting("DEPT_ELECTRICITY_EMAIL", "electricity@justiceconnect.gov"),
    "Water Supply Department": get_setting("DEPT_WATER_EMAIL", "watersupply@justiceconnect.gov"),
    "Transport Department": get_setting("DEPT_TRANSPORT_EMAIL", "transport@justiceconnect.gov"),
    "Revenue Department": get_setting("DEPT_REVENUE_EMAIL", "revenue@justiceconnect.gov"),
    "Education Department": get_setting("DEPT_EDUCATION_EMAIL", "education@justiceconnect.gov"),
    "Health Department": get_setting("DEPT_HEALTH_EMAIL", "health@justiceconnect.gov"),
    "Other": get_setting("DEPT_OTHER_EMAIL", "support@justiceconnect.gov")
}


def send_sms_to_mobile(mobile, message):
    account_sid = get_setting("TWILIO_ACCOUNT_SID")
    auth_token = get_setting("TWILIO_AUTH_TOKEN")
    from_number = get_setting("TWILIO_FROM_NUMBER")

    if not account_sid or not auth_token or not from_number or not mobile:
        return False

    try:
        data = urllib.parse.urlencode({
            "To": mobile,
            "From": from_number,
            "Body": message
        }).encode()
        auth = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
        request = urllib.request.Request(
            f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
            data=data,
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
        return True
    except Exception:
        return False


def send_complaint_notification(complaint_id, citizen_name, citizen_email, mobile, department, complaint_summary):
    smtp_host = get_setting("SMTP_HOST")
    smtp_port = int(get_setting("SMTP_PORT", "587"))
    smtp_username = get_setting("SMTP_USERNAME")
    smtp_password = get_setting("SMTP_PASSWORD")
    from_email = get_setting("SMTP_FROM_EMAIL") or smtp_username or "noreply@justiceconnect.gov"

    email_sent = False
    sms_sent = False

    if smtp_host and smtp_username and smtp_password:
        member_email = get_setting(
            f"MEMBER_EMAIL_{re.sub(r'[^A-Za-z0-9]+', '_', department).strip('_').upper()}"
        ) or get_setting("MEMBER_EMAIL")
        receiver_email = member_email or DEPARTMENT_EMAILS.get(
            department,
            get_setting("DEFAULT_DEPARTMENT_EMAIL", "support@justiceconnect.gov")
        )
        recipients = []

        if citizen_email:
            recipients.append(citizen_email)
        if receiver_email and receiver_email not in recipients:
            recipients.append(receiver_email)

        if recipients:
            msg = EmailMessage()
            msg["Subject"] = f"Complaint Submitted - {complaint_id}"
            msg["From"] = from_email
            msg["To"] = ", ".join(recipients)
            msg.set_content(
                f"Dear {citizen_name},\n\n"
                f"Your complaint has been submitted successfully.\n"
                f"Complaint ID: {complaint_id}\n"
                f"Department: {department}\n"
                f"Summary: {complaint_summary}\n\n"
                f"The assigned member or department has also been notified at {receiver_email}.\n\n"
                f"Thank you for using JusticeConnect."
            )

            try:
                if smtp_port == 465:
                    server = smtplib.SMTP_SSL(smtp_host, smtp_port)
                else:
                    server = smtplib.SMTP(smtp_host, smtp_port)
                    server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
                server.quit()
                email_sent = True
            except Exception:
                email_sent = False

    if mobile:
        sms_message = (
            f"Your complaint {complaint_id} has been submitted successfully. "
            f"Department: {department}."
        )
        sms_sent = send_sms_to_mobile(mobile, sms_message)

    return email_sent or sms_sent


def cleanup_expired_complaints(days=30):
    conn = get_db()
    cur = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    expired = cur.execute(
        "SELECT complaint_id FROM complaints WHERE created_at < ?",
        (cutoff,)
    ).fetchall()

    expired_ids = [row[0] for row in expired]

    if expired_ids:
        placeholders = ", ".join("?" for _ in expired_ids)
        cur.execute(
            f"DELETE FROM status_history WHERE complaint_id IN ({placeholders})",
            tuple(expired_ids)
        )
        cur.execute(
            f"DELETE FROM complaints WHERE complaint_id IN ({placeholders})",
            tuple(expired_ids)
        )

    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            mobile TEXT NOT NULL,
            email TEXT,
            category TEXT NOT NULL,
            department TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'Submitted',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            attachment BLOB,
            attachment_name TEXT,
            attachment_type TEXT
        )
    """)

    columns = [
        ("attachment", "BLOB"),
        ("attachment_name", "TEXT"),
        ("attachment_type", "TEXT")
    ]

    existing_columns = [
        row["name"]
        for row in cur.execute("PRAGMA table_info(complaints)").fetchall()
    ]

    for column_name, column_type in columns:
        if column_name not in existing_columns:
            cur.execute(
                f"ALTER TABLE complaints ADD COLUMN {column_name} {column_type}"
            )

    cur.execute("""
        CREATE TABLE IF NOT EXISTS status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT NOT NULL,
            status TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    cur.execute(
        "INSERT OR IGNORE INTO admins (username, password) VALUES (?, ?)",
        ("admin", "admin123")
    )

    cur.execute(
        """
        INSERT INTO admins (username, password)
        VALUES (?, ?)
        ON CONFLICT(username) DO UPDATE SET password = excluded.password
        """,
        ("Hemu", "hemu@5622s")
    )

    cur.execute(
        "INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)",
        ("citizen", "citizen123")
    )

    cur.execute(
        """
        INSERT INTO users (username, password)
        VALUES (?, ?)
        ON CONFLICT(username) DO UPDATE SET password = excluded.password
        """,
        ("user", "user123")
    )

    conn.commit()
    conn.close()

def create_complaint_id():
    return "JC-" + datetime.now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:6].upper()

def add_complaint(
    name,
    mobile,
    email,
    category,
    department,
    location,
    description,
    attachment,
    attachment_name,
    attachment_type
):
    conn = get_db()

    complaint_id = create_complaint_id()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("""
        INSERT INTO complaints
        (
            complaint_id,
            name,
            mobile,
            email,
            category,
            department,
            location,
            description,
            status,
            created_at,
            updated_at,
            attachment,
            attachment_name,
            attachment_type
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        complaint_id,
        name,
        mobile,
        email,
        category,
        department,
        location,
        description,
        "Submitted",
        now,
        now,
        attachment,
        attachment_name,
        attachment_type
    ))

    conn.execute("""
        INSERT INTO status_history
        (complaint_id, status, updated_at)
        VALUES (?, ?, ?)
    """, (
        complaint_id,
        "Submitted",
        now
    ))

    conn.commit()
    conn.close()

    return complaint_id

def get_complaint(complaint_id):
    conn = get_db()

    complaint = conn.execute(
        "SELECT * FROM complaints WHERE complaint_id = ?",
        (complaint_id,)
    ).fetchone()

    conn.close()

    return complaint

def get_status_history(complaint_id):
    conn = get_db()

    rows = conn.execute("""
        SELECT status, updated_at
        FROM status_history
        WHERE complaint_id = ?
        ORDER BY id ASC
    """, (complaint_id,)).fetchall()

    conn.close()

    return rows

def update_status(complaint_id, new_status):
    conn = get_db()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("""
        UPDATE complaints
        SET status = ?, updated_at = ?
        WHERE complaint_id = ?
    """, (
        new_status,
        now,
        complaint_id
    ))

    conn.execute("""
        INSERT INTO status_history
        (complaint_id, status, updated_at)
        VALUES (?, ?, ?)
    """, (
        complaint_id,
        new_status,
        now
    ))

    conn.commit()
    conn.close()

def get_all_complaints():
    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM complaints
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return rows

def get_complaints_by_mobile(mobile):
    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM complaints
        WHERE mobile = ?
        ORDER BY id DESC
    """, (mobile,)).fetchall()

    conn.close()

    return rows

def login_admin(username, password):
    conn = get_db()

    admin = conn.execute("""
        SELECT *
        FROM admins
        WHERE username = ? AND password = ?
    """, (
        username,
        password
    )).fetchone()

    conn.close()

    return admin is not None


def login_user(username, password):
    conn = get_db()

    user = conn.execute("""
        SELECT *
        FROM users
        WHERE username = ? AND password = ?
    """, (
        username,
        password
    )).fetchone()

    conn.close()

    return user is not None

def is_valid_mobile_number(value):
    value = (value or "").strip()
    return bool(re.fullmatch(r"\+91[6-9]\d{9}", value))


def is_valid_gmail(value):
    value = (value or "").strip()
    return bool(re.fullmatch(r"[A-Za-z0-9._%+\-]+@gmail\.com", value))


def voice_assistant_input(default_text=""):
    components.html(
        """
        <style>
            body { font-family: sans-serif; margin: 0; color: #172033; }
            .voice-box { border: 1px solid #dbe4f0; border-radius: 12px; padding: 14px; background: #f8fbff; }
            button { border: 0; border-radius: 8px; padding: 10px 14px; background: #123d8c; color: white; cursor: pointer; font-weight: 700; }
            button.listening { background: #b42318; }
            #transcript { margin: 10px 0 0; min-height: 22px; color: #394760; }
            #answer { margin: 8px 0 0; font-weight: 600; }
        </style>
        <div class="voice-box">
            <button id="listen" type="button">🎙️ Speak to Citizen Assistant</button>
            <div id="transcript">Press the button and ask about complaints, tracking, rights, or services.</div>
            <div id="answer"></div>
        </div>
        <script>
            const listen = document.getElementById("listen");
            const transcript = document.getElementById("transcript");
            const answer = document.getElementById("answer");
            const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            const respond = (question) => {
                const q = question.toLowerCase();
                if (q.includes("complaint") || q.includes("report") || q.includes("problem")) {
                    return "Use Report a Problem to submit your issue. A unique Complaint ID will be generated.";
                }
                if (q.includes("track") || q.includes("status")) {
                    return "Use Track Complaint and enter your Complaint ID to view the latest status.";
                }
                if (q.includes("right")) {
                    return "Open Know Your Rights to explore basic information about citizen rights.";
                }
                if (q.includes("service") || q.includes("certificate")) {
                    return "Open Government Services to find information about available services.";
                }
                return "I can help with complaint reporting, complaint tracking, citizen rights and government services.";
            };
            if (!Recognition) {
                listen.disabled = true;
                listen.textContent = "Voice input is unavailable in this browser";
            } else {
                const recognition = new Recognition();
                recognition.lang = "en-IN";
                recognition.interimResults = false;
                recognition.onstart = () => { listen.classList.add("listening"); listen.textContent = "Listening..."; };
                recognition.onend = () => { listen.classList.remove("listening"); listen.textContent = "🎙️ Speak to Citizen Assistant"; };
                recognition.onerror = () => { answer.textContent = "Microphone access was not available. Use the text box below."; };
                recognition.onresult = (event) => {
                    const text = event.results[0][0].transcript;
                    transcript.textContent = "You said: " + text;
                    answer.textContent = respond(text);
                    window.speechSynthesis.cancel();
                    window.speechSynthesis.speak(new SpeechSynthesisUtterance(respond(text)));
                };
                listen.onclick = () => recognition.start();
            }
        </script>
        """,
        height=205
    )
    value = st.text_input(
        "Ask your question",
        value=default_text,
        key="voice_assistant_input_box"
    )
    col1, col2 = st.columns([3, 1])
    with col2:
        st.caption("🎙️ Voice input works in supported browsers")
    return value


def t(en, te):
    return te if st.session_state.language == "Telugu" else en

init_db()
cleanup_expired_complaints()

if "language" not in st.session_state:
    st.session_state.language = "English"

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

if "user_logged_in" not in st.session_state:
    st.session_state.user_logged_in = False

st.markdown("""
<style>
    .main-title {
        font-size: 42px;
        font-weight: 800;
        margin-bottom: 0;
    }

    .hero {
        background: linear-gradient(135deg, #0b1020 0%, #123d8c 38%, #3b82f6 100%);
        border-radius: 28px;
        padding: 34px 30px;
        margin-bottom: 26px;
        box-shadow: 0 18px 42px rgba(37, 99, 235, 0.25);
        border: 1px solid rgba(255,255,255,0.08);
    }

    .hero-badge {
        display: inline-block;
        background: rgba(255,255,255,0.12);
        border: 1px solid rgba(255,255,255,0.2);
        color: #e0f2fe;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        border-radius: 999px;
        padding: 8px 14px;
        margin-bottom: 14px;
    }

    .hero-title {
        font-size: clamp(2.3rem, 4vw, 4rem);
        line-height: 1.08;
        font-weight: 800;
        color: #ffffff;
        margin: 0 0 14px 0;
    }

    .hero-subtitle {
        color: #dbeafe;
        font-size: 1.08rem;
        max-width: 720px;
        margin-bottom: 18px;
        line-height: 1.7;
    }

    .hero-pill-row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 16px;
    }

    .hero-pill {
        background: rgba(255,255,255,0.12);
        border: 1px solid rgba(255,255,255,0.18);
        color: #f8fafc;
        border-radius: 999px;
        padding: 8px 14px;
        font-size: 0.82rem;
        font-weight: 600;
    }

    .hero-panel {
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.18);
        border-radius: 22px;
        padding: 20px;
        color: white;
    }

    .hero-panel h4 {
        margin: 0 0 14px 0;
        font-size: 1.05rem;
        color: #f8fafc;
    }

    .hero-panel .stat-row {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
        margin-top: 12px;
    }

    .mini-stat {
        background: rgba(15, 23, 42, 0.18);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 14px;
        padding: 12px 10px;
    }

    .mini-stat strong {
        display: block;
        font-size: 1.2rem;
        margin-bottom: 4px;
    }

    .mini-stat span {
        color: #dbeafe;
        font-size: 0.8rem;
    }

    .cta-row {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        margin-top: 18px;
    }

    .cta-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 12px 18px;
        border-radius: 12px;
        font-weight: 700;
        text-decoration: none;
        border: 1px solid transparent;
    }

    .cta-btn.primary {
        background: #f8fafc;
        color: #0f172a;
    }

    .cta-btn.secondary {
        background: transparent;
        color: white;
        border-color: rgba(255,255,255,0.25);
    }

    .section-label {
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #2563eb;
        font-weight: 700;
        margin-bottom: 10px;
    }

    .feature-card {
        background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
        border: 1px solid #dfe8f5;
        border-radius: 20px;
        padding: 22px 20px;
        height: 100%;
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
    }

    .feature-card h3 {
        margin: 12px 0 8px 0;
        color: #0f172a;
        font-size: 1.2rem;
    }

    .feature-card p {
        margin: 0;
        color: #475569;
        line-height: 1.6;
    }

    .info-panel {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 18px;
        padding: 18px 20px;
        margin-top: 8px;
    }

    .info-panel h4 {
        margin: 0 0 10px 0;
        color: #1e3a8a;
    }

    .step-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 18px;
        padding: 18px 16px;
        text-align: center;
        height: 100%;
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
    }

    .step-number {
        width: 42px;
        height: 42px;
        border-radius: 50%;
        background: linear-gradient(135deg, #1d4ed8, #60a5fa);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        margin: 0 auto 12px auto;
    }

    .step-box h4 {
        margin: 0 0 8px 0;
        color: #0f172a;
    }

    .step-box p {
        margin: 0;
        color: #475569;
        line-height: 1.55;
    }

    .subtitle {
        font-size: 18px;
        color: #666;
    }

    .card {
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #ddd;
        background: #ffffff;
        margin-bottom: 15px;
    }

    .status {
        font-size: 18px;
        font-weight: bold;
    }

    .attachment-box {
        padding: 15px;
        border: 1px solid #ddd;
        border-radius: 12px;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

st.sidebar.title("⚖️ JusticeConnect")

st.session_state.language = st.sidebar.selectbox(
    "🌐 Language / భాష",
    ["English", "Telugu"]
)

menu = st.sidebar.radio(
    t("Navigation", "నావిగేషన్"),
    [
        t("Home", "హోమ్"),
        t("User Login", "వినియోగదారు లాగిన్"),
        t("Report a Problem", "సమస్యను నివేదించండి"),
        t("Track Complaint", "ఫిర్యాదును ట్రాక్ చేయండి"),
        t("Know Your Rights", "మీ హక్కులు తెలుసుకోండి"),
        t("Government Services", "ప్రభుత్వ సేవలు"),
        t("Citizen Assistant", "సిటిజన్ అసిస్టెంట్"),
        t("Transparency Dashboard", "పారదర్శకత డ్యాష్‌బోర్డ్"),
        t("Admin Login", "అడ్మిన్ లాగిన్")
    ]
)

if menu == t("Home", "హోమ్"):

    st.markdown(
        """
        <div class="hero">
            <div class="hero-badge">⚖️ JusticeConnect</div>
            <h1 class="hero-title">A stronger voice for every citizen.</h1>
            <p class="hero-subtitle">Report issues, understand your rights, access government services, and track complaint updates in one transparent and citizen-first platform.</p>
            <div class="cta-row">
                <a class="cta-btn primary" href="#">📝 Report a problem</a>
                <a class="cta-btn secondary" href="#">🔎 Track complaint</a>
            </div>
            <div class="hero-pill-row">
                <span class="hero-pill">⚡ Fast Submission</span>
                <span class="hero-pill">📡 SMS + Email Alerts</span>
                <span class="hero-pill">🧭 Civic Support</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown(
            f'<div class="section-label">{t("Why it matters", "ఎందుకు ముఖ్యమైనది")}</div>',
            unsafe_allow_html=True
        )
        st.markdown(
            f'<div class="subtitle">{t("JusticeConnect gives citizens a direct path to report problems, discover public services, understand their rights, and stay informed through transparent grievance handling.", "JusticeConnect పౌరులకు సమస్యలను నివేదించేందుకు, ప్రభుత్వ సేవలను తెలుసుకునేందుకు, వారి హక్కులను అర్థం చేసుకునేందుకు మరియు పారదర్శకమైన ఫిర్యాదు పరిష్కారంతో సమాచారం పొందేందుకు స్పష్టమైన మార్గాన్ని అందిస్తుంది.")}</div>',
            unsafe_allow_html=True
        )

    with col_right:
        st.markdown(
            """
            <div class="hero-panel">
                <h4>📊 Platform Snapshot</h4>
                <div class="stat-row">
                    <div class="mini-stat"><strong>24/7</strong><span>Citizen support</span></div>
                    <div class="mini-stat"><strong>30D</strong><span>Auto retention</span></div>
                    <div class="mini-stat"><strong>SMS</strong><span>Email alerts</span></div>
                    <div class="mini-stat"><strong>Live</strong><span>Status updates</span></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown(
        f'<div class="section-label" style="margin-top: 26px;">{t("What you can do", "మీరు ఏమి చేయగలరు")}</div>',
        unsafe_allow_html=True
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            """
            <div class="feature-card">
                <div style="font-size: 2rem;">📝</div>
                <h3>Report</h3>
                <p>Submit civic issues, local problems, or service complaints in just a few steps.</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c2:
        st.markdown(
            """
            <div class="feature-card">
                <div style="font-size: 2rem;">🔎</div>
                <h3>Track</h3>
                <p>Use your Complaint ID to follow the latest status and updates in real time.</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c3:
        st.markdown(
            """
            <div class="feature-card">
                <div style="font-size: 2rem;">⚖️</div>
                <h3>Rights</h3>
                <p>Learn about citizen rights, grievance channels, and public service access.</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown(
        f'<div class="section-label" style="margin-top: 26px;">{t("How it works", "ఇది ఎలా పనిచేస్తుంది")}</div>',
        unsafe_allow_html=True
    )

    steps = [
        ("1", t("Report", "నివేదించండి"), t("Citizen submits a concern or complaint.", "పౌరుడు సమస్య లేదా ఫిర్యాదును సమర్పిస్తాడు.")),
        ("2", t("Get ID", "ID పొందండి"), t("A unique complaint ID is generated immediately.", "విశేష Complaint ID వెంటనే రూపొందించబడుతుంది.")),
        ("3", t("Review", "సమీక్ష"), t("The relevant department reviews the issue.", "సంబంధిత శాఖ సమస్యను సమీక్షిస్తుంది.")),
        ("4", t("Track", "ట్రాక్"), t("The citizen follows the status and updates.", "పౌరుడు స్థితి మరియు నవీకరణలను పర్యవేక్షిస్తాడు.")),
        ("5", t("Resolve", "పరిష్కరించు"), t("The matter is addressed and closed transparently.", "సమస్య పారదర్శకంగా పరిష్కరించబడుతుంది."))
    ]

    cols = st.columns(5)

    for i, step in enumerate(steps):
        with cols[i]:
            st.markdown(
                f"""
                <div class="step-box">
                    <div class="step-number">{step[0]}</div>
                    <h4>{step[1]}</h4>
                    <p>{step[2]}</p>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.markdown(
        """
        <div style="margin-top: 28px; padding: 14px 18px; background: linear-gradient(90deg, #eff6ff 0%, #f8fafc 100%); border: 1px solid #dbeafe; border-radius: 16px; color: #1e3a8a; font-weight: 600;">
            ✅ Aligned with UN Sustainable Development Goal 16: Peace, Justice and Strong Institutions.
        </div>
        """,
        unsafe_allow_html=True
    )

elif menu == t("Report a Problem", "సమస్యను నివేదించండి"):

    st.title("📝 " + t(
        "Report a Problem",
        "సమస్యను నివేదించండి"
    ))

    st.write(
        t(
            "Submit your complaint. You can attach an image or PDF as supporting evidence.",
            "మీ ఫిర్యాదును సమర్పించండి. ఆధారంగా చిత్రం లేదా PDF ను జత చేయవచ్చు."
        )
    )

    with st.form("complaint_form"):

        col1, col2 = st.columns(2)

        with col1:

            name = st.text_input(
                t("Citizen Name *", "పౌరుడి పేరు *")
            )

            mobile = st.text_input(
                t("Mobile Number *", "మొబైల్ నంబర్ *"),
                placeholder="+919876543210"
            )

            email = st.text_input(
                t("Email *", "ఇమెయిల్ *"),
                placeholder="yourname@gmail.com"
            )

            category = st.selectbox(
                t("Problem Category *", "సమస్య వర్గం *"),
                [
                    "Public Safety",
                    "Roads & Infrastructure",
                    "Water Supply",
                    "Electricity",
                    "Public Transport",
                    "Corruption",
                    "Government Service",
                    "Education",
                    "Healthcare",
                    "Other",
                    "OT"
                ]
            )

        with col2:

            department = st.selectbox(
                t("Department *", "శాఖ *"),
                [
                    "Municipal Administration",
                    "Police Department",
                    "Electricity Department",
                    "Water Supply Department",
                    "Transport Department",
                    "Revenue Department",
                    "Education Department",
                    "Health Department",
                    "Other",
                    "OT"
                ]
            )

            location = st.text_input(
                t("Location *", "ప్రాంతం *")
            )

            description = st.text_area(
                t(
                    "Describe the Problem *",
                    "సమస్యను వివరించండి *"
                ),
                height=180
            )

        uploaded_file = st.file_uploader(
            t(
                "Upload supporting image or PDF",
                "సంబంధిత చిత్రం లేదా PDF అప్లోడ్ చేయండి"
            ),
            type=[
                "png",
                "jpg",
                "jpeg",
                "pdf"
            ]
        )

        if uploaded_file:
            st.info(
                f"📎 {uploaded_file.name} "
                f"({uploaded_file.size / 1024:.1f} KB)"
            )

        submitted = st.form_submit_button(
            t(
                "Submit Complaint",
                "ఫిర్యాదును సమర్పించండి"
            ),
            use_container_width=True
        )

    if submitted:

        mobile = (mobile or "").strip()
        email = (email or "").strip()

        if not name or not mobile or not email or not location or not description:
            st.error(
                t(
                    "Please fill all required fields.",
                    "అవసరమైన అన్ని వివరాలను నమోదు చేయండి."
                )
            )
        elif not mobile.isdigit() and not mobile.startswith("+91"):
            st.error(
                t(
                    "Phone number must start with +91 and contain only digits after the prefix.",
                    "మొబైల్ నంబర్ +91 తో ప్రారంభించి, ప్రిఫిక్స్ తర్వాత మాత్రమే అంకెలను కలిగి ఉండాలి."
                )
            )
        elif not is_valid_mobile_number(mobile):
            st.error(
                t(
                    "Phone number must be in the format +91XXXXXXXXXX with 10 digits after +91.",
                    "ఫోన్ నంబర్ +91XXXXXXXXXX ఫార్మాట్‌లో ఉండాలి, +91 తర్వాత 10 అంకెలు ఉండాలి."
                )
            )
        elif not is_valid_gmail(email):
            st.error(
                t(
                    "Email must be a valid Gmail address ending with @gmail.com.",
                    "ఇమెయిల్ తప్పనిసరిగా Gmail రూపంలో ఉండాలి, @gmail.com తో ముగియాలి."
                )
            )
        else:

            attachment = None
            attachment_name = None
            attachment_type = None

            if uploaded_file:

                attachment = uploaded_file.getvalue()
                attachment_name = uploaded_file.name
                attachment_type = uploaded_file.type

            complaint_id = add_complaint(
                name,
                mobile,
                email,
                category,
                department,
                location,
                description,
                attachment,
                attachment_name,
                attachment_type
            )

            notification_sent = send_complaint_notification(
                complaint_id,
                name,
                email,
                mobile,
                department,
                description
            )

            if notification_sent:
                st.info(
                    t(
                        "A confirmation email has been sent to the citizen and the receiving department.",
                        "సిటిజన్ మరియు అంద받ే శాఖకు కన్ఫర్మేషన్ ఇమెయిల్ పంపబడింది."
                    )
                )
            else:
                st.info(
                    t(
                        "Complaint saved successfully. Email sending is not enabled yet until SMTP settings are configured.",
                        "ఫిర్యాదు సేవ్ చేయబడింది. SMTP సెట్టింగులు కాన్ఫిగర్ చేయకపోతే ఇమెయిల్ పంపడం అందుబాటులో ఉండదు."
                    )
                )

            st.success(
                t(
                    "Complaint submitted successfully!",
                    "ఫిర్యాదు విజయవంతంగా సమర్పించబడింది!"
                )
            )

            st.subheader(
                t(
                    "Your Complaint ID",
                    "మీ Complaint ID"
                )
            )

            st.code(complaint_id)

            if uploaded_file:
                st.success(
                    t(
                        "Your supporting file has been securely stored with the complaint record.",
                        "మీ సంబంధిత ఫైల్ ఫిర్యాదు రికార్డుతో సేవ్ చేయబడింది."
                    )
                )

            st.warning(
                t(
                    "Save this Complaint ID. You need it to track your complaint.",
                    "ఈ Complaint ID ని భద్రపరచండి. ఫిర్యాదును ట్రాక్ చేయడానికి ఇది అవసరం."
                )
            )

elif menu == t("Track Complaint", "ఫిర్యాదును ట్రాక్ చేయండి"):

    st.title("🔎 " + t(
        "Track Complaint",
        "ఫిర్యాదును ట్రాక్ చేయండి"
    ))

    complaint_id = st.text_input(
        t(
            "Enter Complaint ID",
            "Complaint ID నమోదు చేయండి"
        ),
        placeholder="JC-20260819-ABC123"
    )

    mobile_to_search = st.text_input(
        t(
            "Enter your mobile number to view all submitted complaints",
            "మీరు సమర్పించిన అన్ని ఫిర్యాదులను చూడటానికి మొబైల్ నంబర్ నమోదు చేయండి"
        ),
        placeholder="9876543210"
    )

    if st.button(
        t(
            "Track Complaint",
            "ఫిర్యాదును ట్రాక్ చేయండి"
        ),
        use_container_width=True
    ):

        if complaint_id:

            complaint = get_complaint(
                complaint_id.strip().upper()
            )

            if complaint:

                st.success(
                    t(
                        "Complaint found.",
                        "ఫిర్యాదు కనుగొనబడింది."
                    )
                )

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(
                        "Complaint ID",
                        complaint["complaint_id"]
                    )

                with col2:
                    st.metric(
                        "Status",
                        complaint["status"]
                    )

                with col3:
                    st.metric(
                        "Department",
                        complaint["department"]
                    )

                st.subheader(
                    t(
                        "Complaint Details",
                        "ఫిర్యాదు వివరాలు"
                    )
                )

                details = {
                    "Citizen": complaint["name"],
                    "Category": complaint["category"],
                    "Location": complaint["location"],
                    "Description": complaint["description"],
                    "Submitted": complaint["created_at"],
                    "Last Updated": complaint["updated_at"]
                }

                st.table(
                    pd.DataFrame(
                        list(details.items()),
                        columns=[
                            "Field",
                            "Details"
                        ]
                    )
                )

                if complaint["attachment"]:

                    st.subheader(
                        "📎 Supporting Document"
                    )

                    st.write(
                        complaint["attachment_name"]
                    )

                    st.caption(
                        "Attachments are available for administrative review."
                    )

                st.subheader(
                    t(
                        "Status Timeline",
                        "స్థితి టైమ్‌లైన్"
                    )
                )

                history = get_status_history(
                    complaint["complaint_id"]
                )

                for index, item in enumerate(history):

                    if index == len(history) - 1:

                        st.success(
                            f"🟢 {item['status']} — {item['updated_at']}"
                        )

                    else:

                        st.write(
                            f"✅ {item['status']} — {item['updated_at']}"
                        )

            else:

                st.error(
                    t(
                        "Complaint ID not found.",
                        "Complaint ID కనుగొనబడలేదు."
                    )
                )

        elif mobile_to_search:

            complaints = get_complaints_by_mobile(
                mobile_to_search.strip()
            )

            if complaints:
                st.success(
                    t(
                        "Your submitted complaints are listed below.",
                        "మీరు సమర్పించిన ఫిర్యాదులు క్రింద చూపబడ్డాయి."
                    )
                )

                complaint_df = pd.DataFrame(
                    [
                        {
                            "Complaint ID": row["complaint_id"],
                            "Category": row["category"],
                            "Department": row["department"],
                            "Status": row["status"],
                            "Location": row["location"],
                            "Submitted": row["created_at"]
                        }
                        for row in complaints
                    ]
                )

                st.dataframe(
                    complaint_df,
                    use_container_width=True,
                    hide_index=True
                )

            else:
                st.warning(
                    t(
                        "No complaints found for this mobile number.",
                        "ఈ మొబైల్ నంబర్ కోసం ఫిర్యాదులు ఏవీ కనుగొనబడలేదు."
                    )
                )

        else:
            st.warning(
                t(
                    "Please enter a Complaint ID or mobile number.",
                    "Complaint ID లేదా మొబైల్ నంబర్ నమోదు చేయండి."
                )
            )

    elif mobile_to_search:

        complaints = get_complaints_by_mobile(
            mobile_to_search.strip()
        )

        if complaints:
            st.success(
                t(
                    "Your submitted complaints are listed below.",
                    "మీరు సమర్పించిన ఫిర్యాదులు క్రింద చూపబడ్డాయి."
                )
            )

            complaint_df = pd.DataFrame(
                [
                    {
                        "Complaint ID": row["complaint_id"],
                        "Category": row["category"],
                        "Department": row["department"],
                        "Status": row["status"],
                        "Location": row["location"],
                        "Submitted": row["created_at"]
                    }
                    for row in complaints
                ]
            )

            st.dataframe(
                complaint_df,
                use_container_width=True,
                hide_index=True
            )

        else:
            st.warning(
                t(
                    "No complaints found for this mobile number.",
                    "ఈ మొబైల్ నంబర్ కోసం ఫిర్యాదులు ఏవీ కనుగొనబడలేదు."
                )
            )

elif menu == t("Know Your Rights", "మీ హక్కులు తెలుసుకోండి"):

    st.title("⚖️ " + t(
        "Know Your Rights",
        "మీ హక్కులు తెలుసుకోండి"
    ))

    rights = {
        "Right to Information": "Citizens can seek information from public authorities under applicable RTI procedures.",
        "Right to Public Services": "Citizens can access government services subject to eligibility and applicable rules.",
        "Right to File a Complaint": "Citizens can submit complaints to appropriate government departments and authorities.",
        "Right to Grievance Redressal": "Citizens may seek resolution of eligible grievances through appropriate grievance mechanisms.",
        "Right to Equality": "Public institutions should provide services according to applicable law without unlawful discrimination.",
        "Right to Privacy": "Personal information should be handled responsibly and protected according to applicable law."
    }

    search = st.text_input(
        t(
            "Search rights",
            "హక్కులను వెతకండి"
        )
    )

    for title, description in rights.items():

        if not search or search.lower() in title.lower():

            with st.expander("⚖️ " + title):

                st.write(description)

elif menu == t("Government Services", "ప్రభుత్వ సేవలు"):

    st.title("🏛️ " + t(
        "Government Services",
        "ప్రభుత్వ సేవలు"
    ))

    services = [
        {
            "Service": "Birth Certificate",
            "Department": "Municipal Administration",
            "Documents": "Hospital record, parent identification",
            "Process": "Apply through the relevant local authority."
        },
        {
            "Service": "Income Certificate",
            "Department": "Revenue Department",
            "Documents": "Identity proof, address proof, income details",
            "Process": "Submit an application through the applicable government service portal."
        },
        {
            "Service": "Caste Certificate",
            "Department": "Revenue Department",
            "Documents": "Identity proof, address proof, supporting records",
            "Process": "Apply through the applicable revenue authority."
        },
        {
            "Service": "Driving Licence",
            "Department": "Transport Department",
            "Documents": "Identity proof, address proof, required application documents",
            "Process": "Apply through the official transport service system."
        },
        {
            "Service": "Electricity Complaint",
            "Department": "Electricity Department",
            "Documents": "Service/consumer number and complaint details",
            "Process": "Submit the complaint through the relevant electricity provider."
        }
    ]

    search = st.text_input(
        t(
            "Search services",
            "సేవలను వెతకండి"
        )
    )

    for service in services:

        if (
            not search
            or search.lower() in service["Service"].lower()
            or search.lower() in service["Department"].lower()
        ):

            with st.expander(
                "🏛️ " + service["Service"]
            ):

                st.write(
                    "**Department:**",
                    service["Department"]
                )

                st.write(
                    "**Required Documents:**",
                    service["Documents"]
                )

                st.write(
                    "**Process:**",
                    service["Process"]
                )

elif menu == t("Citizen Assistant", "సిటిజన్ అసిస్టెంట్"):

    st.title("🤖 " + t(
        "Citizen Assistant",
        "సిటిజన్ అసిస్టెంట్"
    ))

    question = voice_assistant_input(
        st.session_state.get("voice_question", "")
    )

    if question:
        st.session_state["voice_question"] = question

    if st.button(
        t(
            "Ask Assistant",
            "అసిస్టెంట్‌ను అడగండి"
        ),
        use_container_width=True
    ):

        q = question.lower()

        if "complaint" in q or "report" in q or "problem" in q:

            answer = (
                "Use Report a Problem to submit your issue. "
                "A unique Complaint ID will be generated."
            )

        elif "track" in q or "status" in q:

            answer = (
                "Use Track Complaint and enter your Complaint ID "
                "to view the latest status."
            )

        elif "right" in q:

            answer = (
                "Open Know Your Rights to explore basic information "
                "about citizen rights."
            )

        elif "service" in q or "certificate" in q:

            answer = (
                "Open Government Services to find information "
                "about available services."
            )

        elif "id" in q:

            answer = (
                "Your Complaint ID is generated automatically "
                "after submitting a complaint."
            )

        else:

            answer = (
                "I can help with complaint reporting, complaint "
                "tracking, citizen rights and government services."
            )

        st.success(answer)

elif menu == t("Transparency Dashboard", "పారదర్శకత డ్యాష్‌బోర్డ్"):

    st.title(
        "📊 " + t(
            "Transparency Dashboard",
            "పారదర్శకత డ్యాష్‌బోర్డ్"
        )
    )

    complaints = get_all_complaints()

    if complaints:

        df = pd.DataFrame(
            [dict(row) for row in complaints]
        )

        total = len(df)
        submitted = len(
            df[df["status"] == "Submitted"]
        )
        review = len(
            df[df["status"] == "Under Review"]
        )
        progress = len(
            df[df["status"] == "In Progress"]
        )
        resolved = len(
            df[df["status"] == "Resolved"]
        )

        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric("Total", total)
        c2.metric("Submitted", submitted)
        c3.metric("Under Review", review)
        c4.metric("In Progress", progress)
        c5.metric("Resolved", resolved)

        col1, col2 = st.columns(2)

        with col1:

            status_data = (
                df["status"]
                .value_counts()
                .reset_index()
            )

            status_data.columns = [
                "Status",
                "Count"
            ]

            fig = px.pie(
                status_data,
                names="Status",
                values="Count",
                title="Complaints by Status"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        with col2:

            category_data = (
                df["category"]
                .value_counts()
                .reset_index()
            )

            category_data.columns = [
                "Category",
                "Count"
            ]

            fig2 = px.bar(
                category_data,
                x="Category",
                y="Count",
                title="Complaints by Category"
            )

            st.plotly_chart(
                fig2,
                use_container_width=True
            )

        st.subheader(
            "Department-wise Complaints"
        )

        department_data = (
            df["department"]
            .value_counts()
            .reset_index()
        )

        department_data.columns = [
            "Department",
            "Complaints"
        ]

        st.dataframe(
            department_data,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "No complaints have been submitted yet."
        )

elif menu == t("User Login", "వినియోగదారు లాగిన్"):

    if not st.session_state.user_logged_in:

        st.title("👤 User Login")

        username = st.text_input(
            "Username"
        )

        password = st.text_input(
            "Password",
            type="password"
        )

        if st.button(
            "Login as User",
            use_container_width=True
        ):

            if login_user(
                username,
                password
            ):

                st.session_state.user_logged_in = True
                st.session_state.admin_logged_in = False
                st.success(
                    "User login successful."
                )
                st.rerun()

            else:

                st.error(
                    "Invalid username or password."
                )

        st.info(
            "Demo user credentials: user / user123"
        )

    else:

        st.title("👤 Citizen Dashboard")

        if st.button(
            "Logout",
            use_container_width=True
        ):

            st.session_state.user_logged_in = False
            st.rerun()

        st.success(
            "You are logged in as a citizen user."
        )
        st.info(
            "You can now report complaints and track them."
        )

elif menu == t("Admin Login", "అడ్మిన్ లాగిన్"):

    if not st.session_state.admin_logged_in:

        st.title("🔐 Admin Login")

        username = st.text_input(
            "Username"
        )

        password = st.text_input(
            "Password",
            type="password"
        )

        if st.button(
            "Login",
            use_container_width=True
        ):

            if login_admin(
                username,
                password
            ):

                st.session_state.admin_logged_in = True
                st.session_state.user_logged_in = False
                st.success(
                    "Login successful."
                )
                st.rerun()

            else:

                st.error(
                    "Invalid username or password."
                )

        st.info(
            "Demo credentials: HEMU / hemu@5622s"
        )

    else:

        st.title("🔐 Admin Dashboard")

        if st.button(
            "Logout",
            use_container_width=True
        ):

            st.session_state.admin_logged_in = False
            st.rerun()

        complaints = get_all_complaints()

        if complaints:

            df = pd.DataFrame(
                [dict(row) for row in complaints]
            )

            st.subheader(
                "Complaint Management"
            )

            selected_id = st.selectbox(
                "Select Complaint",
                df["complaint_id"].tolist()
            )

            complaint = get_complaint(
                selected_id
            )

            if complaint:

                col1, col2 = st.columns(2)

                with col1:

                    st.write(
                        "**Citizen:**",
                        complaint["name"]
                    )

                    st.write(
                        "**Mobile:**",
                        complaint["mobile"]
                    )

                    st.write(
                        "**Email:**",
                        complaint["email"] or "Not provided"
                    )

                    st.write(
                        "**Category:**",
                        complaint["category"]
                    )

                    st.write(
                        "**Department:**",
                        complaint["department"]
                    )

                with col2:

                    st.write(
                        "**Location:**",
                        complaint["location"]
                    )

                    st.write(
                        "**Submitted:**",
                        complaint["created_at"]
                    )

                    st.write(
                        "**Last Updated:**",
                        complaint["updated_at"]
                    )

                    st.write(
                        "**Current Status:**",
                        complaint["status"]
                    )

                st.write(
                    "**Description:**",
                    complaint["description"]
                )

                st.divider()

                st.subheader(
                    "📎 Supporting Attachment"
                )

                if complaint["attachment"]:

                    file_data = complaint["attachment"]
                    file_name = complaint["attachment_name"]
                    file_type = complaint["attachment_type"]

                    st.success(
                        f"Attachment available: {file_name}"
                    )

                    if file_type == "application/pdf":

                        st.download_button(
                            label="⬇️ Download PDF",
                            data=file_data,
                            file_name=file_name,
                            mime="application/pdf",
                            use_container_width=True
                        )

                        pdf_display = f"""
                        <iframe
                            src="data:application/pdf;base64,{__import__('base64').b64encode(file_data).decode()}"
                            width="100%"
                            height="600"
                            type="application/pdf">
                        </iframe>
                        """

                        st.markdown(
                            pdf_display,
                            unsafe_allow_html=True
                        )

                    elif file_type in [
                        "image/png",
                        "image/jpeg",
                        "image/jpg"
                    ]:

                        st.image(
                            file_data,
                            caption=file_name,
                            use_container_width=True
                        )

                        st.download_button(
                            label="⬇️ Download Image",
                            data=file_data,
                            file_name=file_name,
                            mime=file_type,
                            use_container_width=True
                        )

                    else:

                        st.download_button(
                            label="⬇️ Download Attachment",
                            data=file_data,
                            file_name=file_name,
                            mime=file_type or "application/octet-stream",
                            use_container_width=True
                        )

                else:

                    st.info(
                        "No attachment was submitted with this complaint."
                    )

                st.divider()

                st.subheader(
                    "🔄 Update Complaint Status"
                )

                statuses = [
                    "Submitted",
                    "Under Review",
                    "In Progress",
                    "Resolved"
                ]

                new_status = st.selectbox(
                    "Select New Status",
                    statuses,
                    index=statuses.index(
                        complaint["status"]
                    )
                )

                if st.button(
                    "Update Complaint Status",
                    use_container_width=True
                ):

                    update_status(
                        selected_id,
                        new_status
                    )

                    st.success(
                        "Complaint status updated successfully."
                    )

                    st.rerun()

                st.divider()

                st.subheader(
                    "📋 Status History"
                )

                history = get_status_history(
                    selected_id
                )

                for item in history:

                    st.write(
                        f"**{item['status']}** — {item['updated_at']}"
                    )

        else:

            st.info(
                "No complaints available."
            )

st.sidebar.divider()

st.sidebar.caption(
    "JusticeConnect • SDG 16 • Peace, Justice and Strong Institutions"
)

st.sidebar.caption(
    "Academic Prototype"
)