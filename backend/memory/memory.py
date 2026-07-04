"""
Albert OS — Memory Engine v3
Spek: 11_DATABASE_AND_MEMORY_SCHEMA.md

Tabelid:
  facts, projects, project_entries, contacts, notes,
  vehicles, documents, conversations,
  user_profile, knowledge, memory_index, milestones

Retrieval pipeline:
  intent → project detect → project memory → global knowledge → rank → inject
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "albert_os.db"


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")  # concurrent reads
    return c


def _init():
    with _conn() as c:
        c.executescript("""
        -- ── Faktid (lühimälu) ─────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS facts (
            key        TEXT PRIMARY KEY,
            value      TEXT,
            updated_at TEXT
        );

        -- ── Kasutajaprofiil ────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS user_profile (
            id          INTEGER PRIMARY KEY CHECK(id = 1),
            language    TEXT DEFAULT 'ru',
            timezone    TEXT DEFAULT 'Europe/Tallinn',
            devices     TEXT DEFAULT '[]',
            permissions TEXT DEFAULT '{}',
            ai_settings TEXT DEFAULT '{}',
            updated_at  TEXT
        );
        INSERT OR IGNORE INTO user_profile (id, updated_at) VALUES (1, datetime('now'));

        -- ── Projektid ──────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS projects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE,
            description TEXT DEFAULT '',
            status      TEXT DEFAULT 'active',
            notes       TEXT DEFAULT '',
            updated_at  TEXT
        );

        -- ── Projekti kirjed ────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS project_entries (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            entry_type   TEXT,
            content      TEXT,
            created_at   TEXT
        );

        -- ── Verstapostid ───────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS milestones (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            title        TEXT,
            done         INTEGER DEFAULT 0,
            created_at   TEXT,
            done_at      TEXT
        );

        -- ── Kontaktid ──────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS contacts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT,
            phone      TEXT DEFAULT '',
            email      TEXT DEFAULT '',
            notes      TEXT DEFAULT '',
            updated_at TEXT
        );

        -- ── Märkmed ───────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            content    TEXT,
            tags       TEXT DEFAULT '',
            project    TEXT DEFAULT '',
            importance INTEGER DEFAULT 0,
            created_at TEXT
        );

        -- ── Vestlused ─────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS conversations (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            device           TEXT,
            prompt           TEXT,
            response         TEXT,
            language         TEXT DEFAULT 'ru',
            summary          TEXT DEFAULT '',
            related_project  TEXT DEFAULT '',
            ai_provider      TEXT DEFAULT '',
            ts               TEXT
        );

        -- ── Teadmistebaas ─────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS knowledge (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT,
            content    TEXT,
            category   TEXT DEFAULT 'general',
            tags       TEXT DEFAULT '',
            project    TEXT DEFAULT '',
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_knowledge_cat ON knowledge(category);
        CREATE INDEX IF NOT EXISTS idx_knowledge_proj ON knowledge(project);

        -- ── Mäluindeks ────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS memory_index (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            title               TEXT,
            category            TEXT,
            project             TEXT DEFAULT '',
            tags                TEXT DEFAULT '',
            importance_score    REAL DEFAULT 0.5,
            source_table        TEXT,
            source_id           INTEGER,
            embedding_reference TEXT DEFAULT '',
            created_at          TEXT,
            updated_at          TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_memidx_proj ON memory_index(project);
        CREATE INDEX IF NOT EXISTS idx_memidx_cat  ON memory_index(category);

        -- ── Sõidukid ──────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS vehicles (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT UNIQUE,
            type       TEXT DEFAULT 'car',
            make       TEXT DEFAULT '',
            model      TEXT DEFAULT '',
            year       TEXT DEFAULT '',
            vin        TEXT DEFAULT '',
            notes      TEXT DEFAULT '',
            updated_at TEXT
        );

        -- ── Dokumendid ────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS documents (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT,
            content    TEXT,
            category   TEXT DEFAULT 'general',
            tags       TEXT DEFAULT '',
            created_at TEXT
        );
        """)

_init()

# ── Kasutajaprofiil ───────────────────────────────────────────────────────────
def get_user_profile() -> dict:
    with _conn() as c:
        r = c.execute("SELECT * FROM user_profile WHERE id=1").fetchone()
        if not r: return {}
        d = dict(r)
        d["devices"]     = json.loads(d.get("devices", "[]") or "[]")
        d["permissions"] = json.loads(d.get("permissions", "{}") or "{}")
        d["ai_settings"] = json.loads(d.get("ai_settings", "{}") or "{}")
        return d

def update_user_profile(**kwargs):
    profile = get_user_profile()
    for key, val in kwargs.items():
        if key in ("devices", "permissions", "ai_settings"):
            profile[key] = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)
        else:
            profile[key] = val
    with _conn() as c:
        c.execute("""UPDATE user_profile SET
            language=?, timezone=?, devices=?, permissions=?, ai_settings=?, updated_at=?
            WHERE id=1""",
            (profile.get("language", "ru"), profile.get("timezone", "Europe/Tallinn"),
             profile.get("devices", "[]") if isinstance(profile.get("devices"), str) else json.dumps(profile.get("devices", [])),
             profile.get("permissions", "{}") if isinstance(profile.get("permissions"), str) else json.dumps(profile.get("permissions", {})),
             profile.get("ai_settings", "{}") if isinstance(profile.get("ai_settings"), str) else json.dumps(profile.get("ai_settings", {})),
             datetime.now().isoformat()))

# ── Faktid ────────────────────────────────────────────────────────────────────
def save_fact(key: str, value: str):
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO facts VALUES (?,?,?)",
                  (key, value, datetime.now().isoformat()))
    _index_memory(key, "fact", importance=0.6)

def get_fact(key: str) -> str | None:
    with _conn() as c:
        r = c.execute("SELECT value FROM facts WHERE key=?", (key,)).fetchone()
        return r["value"] if r else None

def get_all_facts() -> dict:
    with _conn() as c:
        return {r["key"]: r["value"] for r in c.execute("SELECT key,value FROM facts").fetchall()}

def forget_fact(key: str):
    with _conn() as c:
        c.execute("DELETE FROM facts WHERE key=?", (key,))
        c.execute("DELETE FROM memory_index WHERE source_table='facts' AND title=?", (key,))

# ── Projektid ─────────────────────────────────────────────────────────────────
def save_project(name: str, description: str = "", notes: str = "", status: str = "active"):
    with _conn() as c:
        c.execute("""INSERT INTO projects (name,description,status,notes,updated_at)
                     VALUES (?,?,?,?,?)
                     ON CONFLICT(name) DO UPDATE SET
                       description=excluded.description, status=excluded.status,
                       notes=excluded.notes, updated_at=excluded.updated_at""",
                  (name, description, status, notes, datetime.now().isoformat()))
    _index_memory(name, "project", project=name, importance=0.9)

def get_projects(status: str = "active") -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM projects WHERE status=? ORDER BY updated_at DESC", (status,)).fetchall()]

# ── Projekti kirjed ───────────────────────────────────────────────────────────
def add_project_entry(project_name: str, entry_type: str, content: str):
    """entry_type: completed|pending|part|diagram|note|maintenance|wiring|supplier|quote|task|milestone"""
    with _conn() as c:
        c.execute("INSERT INTO project_entries (project_name,entry_type,content,created_at) VALUES (?,?,?,?)",
                  (project_name, entry_type, content, datetime.now().isoformat()))
    _index_memory(content[:60], "project_entry", project=project_name,
                  importance=0.8 if entry_type in ("maintenance", "wiring", "part") else 0.5)

def get_project_entries(project_name: str, entry_type: str = None) -> list:
    with _conn() as c:
        if entry_type:
            rows = c.execute("""SELECT * FROM project_entries
                WHERE project_name=? AND entry_type=? ORDER BY created_at DESC""",
                (project_name, entry_type)).fetchall()
        else:
            rows = c.execute("""SELECT * FROM project_entries
                WHERE project_name=? ORDER BY created_at DESC LIMIT 20""",
                (project_name,)).fetchall()
        return [dict(r) for r in rows]

# ── Verstapostid ──────────────────────────────────────────────────────────────
def add_milestone(project_name: str, title: str) -> int:
    with _conn() as c:
        cur = c.execute("INSERT INTO milestones (project_name,title,created_at) VALUES (?,?,?)",
                        (project_name, title, datetime.now().isoformat()))
        return cur.lastrowid

def complete_milestone(milestone_id: int):
    with _conn() as c:
        c.execute("UPDATE milestones SET done=1, done_at=? WHERE id=?",
                  (datetime.now().isoformat(), milestone_id))

def get_milestones(project_name: str, include_done: bool = False) -> list:
    with _conn() as c:
        if include_done:
            rows = c.execute("SELECT * FROM milestones WHERE project_name=? ORDER BY created_at",
                             (project_name,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM milestones WHERE project_name=? AND done=0 ORDER BY created_at",
                             (project_name,)).fetchall()
        return [dict(r) for r in rows]

# ── Teadmistebaas ─────────────────────────────────────────────────────────────
KNOWLEDGE_CATEGORIES = ["repair", "workflow", "manual", "code", "checklist", "general"]

def add_knowledge(title: str, content: str, category: str = "general",
                  tags: str = "", project: str = "") -> int:
    if category not in KNOWLEDGE_CATEGORIES:
        category = "general"
    with _conn() as c:
        cur = c.execute("""INSERT INTO knowledge (title,content,category,tags,project,created_at)
                           VALUES (?,?,?,?,?,?)""",
                        (title, content, category, tags, project, datetime.now().isoformat()))
        kid = cur.lastrowid
    _index_memory(title, f"knowledge:{category}", project=project, importance=0.85)
    return kid

def search_knowledge(query: str, category: str = None, project: str = None) -> list:
    with _conn() as c:
        base = "SELECT * FROM knowledge WHERE (title LIKE ? OR content LIKE ? OR tags LIKE ?)"
        params = [f"%{query}%"] * 3
        if category:
            base += " AND category=?"
            params.append(category)
        if project:
            base += " AND (project=? OR project='')"
            params.append(project)
        base += " ORDER BY created_at DESC LIMIT 8"
        return [dict(r) for r in c.execute(base, params).fetchall()]

def get_knowledge_by_category(category: str, project: str = None) -> list:
    with _conn() as c:
        if project:
            rows = c.execute("SELECT * FROM knowledge WHERE category=? AND (project=? OR project='') ORDER BY created_at DESC LIMIT 10",
                             (category, project)).fetchall()
        else:
            rows = c.execute("SELECT * FROM knowledge WHERE category=? ORDER BY created_at DESC LIMIT 10",
                             (category,)).fetchall()
        return [dict(r) for r in rows]

# ── Mäluindeks ────────────────────────────────────────────────────────────────
def _index_memory(title: str, category: str, project: str = "", importance: float = 0.5,
                  source_table: str = "", source_id: int = 0):
    """Registreerib mälukande indeksisse — automaatne."""
    now = datetime.now().isoformat()
    with _conn() as c:
        c.execute("""INSERT INTO memory_index
            (title,category,project,importance_score,source_table,source_id,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (title[:120], category, project, importance, source_table, source_id, now, now))

def search_memory_index(query: str, project: str = None, min_importance: float = 0.0) -> list:
    with _conn() as c:
        base = "SELECT * FROM memory_index WHERE (title LIKE ? OR category LIKE ?)"
        params = [f"%{query}%", f"%{query}%"]
        if project:
            base += " AND (project=? OR project='')"
            params.append(project)
        if min_importance > 0:
            base += " AND importance_score >= ?"
            params.append(min_importance)
        base += " ORDER BY importance_score DESC, updated_at DESC LIMIT 15"
        return [dict(r) for r in c.execute(base, params).fetchall()]

# ── Kontaktid ─────────────────────────────────────────────────────────────────
def save_contact(name: str, phone: str = "", email: str = "", notes: str = ""):
    with _conn() as c:
        existing = c.execute("SELECT id FROM contacts WHERE name LIKE ?", (name,)).fetchone()
        if existing:
            c.execute("UPDATE contacts SET phone=?,email=?,notes=?,updated_at=? WHERE id=?",
                      (phone, email, notes, datetime.now().isoformat(), existing["id"]))
        else:
            c.execute("INSERT INTO contacts (name,phone,email,notes,updated_at) VALUES (?,?,?,?,?)",
                      (name, phone, email, notes, datetime.now().isoformat()))

def find_contact(query: str) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM contacts WHERE name LIKE ? ORDER BY updated_at DESC LIMIT 1",
                      (f"%{query}%",)).fetchone()
        return dict(r) if r else None

def get_all_contacts() -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM contacts ORDER BY name").fetchall()]

# ── Märkmed ───────────────────────────────────────────────────────────────────
def save_note(content: str, tags: str = "", project: str = "", importance: int = 0):
    with _conn() as c:
        c.execute("INSERT INTO notes (content,tags,project,importance,created_at) VALUES (?,?,?,?,?)",
                  (content, tags, project, importance, datetime.now().isoformat()))
    _index_memory(content[:80], "note", project=project, importance=0.4 + importance * 0.2)

def search_notes(query: str, project: str = None) -> list:
    with _conn() as c:
        base = "SELECT * FROM notes WHERE (content LIKE ? OR tags LIKE ?)"
        params = [f"%{query}%", f"%{query}%"]
        if project:
            base += " AND project=?"
            params.append(project)
        base += " ORDER BY importance DESC, created_at DESC LIMIT 10"
        return [dict(r) for r in c.execute(base, params).fetchall()]

def get_recent_notes(n: int = 5) -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM notes ORDER BY created_at DESC LIMIT ?", (n,)).fetchall()]

# ── Vestlused ─────────────────────────────────────────────────────────────────
def save_interaction(device: str, prompt: str, results: list,
                     language: str = "ru", related_project: str = "", ai_provider: str = ""):
    response = results[0].get("response", "") if results else ""
    provider = ai_provider or (results[0].get("id", "") if results else "")
    with _conn() as c:
        c.execute("""INSERT INTO conversations
            (device,prompt,response,language,related_project,ai_provider,ts)
            VALUES (?,?,?,?,?,?,?)""",
            (device, prompt[:500], response[:500], language, related_project, provider,
             datetime.now().isoformat()))
        # Retention: hoia 2000 viimast
        c.execute("DELETE FROM conversations WHERE id NOT IN "
                  "(SELECT id FROM conversations ORDER BY id DESC LIMIT 2000)")
        # Vana auto-summarize: >100 kirjet → kokkuvõte faktidesse
        count = c.execute("SELECT COUNT(*) as n FROM conversations").fetchone()["n"]
        if count > 100 and count % 50 == 0:
            _summarize_old_conversations(c)

def _summarize_old_conversations(c):
    """Koondab vanad vestlused kokku faktidena (lihtne heuristika; asenda LLM-iga tulevikus)."""
    old = c.execute("""SELECT prompt, response FROM conversations
        ORDER BY id ASC LIMIT 50""").fetchall()
    topics = {}
    for row in old:
        words = (row["prompt"] or "").lower().split()
        for w in words:
            if len(w) > 4:
                topics[w] = topics.get(w, 0) + 1
    top = sorted(topics.items(), key=lambda x: -x[1])[:5]
    summary = "Varasemad teemad: " + ", ".join(t[0] for t in top)
    c.execute("INSERT OR REPLACE INTO facts VALUES (?,?,?)",
              ("auto_summary", summary, datetime.now().isoformat()))

def get_recent(n: int = 20) -> list:
    with _conn() as c:
        rows = c.execute("SELECT * FROM conversations ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        return [dict(r) for r in reversed(rows)]

def get_stats() -> dict:
    with _conn() as c:
        return {
            "total_conversations": c.execute("SELECT COUNT(*) as n FROM conversations").fetchone()["n"],
            "facts": c.execute("SELECT COUNT(*) as n FROM facts").fetchone()["n"],
            "contacts": c.execute("SELECT COUNT(*) as n FROM contacts").fetchone()["n"],
            "active_projects": c.execute("SELECT COUNT(*) as n FROM projects WHERE status='active'").fetchone()["n"],
            "notes": c.execute("SELECT COUNT(*) as n FROM notes").fetchone()["n"],
            "knowledge": c.execute("SELECT COUNT(*) as n FROM knowledge").fetchone()["n"],
            "memory_index": c.execute("SELECT COUNT(*) as n FROM memory_index").fetchone()["n"],
        }

# ── Projekti tuvastus ─────────────────────────────────────────────────────────
def detect_active_project(prompt: str) -> str | None:
    with _conn() as c:
        projects = [dict(r) for r in c.execute("SELECT name FROM projects WHERE status='active'").fetchall()]
    p = prompt.lower()
    for proj in projects:
        if proj["name"].lower() in p:
            return proj["name"]
    keywords = {
        "BMW":  ["bmw", "бмв", "mootor", "двигатель", "obd", "e46", "e90", "f10", "n46", "m47"],
        "Boat": ["boat", "paat", "лодк", "marine", "wiring", "yamaha", "volvo penta", "nmea"],
    }
    for name, kws in keywords.items():
        if any(kw in p for kw in kws):
            with _conn() as c:
                proj_exists = c.execute("SELECT name FROM projects WHERE name LIKE ?", (f"%{name}%",)).fetchone()
                if proj_exists: return proj_exists["name"]
    return None

# ── Retrieval Pipeline ────────────────────────────────────────────────────────
def get_context_for_prompt(prompt: str = "") -> str:
    """
    Pipeline: intent detect → project → knowledge → facts → contacts → notes → recent
    Ranked by importance, truncated to fit prompt window.
    """
    parts = []
    active_project = detect_active_project(prompt) if prompt else None

    # 1. Faktid
    facts = get_all_facts()
    if facts:
        parts.append("ИЗВЕСТНЫЕ ФАКТЫ:")
        for k, v in list(facts.items())[:15]:
            parts.append(f"  {k}: {v}")

    # 2. Kontaktid
    contacts = get_all_contacts()
    if contacts:
        parts.append("\nКОНТАКТЫ:")
        for ct in contacts[:20]:
            line = f"  {ct['name']}"
            if ct['phone']: line += f" тел:{ct['phone']}"
            if ct['email']: line += f" email:{ct['email']}"
            parts.append(line)

    # 3. Aktiivsed projektid
    projects = get_projects("active")
    if projects:
        parts.append("\nАКТИВНЫЕ ПРОЕКТЫ:")
        for p in projects[:8]:
            line = f"  [{p['name']}] {p['description']}"
            if p['notes']: line += f" | {p['notes'][:80]}"
            parts.append(line)

    # 4. Aktiivse projekti detailid (kõrgeim prioriteet)
    if active_project:
        entries = get_project_entries(active_project)
        if entries:
            parts.append(f"\nАКТИВНЫЙ ПРОЕКТ — {active_project}:")
            for e in entries[:10]:
                parts.append(f"  [{e['entry_type']}] {e['content'][:120]}")
        # Verstapostid
        milestones = get_milestones(active_project)
        if milestones:
            parts.append(f"  VERSTAPOSTID ({active_project}):")
            for m in milestones[:5]:
                parts.append(f"    ○ {m['title']}")
        # Teadmistebaas projekti kohta
        kbs = search_knowledge(prompt[:60] if prompt else active_project,
                               project=active_project)
        if kbs:
            parts.append(f"  TEADMISTEBAAS ({active_project}):")
            for kb in kbs[:3]:
                parts.append(f"    [{kb['category']}] {kb['title']}: {kb['content'][:100]}")

    # 5. Globaalne teadmistebaas (kui relevantne)
    elif prompt:
        kbs = search_knowledge(prompt[:60])
        if kbs:
            parts.append("\nТЕАМИСТЕБААС:")
            for kb in kbs[:3]:
                parts.append(f"  [{kb['category']}] {kb['title']}: {kb['content'][:100]}")

    # 6. Viimased märkmed
    recent_notes = get_recent_notes(3)
    if recent_notes:
        parts.append("\nПОСЛЕДНИЕ ЗАМЕТКИ:")
        for n in recent_notes:
            parts.append(f"  {n['content'][:120]}")

    # 7. Viimased vestlused
    recent = get_recent(6)
    if recent:
        parts.append("\nПОСЛЕДНИЕ РАЗГОВОРЫ:")
        for r in recent:
            parts.append(f"  Пользователь: {r['prompt'][:100]}")
            parts.append(f"  JARVIS: {r['response'][:100]}")

    return "\n".join(parts) if parts else ""

# ── Sõidukid ─────────────────────────────────────────────────────────────────
def save_vehicle(name: str, type: str = "car", make: str = "", model: str = "",
                 year: str = "", vin: str = "", notes: str = ""):
    with _conn() as c:
        c.execute("""INSERT INTO vehicles (name,type,make,model,year,vin,notes,updated_at)
                     VALUES (?,?,?,?,?,?,?,?)
                     ON CONFLICT(name) DO UPDATE SET
                       type=excluded.type, make=excluded.make, model=excluded.model,
                       year=excluded.year, vin=excluded.vin, notes=excluded.notes,
                       updated_at=excluded.updated_at""",
                  (name, type, make, model, year, vin, notes, datetime.now().isoformat()))

def get_vehicles() -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM vehicles ORDER BY updated_at DESC").fetchall()]

# ── Dokumendid ────────────────────────────────────────────────────────────────
def save_document(title: str, content: str, category: str = "general", tags: str = ""):
    with _conn() as c:
        c.execute("INSERT INTO documents (title,content,category,tags,created_at) VALUES (?,?,?,?,?)",
                  (title, content, category, tags, datetime.now().isoformat()))
    _index_memory(title, f"document:{category}", importance=0.7)

def search_documents(query: str) -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM documents WHERE title LIKE ? OR content LIKE ? OR tags LIKE ? ORDER BY created_at DESC LIMIT 5",
            (f"%{query}%", f"%{query}%", f"%{query}%")).fetchall()]

