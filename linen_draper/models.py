import datetime

import reflex as rx
import sqlmodel


class InterventionAlert(rx.Model, table=True):
    title: str = sqlmodel.Field(sa_type=sqlmodel.Text)
    link: str = sqlmodel.Field(unique=True, index=True)
    description: str = sqlmodel.Field(sa_type=sqlmodel.Text)
    pub_date: datetime.datetime
    guid: str | None = sqlmodel.Field(default=None, unique=True, index=True)
    created_at: datetime.datetime = sqlmodel.Field(
        sa_column=sqlmodel.Column(
            sqlmodel.DateTime(timezone=True),
            server_default=sqlmodel.func.now(),
        ),
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    def dict(self, *args, **kwargs) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "description": self.description,
            "pub_date": self.pub_date.isoformat() if self.pub_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UserInfo(rx.Model, table=True):
    email: str = sqlmodel.Field(default="")
    email_enabled: bool = sqlmodel.Field(default=True)
    last_email_sent_at: datetime.datetime | None = sqlmodel.Field(default=None)
    weekly_enabled: bool = sqlmodel.Field(default=False)
    last_weekly_sent_at: datetime.datetime | None = sqlmodel.Field(default=None)
    monthly_enabled: bool = sqlmodel.Field(default=False)
    last_monthly_sent_at: datetime.datetime | None = sqlmodel.Field(default=None)
    user_id: int = sqlmodel.Field(foreign_key="localuser.id")
