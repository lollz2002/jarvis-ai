"""
JARVIS Windows Agent — täielik arvutijuhtimine + kaugjuhtimine
Käivita: python agent.py
"""
import asyncio
import json
import os
import glob
import subprocess
import webbrowser
import platform
import base64
import time
import psutil
import websockets
from datetime import datetime
from pathlib import Path
from io import BytesIO

BACKEND_WS = "wss://carefree-gentleness-production-6657.up.railway.app/ws/windows_agent"
HOME = Path.home()

# Claude API otse Windows agendist
CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
if not CLAUDE_API_KEY:
    import sys
    print("✗ ANTHROPIC_API_KEY puudub — seadke keskkonnamuutuja enne käivitamist.")
    sys.exit(1)
_streaming = False
_stream_quality = 50   # JPEG kvaliteet (madalam = kiirem)
_stream_interval = 0.5 # sekundeid kaadrite vahel

# ── Ekraanivoogedastus ─────────────────────────────────────────────────────────

def capture_screen_bytes(quality=50, scale=0.5) -> bytes:
    try:
        import mss
        from PIL import Image
        with mss.mss() as sct:
            mon = sct.monitors[1]
            img = sct.grab(mon)
            pil = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            w = int(pil.width * scale)
            h = int(pil.height * scale)
            pil = pil.resize((w, h), Image.LANCZOS)
            buf = BytesIO()
            pil.save(buf, format="JPEG", quality=quality, optimize=True)
            return buf.getvalue()
    except ImportError:
        from PIL import ImageGrab, Image
        img = ImageGrab.grab()
        w = int(img.width * scale)
        h = int(img.height * scale)
        img = img.resize((w, h), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()

async def stream_screen(ws):
    global _streaming
    print("📺 Ekraanivoogedastus alustatud")
    while _streaming:
        try:
            frame = capture_screen_bytes(_stream_quality)
            b64 = base64.b64encode(frame).decode()
            await ws.send(json.dumps({
                "type": "screen_frame",
                "frame": b64,
                "ts": time.time()
            }))
        except Exception as e:
            print(f"Voogedastuse viga: {e}")
        await asyncio.sleep(_stream_interval)
    print("📺 Ekraanivoogedastus peatatud")

# ── Hiirejuhtimine ─────────────────────────────────────────────────────────────

def get_pyautogui():
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        return pyautogui
    except ImportError:
        return None

async def mouse_click(args):
    pg = get_pyautogui()
    if not pg: return "pyautogui pole installitud"
    x, y = args.get("x", 0), args.get("y", 0)
    # Tõlgi suhtelised koordinaadid absoluutseteks
    if args.get("relative"):
        import mss
        with mss.mss() as sct:
            mon = sct.monitors[1]
            x = int(x * mon["width"])
            y = int(y * mon["height"])
    btn = args.get("button", "left")
    double = args.get("double", False)
    if double:
        pg.doubleClick(x, y)
    else:
        pg.click(x, y, button=btn)
    return f"Klikitud ({x}, {y})"

async def mouse_move(args):
    pg = get_pyautogui()
    if not pg: return "pyautogui pole installitud"
    x, y = args.get("x", 0), args.get("y", 0)
    if args.get("relative"):
        import mss
        with mss.mss() as sct:
            mon = sct.monitors[1]
            x = int(x * mon["width"])
            y = int(y * mon["height"])
    pg.moveTo(x, y, duration=0.1)
    return "Hiir liigutatud"

async def keyboard_type(args):
    pg = get_pyautogui()
    if not pg: return "pyautogui pole installitud"
    text = args.get("text", "")
    pg.typewrite(text, interval=0.05)
    return f"Trükitud: {text}"

async def keyboard_hotkey(args):
    pg = get_pyautogui()
    if not pg: return "pyautogui pole installitud"
    keys = args.get("keys", [])
    pg.hotkey(*keys)
    return f"Klahvikombinatsioon: {'+'.join(keys)}"

async def scroll(args):
    pg = get_pyautogui()
    if not pg: return "pyautogui pole installitud"
    amount = args.get("amount", 3)
    direction = args.get("direction", "down")
    pg.scroll(-amount if direction == "down" else amount)
    return f"Keritatud {direction}"

# ── Failid ja süsteem ──────────────────────────────────────────────────────────

async def find_file(args):
    name = args.get("name", "")
    search_path = args.get("path", str(HOME))
    results = []
    skip = {'Windows', 'Program Files', 'Program Files (x86)', '$Recycle.Bin',
            'AppData', '__pycache__', 'node_modules', '.git'}
    try:
        for root, dirs, files in os.walk(search_path):
            dirs[:] = [d for d in dirs if d not in skip and not d.startswith('.')]
            for f in files:
                if name.lower() in f.lower():
                    results.append(os.path.join(root, f))
                    if len(results) >= 15:
                        break
            if len(results) >= 15:
                break
    except Exception:
        pass
    return "\n".join(results) if results else f"Файл '{name}' не найден."

async def open_file(args):
    path = args.get("path", "")
    if os.path.exists(path):
        os.startfile(path)
        return f"Открываю {path}, сэр."
    return f"Файл не найден: {path}"

async def open_app(args):
    app = args.get("app", "")
    apps = {
        "chrome": "chrome", "firefox": "firefox", "notepad": "notepad",
        "explorer": "explorer", "calculator": "calc", "paint": "mspaint",
        "word": "winword", "excel": "excel", "terminal": "cmd",
        "powershell": "powershell", "steam": r"C:\Program Files (x86)\Steam\steam.exe",
        "spotify": str(HOME / "AppData/Roaming/Spotify/Spotify.exe"),
        "task manager": "taskmgr", "settings": "ms-settings:",
    }
    target = apps.get(app.lower(), app)
    try:
        subprocess.Popen(target, shell=True)
        return f"Открываю {app}, сэр."
    except Exception as e:
        return f"Не удалось открыть {app}: {e}"

async def search_web(args):
    query = args.get("query", "")
    engine = args.get("engine", "google")
    urls = {
        "google": f"https://www.google.com/search?q={query.replace(' ', '+')}",
        "youtube": f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}",
        "maps": f"https://www.google.com/maps/search/{query.replace(' ', '+')}",
        "images": f"https://www.google.com/search?tbm=isch&q={query.replace(' ', '+')}",
    }
    webbrowser.open(urls.get(engine, urls["google"]))
    return f"Ищу '{query}' в {engine}, сэр."

