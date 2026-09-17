# JusticeConnect

## Complaint notifications

Complaint submission emails are sent to both the complainant and the assigned member. Configure SMTP before starting Streamlit:

```powershell
$env:SMTP_HOST = "smtp.gmail.com"
$env:SMTP_PORT = "587"
$env:SMTP_USERNAME = "your-account@gmail.com"
$env:SMTP_PASSWORD = "your-app-password"
$env:SMTP_FROM_EMAIL = "your-account@gmail.com"
$env:MEMBER_EMAIL = "assigned-member@example.com"
```

`MEMBER_EMAIL` is used for every department. A department-specific value can be supplied with names such as `MEMBER_EMAIL_POLICE_DEPARTMENT` or `MEMBER_EMAIL_WATER_SUPPLY_DEPARTMENT`. When no member email is supplied, the configured department address is used.

The Citizen Assistant includes browser speech recognition in supported Chrome and Edge browsers. Microphone permission must be allowed; the text input remains available as a fallback.