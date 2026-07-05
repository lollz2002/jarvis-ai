"""
JARVIS tööriistad — kõik mida JARVIS võib teha kasutaja loal.
OpenAI function calling kaudu JARVIS ise otsustab milliseid kasutada.
"""
import os
import re
import subprocess
import webbrowser
from datetime import datetime
from core.monitor import record_tool, audit
from memory.memory import (save_fact, get_context_for_prompt, forget_fact,
    save_project, get_projects, save_contact, find_contact, get_all_contacts,
    save_note, search_notes, get_recent_notes, add_project_entry, get_project_entries,
    export_memory, add_knowledge, search_knowledge, add_milestone, get_milestones,
    complete_milestone, update_user_profile, get_user_profile, delete_all_memory,
    search_memory_index)

# ── Tööriistade definitsioonid (OpenAI format) ────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "change_voice_speed",
            "description": "Change how fast JARVIS speaks",
            "parameters": {"type": "object", "properties": {
                "speed": {"type": "number", "description": "Speed: 0.7=slow, 1.0=normal, 1.3=fast"}
            }, "required": ["speed"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "change_voice",
            "description": "Change JARVIS voice ID on ElevenLabs or switch to OpenAI TTS",
            "parameters": {"type": "object", "properties": {
                "voice_id": {"type": "string", "description": "ElevenLabs voice ID or 'onyx'/'alloy'/'nova' for OpenAI"},
                "engine": {"type": "string", "enum": ["openai", "elevenlabs"], "description": "TTS engine to use"}
            }, "required": ["engine"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Open a web search on all connected devices (phone, computer)",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Search query"},
                "engine": {"type": "string", "enum": ["google", "youtube", "maps"], "default": "google"}
            }, "required": ["query"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a URL on all connected devices",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"}
            }, "required": ["url"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Save an important fact about the user to permanent memory. Use for user preferences, personal info, settings.",
            "parameters": {"type": "object", "properties": {
                "key": {"type": "string", "description": "Fact name, e.g. 'user_name', 'user_city', 'car_model'"},
                "value": {"type": "string", "description": "Fact value"}
            }, "required": ["key", "value"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "forget_fact",
            "description": "Delete a fact from memory when user says 'forget this' or 'delete'",
            "parameters": {"type": "object", "properties": {
                "key": {"type": "string", "description": "Fact key to delete"}
            }, "required": ["key"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_project_entry",
            "description": "Add a detailed entry to a project — completed work, pending tasks, parts ordered, diagrams found, maintenance done, wiring notes, supplier info, quotes",
            "parameters": {"type": "object", "properties": {
                "project_name": {"type": "string", "description": "Project name, e.g. 'BMW E46', 'Boat'"},
                "entry_type": {"type": "string", "enum": ["completed", "pending", "part", "diagram", "note", "maintenance", "wiring", "supplier", "quote"], "description": "Type of entry"},
                "content": {"type": "string", "description": "Entry content"}
            }, "required": ["project_name", "entry_type", "content"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "export_memory",
            "description": "Export all memory as JSON — when user asks 'show all memory', 'export memory', 'what do you remember'",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_project",
            "description": "Save or update a project the user is working on. Use for BMW projects, boat, construction, programming etc.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string", "description": "Project name, e.g. 'BMW E46', 'Boat engine', 'Office renovation'"},
                "description": {"type": "string", "description": "What this project is about"},
                "notes": {"type": "string", "description": "Current status, things to do, issues found"},
                "status": {"type": "string", "enum": ["active", "paused", "done"], "description": "Project status"}
            }, "required": ["name"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_contact",
            "description": "Save a contact (person) to memory with their phone number and/or email",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string", "description": "Contact name, e.g. 'Mom', 'Boss', 'Mechanic Jaan'"},
                "phone": {"type": "string", "description": "Phone number"},
                "email": {"type": "string", "description": "Email address"},
                "notes": {"type": "string", "description": "Notes about this person"}
            }, "required": ["name"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": "Save a note or reminder to memory. Use when user says 'remember', 'note', 'write down'",
            "parameters": {"type": "object", "properties": {
                "content": {"type": "string", "description": "Note content"},
                "tags": {"type": "string", "description": "Tags for this note, comma separated, e.g. 'bmw,engine,urgent'"}
            }, "required": ["content"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Search through saved notes, projects, contacts and facts. Use when user asks 'what did I say about X' or 'find note about Y'",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Search query"}
            }, "required": ["query"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_memory",
            "description": "Show user what is stored in memory — projects, contacts, facts, recent notes",
            "parameters": {"type": "object", "properties": {
                "category": {"type": "string", "enum": ["all", "projects", "contacts", "facts", "notes"], "description": "What to show"}
            }, "required": ["category"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "change_primary_ai",
            "description": "Change which AI system JARVIS uses as primary",
            "parameters": {"type": "object", "properties": {
                "agent": {"type": "string", "enum": ["gpt4o", "claude", "gemini", "all"]}
            }, "required": ["agent"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_response_length",
            "description": "Change how long JARVIS responses are",
            "parameters": {"type": "object", "properties": {
                "length": {"type": "string", "enum": ["brief", "normal", "detailed"]}
            }, "required": ["length"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "phone_call",
            "description": "Call someone by phone number or name. Opens phone dialer on the user's mobile device.",
            "parameters": {"type": "object", "properties": {
                "number": {"type": "string", "description": "Phone number to call, e.g. +37212345678"},
                "name": {"type": "string", "description": "Contact name (for display)"}
            }, "required": ["number"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "phone_sms",
            "description": "Send an SMS to a phone number",
            "parameters": {"type": "object", "properties": {
                "number": {"type": "string"},
                "body": {"type": "string", "description": "SMS message text"}
            }, "required": ["number"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "phone_email",
            "description": "Send an email",
            "parameters": {"type": "object", "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string"},
                "body": {"type": "string"}
            }, "required": ["to"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_computer_command",
            "description": "Execute a command on the user's Windows computer. Available commands: find_file, open_file, open_app, search_web, list_files, system_info, screenshot, read_file, create_file, close_app, mouse_click, keyboard_type, keyboard_hotkey, scroll, get_clipboard, set_clipboard",
            "parameters": {"type": "object", "properties": {
                "command": {"type": "string", "enum": ["find_file","open_file","open_app","search_web","list_files","system_info","screenshot","read_file","create_file","close_app","mouse_click","keyboard_type","keyboard_hotkey","scroll","get_clipboard","set_clipboard"]},
                "args": {"type": "object", "description": "Command arguments"}
            }, "required": ["command"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_screen_with_claude",
            "description": "Take a screenshot of the user's work computer screen (or a specific program window) and analyze it with Claude Vision AI. Use this when the user wants to know what's on their work computer screen, extract data from a work program, read documents, check emails, etc.",
            "parameters": {"type": "object", "properties": {
                "question": {"type": "string", "description": "What to analyze or extract from the screen"},
                "window": {"type": "string", "description": "Optional: partial title of the specific program window to capture, e.g. '1C', 'Excel', 'Outlook'. Leave empty for full screen."}
            }, "required": ["question"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_claude_code_on_computer",
            "description": "Run Claude Code CLI on the user's work computer with a prompt. Use for complex tasks that require Claude Code's capabilities.",
            "parameters": {"type": "object", "properties": {
                "prompt": {"type": "string", "description": "The prompt/task for Claude Code"}
            }, "required": ["prompt"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_knowledge",
            "description": "Save reusable information to knowledge base: repair procedures, workflows, manuals, code snippets, checklists",
            "parameters": {"type": "object", "properties": {
                "title":    {"type": "string"},
                "content":  {"type": "string"},
                "category": {"type": "string", "enum": ["repair", "workflow", "manual", "code", "checklist", "general"]},
                "tags":     {"type": "string"},
                "project":  {"type": "string"}
            }, "required": ["title", "content"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Search the knowledge base for reusable information, procedures, manuals",
            "parameters": {"type": "object", "properties": {
                "query":    {"type": "string"},
                "category": {"type": "string"},
                "project":  {"type": "string"}
            }, "required": ["query"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_milestone",
            "description": "Add a milestone or task to a project",
            "parameters": {"type": "object", "properties": {
                "project_name": {"type": "string"},
                "title":        {"type": "string"}
            }, "required": ["project_name", "title"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_milestones",
            "description": "Get pending milestones/tasks for a project",
            "parameters": {"type": "object", "properties": {
                "project_name": {"type": "string"}
            }, "required": ["project_name"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Search across all memories by keyword",
            "parameters": {"type": "object", "properties": {
                "query":   {"type": "string"},
                "project": {"type": "string"}
            }, "required": ["query"]}
        }
    },
]

# ── Käitusaja konfiguratsioon ──────────────────────────────────────────────────
_config = {
    "voice_speed": 0.95,
    "voice_engine": "openai",
    "voice_id": "onyx",
    "primary_agent": "auto",
    "max_tokens": 300,
}

def get_cfg(key, default=None):
    return _config.get(key, default)

# ── Tööriistade täitmine ───────────────────────────────────────────────────────
def execute_tool(name: str, args: dict) -> tuple[str, dict | None]:
    """
    Täidab tööriista. Tagastab (tekst_vastuseks, ws_sõnum_klientidele|None)
    """
    record_tool(name)   # monitoring
    audit("tool_called", {"tool": name, "args_keys": list(args.keys())})
    from core.events import emit_sync, TOOL_EXECUTED
    emit_sync(TOOL_EXECUTED, {"tool": name, "args_keys": list(args.keys())})

    if name == "change_voice_speed":
        _config["voice_speed"] = args.get("speed", 0.95)
        return f"Скорость речи изменена на {args['speed']}, сэр.", None

    elif name == "change_voice":
        engine = args.get("engine", "openai")
        voice_id = args.get("voice_id", "onyx")
        _config["voice_engine"] = engine
        _config["voice_id"] = voice_id
        return f"Голос изменён, сэр. Движок: {engine}, голос: {voice_id}.", None

    elif name == "phone_call":
        number = args.get("number", "")
        contact = args.get("name", number)
        return f"Звоню {contact}, сэр.", {"type": "phone_call", "number": number, "name": contact}

    elif name == "phone_sms":
        number = args.get("number", "")
        body = args.get("body", "")
        return f"Отправляю SMS на {number}, сэр.", {"type": "phone_sms", "number": number, "body": body}

    elif name == "phone_email":
        to = args.get("to", "")
        return f"Открываю почту для {to}, сэр.", {
            "type": "phone_email", "to": to,
            "subject": args.get("subject", ""), "body": args.get("body", "")
        }

    elif name == "search_web":
        query = args.get("query", "")
        engine = args.get("engine", "google")
        urls = {
            "google": f"https://www.google.com/search?q={query.replace(' ', '+')}",
            "youtube": f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}",
            "maps": f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
        }
        url = urls.get(engine, urls["google"])
        return f"Выполняю поиск: {query}", {"type": "browser_open", "url": url}

    elif name == "open_url":
        url = args.get("url", "")
        return f"Открываю {url}, сэр.", {"type": "browser_open", "url": url}

    elif name == "remember_fact":
        save_fact(args["key"], args["value"])
        return f"Запомнил: {args['key']} = {args['value']}, сэр.", None

    elif name == "forget_fact":
        forget_fact(args["key"])
        return f"Удалил из памяти: {args['key']}, сэр.", None

    elif name == "add_project_entry":
        add_project_entry(args["project_name"], args["entry_type"], args["content"])
        return f"Добавлено в проект '{args['project_name']}' [{args['entry_type']}]: {args['content'][:60]}, сэр.", None

    elif name == "export_memory":
        data = export_memory()
        summary = (f"Память: {data['stats'].get('facts',0)} фактов, "
                   f"{data['stats'].get('contacts',0)} контактов, "
                   f"{data['stats'].get('active_projects',0)} проектов, "
                   f"{data['stats'].get('notes',0)} заметок, "
                   f"{data['stats'].get('total_conversations',0)} разговоров.")
        return summary, None

    elif name == "save_project":
        save_project(args["name"], args.get("description",""), args.get("notes",""), args.get("status","active"))
        return f"Проект '{args['name']}' сохранён, сэр.", None

    elif name == "save_contact":
        save_contact(args["name"], args.get("phone",""), args.get("email",""), args.get("notes",""))
        return f"Контакт '{args['name']}' сохранён, сэр.", None

    elif name == "save_note":
        save_note(args["content"], args.get("tags",""))
        return f"Заметка сохранена, сэр: {args['content'][:60]}{'...' if len(args['content'])>60 else ''}", None

    elif name == "search_memory":
        q = args.get("query","")
        notes = search_notes(q)
        contact = find_contact(q)
        projects = [p for p in get_projects() if q.lower() in p["name"].lower() or q.lower() in (p["description"] or "").lower()]
        kbs = search_knowledge(q)
        idx = search_memory_index(q)
        parts = []
        if contact: parts.append(f"Контакт: {contact['name']} тел:{contact['phone']}")
        if projects: parts.append("Проекты: " + ", ".join(p["name"] for p in projects[:3]))
        if notes: parts.append("Заметки: " + " | ".join(n["content"][:80] for n in notes[:3]))
        if kbs: parts.append("Teadmistebaas: " + " | ".join(f"{k['title']}: {k['content'][:60]}" for k in kbs[:2]))
        if idx: parts.append("Indeks: " + " | ".join(f"{i['title']} [{i['category']}]" for i in idx[:3]))
        return "\n".join(parts) if parts else f"По запросу '{q}' ничего не найдено, сэр.", None

    elif name == "add_knowledge":
        add_knowledge(args["title"], args["content"], args.get("category","general"),
                      args.get("tags",""), args.get("project",""))
        return f"Teadmistebaasi lisatud: '{args['title']}' [{args.get('category','general')}], сэр.", None

    elif name == "search_knowledge":
        results = search_knowledge(args["query"], args.get("category"), args.get("project"))
        if not results:
            return f"Teadmistebaasist '{args['query']}' ei leitud, сэр.", None
        return "Leitud: " + " | ".join(f"[{r['category']}] {r['title']}: {r['content'][:80]}" for r in results[:3]), None

    elif name == "add_milestone":
        mid = add_milestone(args["project_name"], args["title"])
        return f"Verstapost lisatud projekti '{args['project_name']}': {args['title']} (#{mid}), сэр.", None

    elif name == "get_milestones":
        ms = get_milestones(args["project_name"])
        if not ms:
            return f"Projektil '{args['project_name']}' pole pooleliolevaid verstaposte, сэр.", None
        return "Verstapostid: " + " | ".join(f"#{m['id']} {m['title']}" for m in ms), None

    elif name == "show_memory":
        cat = args.get("category","all")
        parts = []
        if cat in ("all","facts"):
            from memory.memory import get_all_facts
            facts = get_all_facts()
            if facts: parts.append("Факты: " + ", ".join(f"{k}={v}" for k,v in list(facts.items())[:10]))
        if cat in ("all","contacts"):
            cts = get_all_contacts()
            if cts: parts.append("Контакты: " + ", ".join(c["name"] for c in cts[:10]))
        if cat in ("all","projects"):
            prs = get_projects()
            if prs: parts.append("Проекты: " + ", ".join(p["name"] for p in prs[:10]))
        if cat in ("all","notes"):
            ns = get_recent_notes(5)
            if ns: parts.append("Заметки: " + " | ".join(n["content"][:60] for n in ns))
        return "\n".join(parts) if parts else "Память пуста, сэр.", None

    elif name == "change_primary_ai":
        _config["primary_agent"] = args.get("agent", "auto")
        return f"Основной ИИ изменён на {args['agent']}, сэр.", None

    elif name == "set_response_length":
        lengths = {"brief": 150, "normal": 300, "detailed": 800}
        _config["max_tokens"] = lengths.get(args.get("length", "normal"), 300)
        return f"Длина ответов: {args.get('length')}, сэр.", None

    elif name == "run_computer_command":
        return f"Выполняю команду на компьютере, сэр.", {
            "type": "computer_command",
            "command": args.get("command"),
            "args": args.get("args", {}),
            "request_id": str(datetime.now().timestamp())
        }

    elif name == "analyze_screen_with_claude":
        return f"Анализирую экран компьютера, сэр.", {
            "type": "computer_command",
            "command": "analyze_with_claude",
            "args": {
                "question": args.get("question", "Что на экране?"),
                "window": args.get("window", "")
            },
            "request_id": str(datetime.now().timestamp())
        }

    elif name == "run_claude_code_on_computer":
        return f"Запускаю Claude Code на компьютере, сэр.", {
            "type": "computer_command",
            "command": "run_claude_code",
            "args": {"prompt": args.get("prompt", "")},
            "request_id": str(datetime.now().timestamp())
        }

    return f"Инструмент '{name}' выполнен, сэр.", None
