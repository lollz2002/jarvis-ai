"""
Albert OS Plugin — Calendar (System)
Kategooria: System
Permissions: calendar, internet, notifications
"""
import os
import httpx
from core.plugin_sdk import AlbertPlugin, Permission


class CalendarPlugin(AlbertPlugin):
    plugin_id   = "calendar"
    name        = "Google Calendar"
    version     = "1.0.0"
    author      = "Albert OS"
    description = "Loe ja loo Google Calendar sündmusi häälkäskluste kaudu"
    permissions = [Permission.CALENDAR, Permission.INTERNET, Permission.NOTIFICATIONS]
    commands    = ["järgmine_sündmus", "lisa_sündmus", "tänane_päev"]

    async def on_startup(self):
        self._api_key = os.getenv("GOOGLE_CALENDAR_API_KEY", "")
        self._cal_id  = os.getenv("GOOGLE_CALENDAR_ID", "primary")

    async def on_voice_command(self, text: str, lang: str) -> str | None:
        t = text.lower()
        if any(kw in t for kw in ["järgmine sündmus", "следующее событие", "next event", "mis mul täna"]):
            return await self._get_next_event()
        if any(kw in t for kw in ["lisa sündmus", "добавь событие", "add event"]):
            return "📅 Sündmuse lisamine: ütle aeg ja pealkiri."
        return None

    async def _get_next_event(self) -> str:
        if not self._api_key:
            return "📅 Google Calendar API võti puudub. Lisa GOOGLE_CALENDAR_API_KEY Railway muutujatesse."
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(
                    f"https://www.googleapis.com/calendar/v3/calendars/{self._cal_id}/events",
                    params={"key": self._api_key, "timeMin": now, "maxResults": 1,
                            "singleEvents": True, "orderBy": "startTime"})
                if r.status_code == 200:
                    items = r.json().get("items", [])
                    if not items:
                        return "📅 Ei leitud tulevasi sündmusi."
                    ev = items[0]
                    start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", ""))
                    return f"📅 Järgmine: {ev.get('summary', '?')} — {start[:16].replace('T', ' ')}"
        except Exception as e:
            return f"📅 Calendar viga: {e}"
        return "📅 Ei saanud kalendrit lugeda."