async def list_files(args):
    path = args.get("path", str(HOME / "Desktop"))
    try:
        items = os.listdir(path)
        files = [f for f in items if os.path.isfile(os.path.join(path, f))]
        dirs = [d + "/" for d in items if os.path.isdir(os.path.join(path, d))]
        return f"Папки: {', '.join(dirs[:8])}\nФайлы: {', '.join(files[:15])}"
    except Exception as e:
        return f"Ошибка: {e}"

async def get_system_info(args):
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('C:\\')
    battery = psutil.sensors_battery()
    bat = f", Батарея: {battery.percent:.0f}%" if battery else ""
    return (f"CPU: {cpu}% | RAM: {ram.percent}% ({ram.used//1024//1024}MB/{ram.total//1024//1024}MB) | "
            f"C: {disk.free//1024**3}GB свободно{bat}")

async def take_screenshot(args):
    try:
        frame = capture_screen_bytes(quality=85, scale=1.0)
        path = str(HOME / "Desktop" / f"jarvis_{datetime.now().strftime('%H%M%S')}.jpg")
        with open(path, 'wb') as f:
            f.write(frame)
        return f"Скриншот сохранён: {path}"
    except Exception as e:
        return f"Ошибка: {e}"

async def read_file_content(args):
    path = args.get("path", "")
    if not os.path.exists(path):
        return f"Файл не найден: {path}"
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read(3000)
    except Exception as e:
        return f"Ошибка: {e}"

