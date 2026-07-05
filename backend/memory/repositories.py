"""
Albert OS — Repository Layer
Spek: 35_DATABASE_BIBLE.md — Repository Pattern

Iga domeen peidab andmebaasi implementatsiooni üksiku repositooriumi taha.
Rakenduse loogika ei puutu kunagi otse SQL-iga kokku.

Repositooriumid:
  UserRepository, ProjectRepository, MemoryRepository,
  ConversationRepository, VisionRepository, VoiceRepository,
  AISessionRepository, TaskRepository
"""
import json
from datetime import datetime
from memory.memory import _conn


def _now() -> str:
    return datetime.now().isoformat()


# ── UserRepository ────────────────────────────────────────────────────────────
class UserRepository:
    """User Domain — profiil, seaded, seadmed."""

    def get(self) -> dict:
        with _conn() as c:
            r = c.execute("SELECT * FROM user_profile WHERE id=1").fetchone()
            if not r:
                return {}
            d = dict(r)
            for k in ("devices", "permissions", "ai_settings"):
                d[k] = json.loads(d.get(k, "{}") or "{}")
            return d

    def update(self, **kwargs) -> None:
        profile = self.get()
        for k, v in kwargs.items():
            if isinstance(v, (dict, list)):
                profile[k] = json.dumps(v, ensure_ascii=False)
            else:
                profile[k] = v
        profile["updated_at"] = _now()
        with _conn() as c:
            c.execute("""UPDATE user_profile
                SET language=?, timezone=?, devices=?, permissions=?, ai_settings=?, updated_at=?
                WHERE id=1""",
                (profile.get("language", "ru"),
                 profile.get("timezone", "Europe/Tallinn"),
                 profile.get("devices") if isinstance(profile.get("devices"), str) else json.dumps(profile.get("devices", [])),
                 profile.get("permissions") if isinstance(profile.get("permissions"), str) else json.dumps(profile.get("permissions", {})),
                 profile.get("ai_settings") if isinstance(profile.get("ai_settings"), str) else json.dumps(profile.get("ai_settings", {})),
                 profile["updated_at"]))


# ── ProjectRepository ─────────────────────────────────────────────────────────
class ProjectRepository:
    """Project Domain — projektid, kirjed, verstapostid."""

    def list(self, status: str = None) -> list[dict]:
        with _conn() as c:
            if status:
                rows = c.execute("SELECT * FROM projects WHERE status=? ORDER BY updated_at DESC", (status,)).fetchall()
            else:
                rows = c.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
            return [dict(r) for r in rows]

    def get(self, name: str) -> dict | None:
        with _conn() as c:
            r = c.execute("SELECT * FROM projects WHERE name=?", (name,)).fetchone()
            return dict(r) if r else None

    def create(self, name: str, description: str = "", type_: str = "general",
               owner: str = "albert") -> dict:
        with _conn() as c:
            c.execute("""INSERT OR IGNORE INTO projects (name, description, type, owner, status, updated_at)
                VALUES (?, ?, ?, ?, 'active', ?)""",
                (name, description, type_, owner, _now()))
            r = c.execute("SELECT * FROM projects WHERE name=?", (name,)).fetchone()
            return dict(r)

    def update_status(self, name: str, status: str) -> None:
        with _conn() as c:
            c.execute("UPDATE projects SET status=?, updated_at=? WHERE name=?",
                      (status, _now(), name))

    def add_entry(self, project_name: str, entry_type: str, content: str) -> int:
        with _conn() as c:
            cur = c.execute("""INSERT INTO project_entries (project_name, entry_type, content, created_at)
                VALUES (?, ?, ?, ?)""", (project_name, entry_type, content, _now()))
            return cur.lastrowid

    def get_entries(self, project_name: str, entry_type: str = None, limit: int = 20) -> list[dict]:
        with _conn() as c:
            if entry_type:
                rows = c.execute("""SELECT * FROM project_entries
                    WHERE project_name=? AND entry_type=? ORDER BY created_at DESC LIMIT ?""",
                    (project_name, entry_type, limit)).fetchall()
            else:
                rows = c.execute("""SELECT * FROM project_entries
                    WHERE project_name=? ORDER BY created_at DESC LIMIT ?""",
                    (project_name, limit)).fetchall()
            return [dict(r) for r in rows]

    def add_milestone(self, project_name: str, title: str) -> int:
        with _conn() as c:
            cur = c.execute("""INSERT INTO milestones (project_name, title, created_at)
                VALUES (?, ?, ?)""", (project_name, title, _now()))
            return cur.lastrowid

    def complete_milestone(self, milestone_id: int) -> None:
        with _conn() as c:
            c.execute("UPDATE milestones SET done=1, done_at=? WHERE id=?",
                      (_now(), milestone_id))


