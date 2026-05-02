import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Callable

import reflex as rx
import reflex_local_auth
import sqlmodel

from linen_draper.models import InterventionAlert, UserInfo

logger = logging.getLogger(__name__)

EMAIL_DIR = Path(".emails")
LATEST_EMAIL = EMAIL_DIR / "latest.html"


def _get_env() -> str:
    return os.environ.get("APP_ENV", "local")


def _build_email_html(alerts: list[InterventionAlert], username: str, report_label: str = "") -> str:
    label = f" ({report_label})" if report_label else ""
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
    <h2>Arch Linux Manual Intervention Report{label}</h2>
    <p>Hello {username}, here are the Arch Linux news items requiring manual intervention:</p>
    <table>
        <thead><tr><th>Date</th><th>Title</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>
    <p><small>Sent by <a href="https://github.com/sam/linen-draper">linen-draper</a> at {datetime.now(timezone.utc).isoformat()}</small></p>
</body>
</html>"""


async def _send_report(
    channel: str,
    enabled_field: str,
    last_sent_field: str,
    time_window_filter: Callable[[InterventionAlert], bool] | None,
    report_label: str,
) -> None:
    env = _get_env()
    logger.info(f"Sending {channel} report (env={env})")

    with rx.session() as session:
        alerts = list(session.exec(
            sqlmodel.select(InterventionAlert).order_by(
                sqlmodel.desc(InterventionAlert.pub_date)  # type: ignore
            )
        ).all())

        users = list(session.exec(
            sqlmodel.select(UserInfo).where(
                getattr(UserInfo, enabled_field)  # type: ignore[arg-type]
            )
        ).all())

        if not alerts:
            logger.info(f"No alerts to send ({channel})")
            return

        if not users:
            logger.info(f"No users with {channel} enabled")
            return

        for user_info in users:
            user = session.exec(
                sqlmodel.select(reflex_local_auth.LocalUser).where(
                    reflex_local_auth.LocalUser.id == user_info.user_id  # type: ignore
                )
            ).first()

            username = getattr(user, "username", "user") if user else "user"

            # Apply time window filter if provided
            if time_window_filter:
                applicable = [a for a in alerts if time_window_filter(a)]
            else:
                applicable = alerts

            # Skip if no alerts in the time window
            if not applicable:
                logger.info(f"No {channel} alerts within window for {user_info.email}")
                continue

            # For daily: skip if no new alerts since last send
            if channel == "daily":
                last_sent = getattr(user_info, last_sent_field)
                if last_sent:
                    new_alerts = [
                        a for a in applicable
                        if a.created_at.replace(tzinfo=timezone.utc)
                        > last_sent.replace(tzinfo=timezone.utc)
                    ]
                    if not new_alerts:
                        logger.info(f"No new alerts for {user_info.email}")
                        continue
                else:
                    new_alerts = applicable
            else:
                new_alerts = applicable

            html_body = _build_email_html(new_alerts, username, report_label)

            if env == "local":
                EMAIL_DIR.mkdir(parents=True, exist_ok=True)
                LATEST_EMAIL.write_text(html_body)
                logger.info(
                    f"[local] Would send {len(new_alerts)} {channel} alerts to "
                    f"{user_info.email} -> {LATEST_EMAIL}"
                )
            else:
                await _smtp_send(user_info.email, html_body, report_label)

            setattr(user_info, last_sent_field, datetime.now(timezone.utc))
            session.add(user_info)
            session.commit()


async def send_daily_digest() -> None:
    await _send_report(
        channel="daily",
        enabled_field="email_enabled",
        last_sent_field="last_email_sent_at",
        time_window_filter=None,
        report_label="Daily",
    )


def _weekly_filter(alert: InterventionAlert) -> bool:
    """Return True if the alert was published within the last 7 days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    pub = alert.pub_date
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    return pub >= cutoff


async def send_weekly_report() -> None:
    await _send_report(
        channel="weekly",
        enabled_field="weekly_enabled",
        last_sent_field="last_weekly_sent_at",
        time_window_filter=_weekly_filter,
        report_label="Weekly",
    )


def _monthly_filter(alert: InterventionAlert) -> bool:
    """Return True if the alert was published within the last 30 days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    pub = alert.pub_date
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    return pub >= cutoff


async def send_monthly_report() -> None:
    await _send_report(
        channel="monthly",
        enabled_field="monthly_enabled",
        last_sent_field="last_monthly_sent_at",
        time_window_filter=_monthly_filter,
        report_label="Monthly",
    )


async def _smtp_send(to_email: str, html_body: str, report_label: str = "") -> None:
    import aiosmtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    from_email = os.environ["SMTP_FROM"]

    label = f" ({report_label})" if report_label else ""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Arch Linux Manual Intervention Report{label}"
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
    logger.info(f"Sent {report_label.lower()} email to {to_email}" if report_label else f"Sent email to {to_email}")
