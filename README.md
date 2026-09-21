# JusticeConnect

## Complaint notifications

Complaint submission emails are sent to the complainant and assigned member. Configure Gmail SMTP in Streamlit Cloud under **Settings -> Secrets**:

```toml
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "your-account@gmail.com"
SMTP_PASSWORD = "your-16-character-gmail-app-password"
MEMBER_EMAIL = "assigned-member@example.com"
```

`SMTP_PASSWORD` must be a Google App Password, not your normal Gmail password. The Gmail account must have two-step verification enabled before an App Password can be created. Never commit `secrets.toml` or expose the App Password in source code.

The complaint is written to `justiceconnect.db` beside `app.py`, so it remains available after Streamlit or the computer is shut down. Records are retained for 30 days by default and are removed on the first app start after they become older than 30 days. To change the retention period, set `COMPLAINT_RETENTION_DAYS` before starting Streamlit.

For SMS notifications to the mobile number entered with a complaint, configure Twilio as well:

```powershell
$env:TWILIO_ACCOUNT_SID = "your-account-sid"
$env:TWILIO_AUTH_TOKEN = "your-auth-token"
$env:TWILIO_FROM_NUMBER = "+10000000000"
```

The citizen's entered Gmail address receives the complaint confirmation email. Email and SMS delivery are optional: the complaint is saved even when either provider is unavailable.

`MEMBER_EMAIL` is used for every department. A department-specific value can be supplied with names such as `MEMBER_EMAIL_POLICE_DEPARTMENT` or `MEMBER_EMAIL_WATER_SUPPLY_DEPARTMENT`. When no member email is supplied, the configured department address is used.

The Citizen Assistant includes browser speech recognition in supported Chrome and Edge browsers. Microphone permission must be allowed; the text input remains available as a fallback.