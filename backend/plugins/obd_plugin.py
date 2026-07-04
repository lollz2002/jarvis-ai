"""
Albert OS Plugin — OBD-II (Vehicle)
Kategooria: Vehicle
Permissions: vehicle_data, internet
Toetab: ELM327 bluetooth/USB adapter, python-obd raamatukogu
"""
import os
import asyncio
from core.plugin_sdk import AlbertPlugin, Permission


class OBDPlugin(AlbertPlugin):
    plugin_id   = "obd2"
    name        = "OBD-II Diagnostics"
    version     = "1.0.0"
    author      = "Albert OS"
    description = "Loeb auto OBD-II diagnostikat ELM327 adapteri kaudu"
    permissions = [Permission.VEHICLE_DATA, Permission.NOTIFICATIONS]
    commands    = ["mootori_pöörded", "jahutustemperatuur", "dtc_koodid", "tühista_vead"]

    async def on_startup(self):
        self._port = os.getenv("OBD_PORT", "")
        self._connected = False
        self._conn = None
        if self._port:
            await self._connect()
        else:
            self.notify("OBD_PORT pole seadistatud — kasutan simulatsiooni", "info")

    async def _connect(self):
        try:
            import obd
            self._conn = await asyncio.to_thread(obd.OBD, self._port)
            self._connected = self._conn.is_connected()
            if self._connected:
                self.notify("OBD-II ühendatud", "success")
        except ImportError:
            self.notify("python-obd pole installitud (pip install obd)", "important")
        except Exception as e:
            self.notify(f"OBD ühendus ebaõnnestus: {e}", "important")

    async def on_voice_command(self, text: str, lang: str) -> str | None:
        t = text.lower()
        if any(kw in t for kw in ["pöörded", "rpm", "обороты"]):
            return await self._query("RPM")
        if any(kw in t for kw in ["temperatuur", "temperature", "температура", "jahutus"]):
            return await self._query("COOLANT_TEMP")
        if any(kw in t for kw in ["dtc", "viga", "ошибка", "error code"]):
            return await self._get_dtc()
        if any(kw in t for kw in ["tühista", "kustuta", "сбросить", "clear"]):
            return await self._clear_dtc()
        return None

    async def _query(self, cmd_name: str) -> str:
        if not self._connected:
            # Simulatsioon arenduseks
            sim = {"RPM": "🔧 RPM: 850 (ralentimine)", "COOLANT_TEMP": "🌡 Jahutus: 87°C (normaalne)"}
            return sim.get(cmd_name, f"🔧 {cmd_name}: — (OBD pole ühendatud)")
        try:
            import obd
            cmd = getattr(obd.commands, cmd_name)
            response = await asyncio.to_thread(self._conn.query, cmd)
            if response.is_null():
                return f"🔧 {cmd_name}: andmeid pole"
            return f"🔧 {cmd_name}: {response.value}"
        except Exception as e:
            return f"🔧 OBD viga: {e}"

    async def _get_dtc(self) -> str:
        if not self._connected:
            return "🔧 DTC: puuduvad veakoodid (simulatsioon)"
        try:
            import obd
            r = await asyncio.to_thread(self._conn.query, obd.commands.GET_DTC)
            if r.is_null() or not r.value:
                return "✅ DTC: veakoode ei leitud"
            codes = ", ".join([f"{c[0]} ({c[1]})" for c in r.value])
            return f"⚠ DTC koodid: {codes}"
        except Exception as e:
            return f"🔧 DTC viga: {e}"

    async def _clear_dtc(self) -> str:
        if not self._connected:
            return "🔧 DTC kustutamine: OBD pole ühendatud"
        try:
            import obd
            await asyncio.to_thread(self._conn.query, obd.commands.CLEAR_DTC)
            return "✅ DTC veakoodid kustutatud"
        except Exception as e:
            return f"🔧 DTC kustutamise viga: {e}"

    async def on_shutdown(self):
        if self._conn:
            try: await asyncio.to_thread(self._conn.close)
            except Exception: pass
