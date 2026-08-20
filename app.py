import streamlit as st
import sqlite3
import uuid
from datetime import datetime
import pandas as pd
import plotly.express as px

DB_NAME = "justiceconnect.db"

st.set_page_config(
    page_title="JusticeConnect",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
        ("Hemu", "hemu5622s")
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

def t(en, te):
    return te if st.session_state.language == "Telugu" else en

init_db()

if "language" not in st.session_state:
    st.session_state.language = "English"

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

st.markdown("""
<style>
.main-title {
    font-size: 42px;
    font-weight: 800;
    margin-bottom: 0;
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
        '<div class="main-title">⚖️ JusticeConnect</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="subtitle">{t("A citizen-first platform for complaints, rights, government services and transparent tracking.", "ఫిర్యాదులు, హక్కులు, ప్రభుత్వ సేవలు మరియు పారదర్శకమైన ట్రాకింగ్ కోసం పౌర కేంద్రిత వేదిక.")}</div>',
        unsafe_allow_html=True
    )

    st.divider()

    st.info(
        t(
            "Aligned with UN Sustainable Development Goal 16: Peace, Justice and Strong Institutions.",
            "ఐక్యరాజ్య సమితి SDG 16: శాంతి, న్యాయం మరియు బలమైన సంస్థలకు అనుగుణంగా రూపొందించబడింది."
        )
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="card">
        <h2>📝 Report</h2>
        <p>Submit a public problem or complaint easily.</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="card">
        <h2>🔎 Track</h2>
        <p>Use your Complaint ID to check progress.</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="card">
        <h2>⚖️ Rights</h2>
        <p>Understand basic rights and available guidance.</p>
        </div>
        """, unsafe_allow_html=True)

    st.subheader(
        t(
            "How JusticeConnect Works",
            "JusticeConnect ఎలా పనిచేస్తుంది"
        )
    )

    steps = [
        ("1", "Report", "Citizen submits a complaint"),
        ("2", "Complaint ID", "System generates a unique ID"),
        ("3", "Review", "Concerned department reviews it"),
        ("4", "Track", "Citizen checks progress"),
        ("5", "Resolution", "Complaint is resolved")
    ]

    cols = st.columns(5)

    for i, step in enumerate(steps):
        with cols[i]:
            st.metric(step[1], step[0])
            st.caption(step[2])

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
                t("Mobile Number *", "మొబైల్ నంబర్ *")
            )

            email = st.text_input(
                t("Email", "ఇమెయిల్")
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
                    "Other"
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
                    "Other"
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

        if not name or not mobile or not location or not description:

            st.error(
                t(
                    "Please fill all required fields.",
                    "అవసరమైన అన్ని వివరాలను నమోదు చేయండి."
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

    question = st.text_input(
        t(
            "Ask your question",
            "మీ ప్రశ్న అడగండి"
        )
    )

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
                st.success(
                    "Login successful."
                )
                st.rerun()

            else:

                st.error(
                    "Invalid username or password."
                )

        st.info(
            "Demo credentials: admin / admin123"
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