# ── MemoryRepository ──────────────────────────────────────────────────────────
class MemoryRepository:
    """Memory Domain — mäluindeks, faktid, märkmed."""

    def search(self, query: str, project: str = None,
               min_importance: float = 0.0, limit: int = 20) -> list[dict]:
        with _conn() as c:
            if project:
                rows = c.execute("""SELECT * FROM memory_index
                    WHERE project=? AND importance_score>=?
                    AND (title LIKE ? OR summary LIKE ?)
                    AND (title NOT LIKE 'archived:%')
                    ORDER BY importance_score DESC LIMIT ?""",
                    (project, min_importance, f"%{query}%", f"%{query}%", limit)).fetchall()
            else:
                rows = c.execute("""SELECT * FROM memory_index
                    WHERE importance_score>=?
                    AND (title LIKE ? OR summary LIKE ?)
                    AND (title NOT LIKE 'archived:%')
                    ORDER BY importance_score DESC LIMIT ?""",
                    (min_importance, f"%{query}%", f"%{query}%", limit)).fetchall()
            return [dict(r) for r in rows]

    def get_facts(self) -> dict:
        with _conn() as c:
            rows = c.execute("SELECT key, value FROM facts").fetchall()
            return {r["key"]: r["value"] for r in rows}

    def set_fact(self, key: str, value: str) -> None:
        with _conn() as c:
            c.execute("INSERT OR REPLACE INTO facts (key, value, updated_at) VALUES (?, ?, ?)",
                      (key, value, _now()))

    def delete_fact(self, key: str) -> None:
        with _conn() as c:
            c.execute("DELETE FROM facts WHERE key=?", (key,))

    def add_note(self, content: str, tags: str = "", project: str = "",
                 importance: int = 0) -> int:
        with _conn() as c:
            cur = c.execute("""INSERT INTO notes (content, tags, project, importance, created_at)
                VALUES (?, ?, ?, ?, ?)""", (content, tags, project, importance, _now()))
            return cur.lastrowid

    def get_notes(self, project: str = "", limit: int = 20) -> list[dict]:
        with _conn() as c:
            if project:
                rows = c.execute("""SELECT * FROM notes WHERE project=?
                    ORDER BY created_at DESC LIMIT ?""", (project, limit)).fetchall()
            else:
                rows = c.execute("SELECT * FROM notes ORDER BY created_at DESC LIMIT ?",
                                 (limit,)).fetchall()
            return [dict(r) for r in rows]

    def schema_version(self) -> int:
        with _conn() as c:
            r = c.execute("SELECT MAX(version) as v FROM schema_version").fetchone()
            return r["v"] if r and r["v"] else 1


