"""
Albert OS Plugin — Home Assistant (Smart Home)
Kategooria: Smart Home
Permissions: internet, notifications
"""
import os
import httpx
from core.plugin_sdk import AlbertPlugin, Permission


class HomeAssistantPlugin(AlbertPlugin):
    plugin_id   = "homeassistant"
    name        = "Home Assistant"
    version     = "1.0.0"
    author      = "Albert OS"
    description = "Juhib Home Assistant seadmeid häälkäsklustega"
    permissions = [Permission.INTERNET, Permission.NOTIFICATIONS]
    commands    = ["lülita", "temperatuur", "seadmete_olek"]

    async def on_startup(self):
        self._url   = os.getenv("HA_URL", "")        # nt. http://192.168.1.100:8123
        self._token = os.getenv("HA_TOKEN", "")
        if not self._url or not self._token:
            self.notify("HA_URL või HA_TOKEN puudub — Home Assistant plugin passiivselt", "info")

    def _headers(self):
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    async def on_voice_command(self, text: str, lang: str) -> str | None:
        t = text.lower()
        if not self._url:
            return None

        # "lülita [sisse/välja] [seade]"
        if any(kw in t for kw in ["lülita sisse", "включи", "turn on", "switch on"]):
            entity = self._extract_entity(t)
            return await self._service("homeassistant", "turn_on", entity)
        if any(kw in t for kw in ["lülita välja", "выключи", "turn off", "switch off"]):
            entity = self._extract_entity(t)
            return await self._service("homeassistant", "turn_off", entity)
        if any(kw in t for kw in ["temperatuur", "температура", "temperature"]) and "home" in t:
            return await self._get_temperature()
        if any(kw in t for kw in ["seadmete olek", "статус", "device status"]):
            return await self._get_states()
        return None

    def _extract_entity(self, text: str) -> str:
        # Lihtne heuristika — asenda täismahulise NLP-ga tulevikus
        keywords = {
            "tuli": "light.living_room", "valgus": "light.living_room",
            "свет": "light.living_room",  "light": "light.living_room",
            "garaaž": "cover.garage",     "гараж": "cover.garage",
            "värav": "cover.gate",
        }
        for kw, entity in keywords.items():
            if kw in text:
                return entity
        return "light.living_room"

    async def _service(self, domain: str, service: str, entity_id: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=6) as c:
                r = await c.post(f"{self._url}/api/services/{domain}/{service}",
                    headers=self._headers(), json={"entity_id": entity_id})
                if r.status_code in (200, 201):
                    action = "sisse lülitatud" if service == "turn_on" else "välja lülitatud"
                    return f"🏠 {entity_id} {action}"
                return f"🏠 HA viga: {r.status_code}"
        except Exception as e:
            return f"🏠 HA ühendus ebaõnnestus: {e}"

    async def _get_temperature(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=6) as c:
                r = await c.get(f"{self._url}/api/states/sensor.indoor_temperature",
                    headers=self._headers())
                if r.status_code == 200:
                    state = r.json()
                    return f"🌡 Toatemperatuur: {state.get('state', '?')}°C"
        except Exception as e:
            return f"🏠 Temperatuuri viga: {e}"
        return "🌡 Temperatuuri andur ei leidnud"

    async def _get_states(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=6) as c:
                r = await c.get(f"{self._url}/api/states", headers=self._headers())
                if r.status_code == 200:
                    states = r.json()
                    lights_on = [s["entity_id"] for s in states if s["entity_id"].startswith("light.") and s["state"] == "on"]
                    return f"🏠 Tuled põlevad: {len(lights_on)} ({', '.join(lights_on[:3])}{'...' if len(lights_on) > 3 else ''})"
        except Exception as e:
            return f"🏠 HA viga: {e}"
        return "🏠 Seadmete olekut ei saanud lugeda"