# ── Export & Delete (GDPR) ────────────────────────────────────────────────────
def export_memory() -> dict:
    return {
        "user_profile":  get_user_profile(),
        "facts":         get_all_facts(),
        "contacts":      get_all_contacts(),
        "projects":      get_projects("active") + get_projects("paused"),
        "notes":         get_recent_notes(200),
        "vehicles":      get_vehicles(),
        "knowledge":     search_knowledge("", category=None),
        "stats":         get_stats(),
        "exported_at":   datetime.now().isoformat(),
    }

def delete_all_memory(confirm: str = ""):
    """GDPR kustutus — nõuab confirm='DELETE'."""
    if confirm != "DELETE":
        raise ValueError("Kinnita kustutamine: confirm='DELETE'")
    tables = ["facts", "contacts", "notes", "conversations", "knowledge",
              "memory_index", "milestones", "project_entries"]
    with _conn() as c:
        for t in tables:
            c.execute(f"DELETE FROM {t}")
    return {"ok": True, "deleted_tables": tables}

# ── Prefs (backwards compat) ──────────────────────────────────────────────────
def save_pref(key: str, value):
    save_fact(f"pref_{key}", str(value))

def get_prefs() -> dict:
    return {k[5:]: v for k, v in get_all_facts().items() if k.startswith("pref_")}
