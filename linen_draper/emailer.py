import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import reflex as rx
import sqlmodel
from sqlalchemy import select

from linen_draper.models import InterventionAlert, UserInfo

logger = logging.getLogger(__name__)

EMAIL_DIR = Path(".emails")
LATEST_EMAIL = EMAIL_DIR / "latest.html"


def _get_env() -> str:
    return os.environ.get("APP_ENV", "local")


def _build_email_html(alerts: list[InterventionAlert], username: str) -> str:
    rows = ""
    for a in alerts:
        rows += f"""<tr>
            <td style="padding:8px;border-bottom:1px solid #ddd">{a.pub_date.strftime('%Y-%m-%d')}</td>
            <td style="padding:8px;border-bottom:1px solid #ddd"><a href="{a.link}">{a.title}</a></td>
        </tr>"""

    return f"""<html>
<head><style>
    body {{ font-family: sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ text-align: left; padding: 8px; background: #f5f5f5; }}
</style></head>
<body>
    <h2>Arch Linux Manual Intervention Report</h2>
    <p>Hello {username}, here are the latest Arch Linux news items requiring manual intervention:</p>
    <table>
        <thead><tr><th>Date</th><th>Title</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>
    <p><small>Sent by <a href="https://github.com/sam/linen-draper">linen-draper</a> at {datetime.now(timezone.utc).isoformat()}</small></p>
</body>
</html>"""


async def send_daily_digest():
    env = _get_env()
    logger.info(f"Sending daily digest (env={env})")

    with rx.session() as session:
        alerts = list(session.exec(
            select(InterventionAlert).order_by(
                sqlmodel.desc(InterventionAlert.pub_date)
            )
        ).all())

        users = list(session.exec(
            select(UserInfo).where(UserInfo.email_enabled == True)
        ).all())

        if not alerts:
            logger.info("No alerts to send")
            return

        if not users:
            logger.info("No users with email enabled")
            return

        for user_info in users:
            user = session.exec(
                select(rx.Model).where(
                    sqlmodel.text("localuser.id = :uid")
                ).params(uid=user_info.user_id)
            ).first()

            username = getattr(user, "username", "user") if user else "user"

            new_alerts = alerts
            if user_info.last_email_sent_at:
                new_alerts = [
                    a for a in alerts
                    if a.created_at.replace(tzinfo=timezone.utc)
                    > user_info.last_email_sent_at.replace(tzinfo=timezone.utc)
                ]
                if not new_alerts:
                    logger.info(f"No new alerts for {user_info.email}")
                    continue

            html_body = _build_email_html(new_alerts, username)

            if env == "local":
                EMAIL_DIR.mkdir(parents=True, exist_ok=True)
                LATEST_EMAIL.write_text(html_body)
                logger.info(
                    f"[local] Would send {len(new_alerts)} alerts to {user_info.email} "
                    f"-> {LATEST_EMAIL}"
                )
            else:
                await _smtp_send(user_info.email, html_body)

            user_info.last_email_sent_at = datetime.now(timezone.utc)
            session.add(user_info)
            session.commit()


async def _smtp_send(to_email: str, html_body: str):
    import aiosmtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    from_email = os.environ["SMTP_FROM"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Arch Linux Manual Intervention Report"
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    await aiosmtplib.send(
        msg,
        hostname=host,
        port=port,
        username=user,
        password=password,
        start_tls=True,
    )
    logger.info(f"Sent email to {to_email}")