async def create_file(args):
    path = args.get("path", "")
    content = args.get("content", "")
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Файл создан: {path}"
    except Exception as e:
        return f"Ошибка: {e}"

async def capture_window(args):
    """Pildistab konkreetse akna pealkirja järgi."""
    title = args.get("title", "")
    import ctypes
    try:
        import win32gui, win32ui, win32con
        from PIL import Image as PILImage

        def find_window(partial_title):
            result = []
            def cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    t = win32gui.GetWindowText(hwnd)
                    if partial_title.lower() in t.lower():
                        result.append(hwnd)
            win32gui.EnumWindows(cb, None)
            return result[0] if result else None

        hwnd = find_window(title) if title else None
        if hwnd:
            win32gui.SetForegroundWindow(hwnd)
            await asyncio.sleep(0.3)
            rect = win32gui.GetWindowRect(hwnd)
            x, y, x2, y2 = rect
            width, height = x2 - x, y2 - y
        else:
            import mss
            with mss.mss() as sct:
                mon = sct.monitors[1]
                x, y, width, height = 0, 0, mon["width"], mon["height"]

        # Pildista ala
        import mss
        with mss.mss() as sct:
            region = {"top": max(0,y), "left": max(0,x), "width": width, "height": height}
            img = sct.grab(region)
            from PIL import Image
            pil = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            buf = BytesIO()
            pil.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        # Fallback: täisekraan
        frame = capture_screen_bytes(quality=85, scale=1.0)
        return base64.b64encode(frame).decode() if isinstance(frame, bytes) else frame

async def analyze_with_claude(args):
    """Pildistab ekraani/akna ja saadab Claudele analüüsiks."""
    question = args.get("question", "Что изображено на экране? Дай краткий отчёт.")
    window_title = args.get("window", "")

    print(f"→ Pildistan {'akent: ' + window_title if window_title else 'ekraani'}...")

    # Pildista
    img_b64 = await capture_window({"title": window_title})

    # Saada Claudele
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": CLAUDE_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 500,
                    "system": "Ты JARVIS. Анализируй экран кратко и по делу. Отвечай на русском, максимум 3 предложения.",
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                            {"type": "text", "text": question}
                        ]
                    }]
                }
            )
            if resp.status_code == 200:
                return resp.json()["content"][0]["text"]
            return f"Claude API вернул {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return f"Ошибка анализа: {e}"

async def run_claude_code(args):
    """Käivitab Claude Code CLI käskluse ja tagastab vastuse."""
    prompt = args.get("prompt", "")
    if not prompt:
        return "Промпт не указан, сэр."
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=60, cwd=str(HOME)
        )
        output = result.stdout.strip() or result.stderr.strip()
        return output[:2000] if output else "Claude Code не вернул результат."
    except FileNotFoundError:
        return "Claude Code CLI не установлен. Установите: npm install -g @anthropic-ai/claude-code"
    except Exception as e:
        return f"Ошибка: {e}"

async def get_clipboard(args):
    """Loeb lõikepuhu sisu."""
    try:
        import pyperclip
        return pyperclip.paste() or "Lõikepuhver on tühi."
    except Exception:
        result = subprocess.run("powershell Get-Clipboard", capture_output=True, text=True, shell=True)
        return result.stdout.strip() or "Lõikepuhver on tühi."

async def set_clipboard(args):
    """Kirjutab teksti lõikepuhvrisse."""
    text = args.get("text", "")
    try:
        import pyperclip
        pyperclip.copy(text)
    except Exception:
        subprocess.run(f'powershell Set-Clipboard -Value "{text}"', shell=True)
    return f"Lõikepuhvrisse kopeeritud: {text[:50]}"

async def close_app(args):
    name = args.get("name", "")
    killed = []
    for proc in psutil.process_iter(['name', 'pid']):
        if name.lower() in proc.info['name'].lower():
            try:
                proc.kill()
                killed.append(proc.info['name'])
            except Exception:
                pass
    return f"Закрыто: {', '.join(killed)}" if killed else f"'{name}' не найден."

