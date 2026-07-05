"""
JARVIS Arvutijuhtimise Agent
Käivita: python computer_agent.py
Ühendub Railway backendiga ja täidab arvutikäsklusi lokaalselt.
"""
import asyncio
import json
import os
import subprocess
import webbrowser
import websockets
from datetime import datetime

BACKEND_WS = "wss://carefree-gentleness-production-6657.up.railway.app/ws/computer_agent"

COMMANDS = {
    "open_browser": lambda args: webbrowser.open(args.get("url", "https://google.com")),
    "open_app": lambda args: subprocess.Popen(args.get("app", "")),
    "search_google": lambda args: webbrowser.open(f"https://www.google.com/search?q={args.get('query','')}"),
    "open_youtube": lambda args: webbrowser.open(f"https://www.youtube.com/results?search_query={args.get('query','')}"),
    "open_file": lambda args: os.startfile(args.get("path", "")),
    "get_time": lambda args: datetime.now().strftime("%H:%M, %d.%m.%Y"),
    "list_files": lambda args: os.listdir(args.get("path", os.path.expanduser("~\\Desktop"))),
    "run_cmd": lambda args: subprocess.check_output(args.get("cmd", ""), shell=True, text=True, timeout=10),
}

async def handle_command(data: dict) -> str:
    cmd = data.get("command")
    args = data.get("args", {})
    if cmd in COMMANDS:
        try:
            result = COMMANDS[cmd](args)
            return str(result) if result else "Выполнено, сэр."
        except Exception as e:
            return f"Ошибка: {e}"
    return f"Команда '{cmd}' неизвестна, сэр."

async def run():
    print(f"JARVIS Arvutijuhtimise Agent käivitub...")
    print(f"Ühendub: {BACKEND_WS}")
    while True:
        try:
            async with websockets.connect(BACKEND_WS) as ws:
                print("✓ Ühendatud JARVIS backendiga")
                # Teata et oleme arvutijuhtimise agent
                await ws.send(json.dumps({
                    "type": "register",
                    "role": "computer_agent",
                    "capabilities": list(COMMANDS.keys())
                }))
                async for message in ws:
                    data = json.loads(message)
                    if data.get("type") == "computer_command":
                        print(f"Käsklus: {data.get('command')} {data.get('args', {})}")
                        result = await handle_command(data)
                        await ws.send(json.dumps({
                            "type": "computer_result",
                            "result": result,
                            "request_id": data.get("request_id")
                        }))
        except Exception as e:
            print(f"Ühendus katkes: {e} — uuesti 5s pärast...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run())
