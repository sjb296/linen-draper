from typing import Optional

import reflex as rx
import sqlmodel

from linen_draper.state.auth import AuthState


class DashboardState(AuthState):
    alerts: list[dict] = []

    def on_load(self) -> Optional[rx.event.EventSpec]:
        if not self.is_authenticated:
            return
        with rx.session() as session:
            results = session.exec(
                sqlmodel.text("""
                    SELECT id, title, link, description, pub_date, created_at
                    FROM interventionalert
                    ORDER BY pub_date DESC
                """)
            ).all()

        self.alerts = []
        for row in results:
            self.alerts.append({
                "id": row[0],
                "title": row[1],
                "link": row[2],
                "description": row[3],
                "pub_date": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
                "created_at": row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
            })