# ── ConversationRepository ────────────────────────────────────────────────────
class ConversationRepository:
    """Conversation Domain — vestlused, sõnumid, tööriistad."""

    def save(self, device: str, prompt: str, response: str, language: str = "ru",
             provider: str = "", project: str = "", tool_calls: list = None) -> int:
        with _conn() as c:
            cur = c.execute("""INSERT INTO conversations
                (device, prompt, response, language, ai_provider, related_project,
                 tool_calls, ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (device, prompt[:2000], response[:4000], language,
                 provider, project,
                 json.dumps(tool_calls or [], ensure_ascii=False), _now()))
            return cur.lastrowid

    def get_recent(self, device: str = None, limit: int = 10) -> list[dict]:
        with _conn() as c:
            if device:
                rows = c.execute("""SELECT * FROM conversations WHERE device=?
                    ORDER BY ts DESC LIMIT ?""", (device, limit)).fetchall()
            else:
                rows = c.execute("SELECT * FROM conversations ORDER BY ts DESC LIMIT ?",
                                 (limit,)).fetchall()
            return [dict(r) for r in rows]

    def summarize_old(self, days_old: int = 30) -> int:
        """Märgi vanad vestlused kokkuvõtlikuks (tulevane auto-summary hook)."""
        with _conn() as c:
            cur = c.execute("""UPDATE conversations SET summary='[auto-archived]'
                WHERE ts < datetime('now', ?) AND summary=''""",
                (f"-{days_old} days",))
            return cur.rowcount


# ── VisionRepository ──────────────────────────────────────────────────────────
class VisionRepository:
    """Vision Domain — pildid, inspektsioonid, OCR."""

    def save_inspection(self, project: str, mode: str, prompt: str,
                        response: str, confidence: str = "medium",
                        ocr_text: str = "", image_size_kb: float = 0) -> int:
        with _conn() as c:
            cur = c.execute("""INSERT INTO vision_inspections
                (project, mode, prompt, response, confidence, ocr_text, image_size_kb, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (project, mode, prompt[:500], response[:3000], confidence,
                 ocr_text[:2000], image_size_kb, _now()))
            return cur.lastrowid

    def get_by_project(self, project: str, limit: int = 10) -> list[dict]:
        with _conn() as c:
            rows = c.execute("""SELECT * FROM vision_inspections WHERE project=?
                ORDER BY created_at DESC LIMIT ?""", (project, limit)).fetchall()
            return [dict(r) for r in rows]

    def get_recent(self, limit: int = 20) -> list[dict]:
        with _conn() as c:
            rows = c.execute("""SELECT id, project, mode, confidence, created_at
                FROM vision_inspections ORDER BY created_at DESC LIMIT ?""",
                (limit,)).fetchall()
            return [dict(r) for r in rows]


# ── VoiceRepository ───────────────────────────────────────────────────────────
class VoiceRepository:
    """Voice Domain — transkriptid, keelesätted."""

    def save_transcript(self, device: str, language: str, transcript: str,
                        summary: str = "", duration_s: float = 0) -> int:
        with _conn() as c:
            cur = c.execute("""INSERT INTO voice_transcripts
                (device, language, transcript, summary, duration_s, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (device, language, transcript, summary, duration_s, _now()))
            return cur.lastrowid

    def get_recent(self, device: str = None, limit: int = 20) -> list[dict]:
        with _conn() as c:
            if device:
                rows = c.execute("""SELECT * FROM voice_transcripts WHERE device=?
                    ORDER BY created_at DESC LIMIT ?""", (device, limit)).fetchall()
            else:
                rows = c.execute("SELECT * FROM voice_transcripts ORDER BY created_at DESC LIMIT ?",
                                 (limit,)).fetchall()
            return [dict(r) for r in rows]


# ── AISessionRepository ───────────────────────────────────────────────────────
class AISessionRepository:
    """AI Session Domain — provider, mudel, latentsus, tokenid."""

    def record(self, device: str, provider: str, model: str, intent: str,
               latency_ms: int, prompt_tokens: int = 0, resp_tokens: int = 0,
               confidence: str = "high", tools_used: list = None) -> int:
        with _conn() as c:
            cur = c.execute("""INSERT INTO ai_sessions
                (device, provider, model, intent, latency_ms, prompt_tokens,
                 resp_tokens, confidence, tools_used, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (device, provider, model, intent, latency_ms, prompt_tokens,
                 resp_tokens, confidence,
                 json.dumps(tools_used or [], ensure_ascii=False), _now()))
            return cur.lastrowid

    def get_stats(self) -> dict:
        with _conn() as c:
            rows = c.execute("""SELECT provider, COUNT(*) as calls,
                AVG(latency_ms) as avg_ms, SUM(resp_tokens) as total_tokens
                FROM ai_sessions GROUP BY provider""").fetchall()
            return {r["provider"]: dict(r) for r in rows}

    def get_recent(self, limit: int = 20) -> list[dict]:
        with _conn() as c:
            rows = c.execute("""SELECT id, provider, model, intent, latency_ms,
                confidence, created_at FROM ai_sessions
                ORDER BY created_at DESC LIMIT ?""", (limit,)).fetchall()
            return [dict(r) for r in rows]


# ── TaskRepository ────────────────────────────────────────────────────────────
class TaskRepository:
    """Task Domain — agendi ülesanded püsivalt."""

    def save(self, task_id: str, agent_type: str, objective: str,
             status: str = "pending", project: str = "", priority: int = 5) -> None:
        with _conn() as c:
            c.execute("""INSERT OR REPLACE INTO agent_tasks
                (task_id, agent_type, objective, status, project, priority, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (task_id, agent_type, objective, status, project, priority, _now()))

    def update(self, task_id: str, status: str, progress_pct: int = 0,
               progress_step: str = "", result: str = "", error: str = "") -> None:
        with _conn() as c:
            finished = _now() if status in ("done", "failed") else None
            c.execute("""UPDATE agent_tasks
                SET status=?, progress_pct=?, progress_step=?,
                    result=?, error=?, finished_at=?
                WHERE task_id=?""",
                (status, progress_pct, progress_step, result[:2000],
                 error[:500], finished, task_id))

    def get(self, task_id: str) -> dict | None:
        with _conn() as c:
            r = c.execute("SELECT * FROM agent_tasks WHERE task_id=?", (task_id,)).fetchone()
            return dict(r) if r else None

    def list(self, status: str = None, limit: int = 20) -> list[dict]:
        with _conn() as c:
            if status:
                rows = c.execute("""SELECT * FROM agent_tasks WHERE status=?
                    ORDER BY created_at DESC LIMIT ?""", (status, limit)).fetchall()
            else:
                rows = c.execute("SELECT * FROM agent_tasks ORDER BY created_at DESC LIMIT ?",
                                 (limit,)).fetchall()
            return [dict(r) for r in rows]


# ── Singletons (importi nendega) ──────────────────────────────────────────────
users         = UserRepository()
projects      = ProjectRepository()
memories      = MemoryRepository()
conversations = ConversationRepository()
vision        = VisionRepository()
voice         = VoiceRepository()
ai_sessions   = AISessionRepository()
tasks         = TaskRepository()