async def run_command(args):
    cmd = args.get("cmd", "")
    safe_prefixes = ["dir", "echo", "ipconfig", "ping", "tasklist", "where", "type",
                     "python --version", "node --version", "git log"]
    if not any(cmd.startswith(s) for s in safe_prefixes):
        return "Команда не в белом списке, сэр."
    try:
        return subprocess.check_output(cmd, shell=True, text=True, timeout=10,
                                       stderr=subprocess.STDOUT)[:1000]
    except Exception as e:
        return str(e)

# ── Käskluste kaart ────────────────────────────────────────────────────────────
COMMANDS = {
    "find_file": find_file, "open_file": open_file, "open_app": open_app,
    "search_web": search_web, "list_files": list_files, "system_info": get_system_info,
    "screenshot": take_screenshot, "read_file": read_file_content,
    "create_file": create_file, "close_app": close_app, "run_command": run_command,
    "mouse_click": mouse_click, "mouse_move": mouse_move,
    "keyboard_type": keyboard_type, "keyboard_hotkey": keyboard_hotkey,
    "scroll": scroll,
    "analyze_with_claude": analyze_with_claude,
    "run_claude_code": run_claude_code,
    "get_clipboard": get_clipboard, "set_clipboard": set_clipboard,
}

async def handle(data: dict) -> str:
    cmd = data.get("command", "")
    args = data.get("args", {})
    fn = COMMANDS.get(cmd)
    if fn:
        try:
            return await fn(args)
        except Exception as e:
            return f"Ошибка: {e}"
    return f"Неизвестная команда: {cmd}"

# ── Peaagent ───────────────────────────────────────────────────────────────────
async def run():
    global _streaming
    print("=" * 50)
    print("  JARVIS Windows Agent v2")
    print(f"  Arvuti: {platform.node()}")
    print(f"  Ühendub: Railway pilvega...")
    print("=" * 50)

    # Installi vajalikud paketid
    for pkg in ["mss", "Pillow", "pyautogui"]:
        subprocess.run(f'pip install {pkg} --quiet', shell=True)

    stream_task = None

    while True:
        try:
            async with websockets.connect(BACKEND_WS, ping_interval=20, ping_timeout=10) as ws:
                print("✓ Ühendatud! JARVIS saab arvutit juhtida.")
                await ws.send(json.dumps({
                    "type": "register", "role": "windows_agent",
                    "computer": platform.node(),
                    "capabilities": list(COMMANDS.keys()) + ["screen_stream"]
                }))

                async for message in ws:
                    try:
                        data = json.loads(message)
                        msg_type = data.get("type")

                        if msg_type == "computer_command":
                            cmd = data.get("command")
                            print(f"→ {cmd} {data.get('args', {})}")

                            # Ekraanivoogedastus
                            if cmd == "start_stream":
                                _streaming = True
                                stream_task = asyncio.create_task(stream_screen(ws))
                                await ws.send(json.dumps({"type": "computer_result",
                                    "result": "Ekraanivoogedastus alustatud, сэр.",
                                    "request_id": data.get("request_id")}))
                                continue
                            elif cmd == "stop_stream":
                                _streaming = False
                                await ws.send(json.dumps({"type": "computer_result",
                                    "result": "Voogedastus peatatud.",
                                    "request_id": data.get("request_id")}))
                                continue

                            result = await handle(data)
                            print(f"← {result[:80]}")
                            await ws.send(json.dumps({
                                "type": "computer_result",
                                "result": result,
                                "request_id": data.get("request_id")
                            }))

                        elif msg_type == "ping":
                            await ws.send(json.dumps({"type": "pong"}))

                    except Exception as e:
                        print(f"Sõnumi viga: {e}")

        except Exception as e:
            _streaming = False
            print(f"✗ Ühendus katkes: {e} — uuesti 5s...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run())
