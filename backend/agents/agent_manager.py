"""
Albert OS — Agent Manager
Spek: 34_AUTONOMOUS_AGENT_BIBLE.md

Haldab spetsialiseeritud agentide elutsüklit:
  Research / Coding / Vision / Planning / Memory / Monitoring / Automation

Elutsükkel:
  1. Receive objective
  2. Create execution plan
  3. Gather context
  4. Execute approved actions
  5. Report progress
  6. Store useful knowledge
  7. Finish or wait

Safety rules (kasutaja peab kinnitama):
  - Secrets exposure
  - Money spending
  - Sending messages
  - Modifying important files
  - Deleting data
"""
import asyncio
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Callable, Awaitable

from core.events import emit_sync, TOOL_EXECUTED, MEMORY_UPDATED
from core.monitor import audit

log = logging.getLogger("albert.agents")

# ── Safety gate ───────────────────────────────────────────────────────────────
_RESTRICTED_ACTIONS = {
    "expose_secrets", "spend_money", "send_message",
    "modify_important_file", "delete_data",
}

def _is_safe(action: str) -> bool:
    return action not in _RESTRICTED_ACTIONS


# ── Progress report ───────────────────────────────────────────────────────────
@dataclass
class Progress:
    step: str         = ""
    percent: int      = 0
    problems: list    = field(default_factory=list)
    eta_sec: int      = 0
    next_action: str  = ""

    def to_dict(self) -> dict:
        return {
            "step":        self.step,
            "percent":     self.percent,
            "problems":    self.problems,
            "eta_sec":     self.eta_sec,
            "next_action": self.next_action,
        }


# ── Task record ───────────────────────────────────────────────────────────────
@dataclass
class AgentTask:
    task_id:     str
    agent_type:  str
    objective:   str
    status:      str        = "pending"    # pending|running|done|failed|waiting
    progress:    Progress   = field(default_factory=Progress)
    result:      str        = ""
    error:       str        = ""
    created_at:  float      = field(default_factory=time.time)
    finished_at: float      = 0.0

    def to_dict(self) -> dict:
        return {
            "task_id":     self.task_id,
            "agent_type":  self.agent_type,
            "objective":   self.objective,
            "status":      self.status,
            "progress":    self.progress.to_dict(),
            "result":      self.result[:500],
            "error":       self.error,
            "created_at":  self.created_at,
            "finished_at": self.finished_at,
        }


# ── Base Agent ────────────────────────────────────────────────────────────────
class BaseAgent:
    """Kõigi agentide ülemklass."""
    agent_type: str = "base"

    def __init__(self, task: AgentTask,
                 on_progress: Callable[[AgentTask], None] | None = None):
        self.task        = task
        self.on_progress = on_progress

    def _report(self, step: str, percent: int, next_action: str = "", problems: list = None, eta_sec: int = 0):
        self.task.progress = Progress(
            step=step, percent=percent,
            problems=problems or [],
            eta_sec=eta_sec,
            next_action=next_action,
        )
        if self.on_progress:
            self.on_progress(self.task)

    def _require_approval(self, action: str, details: str = "") -> bool:
        """Safety gate — piiratud tegevused nõuavad kasutaja kinnitust."""
        if not _is_safe(action):
            log.warning("Agent '%s' tried restricted action '%s': %s",
                        self.agent_type, action, details)
            self.task.progress.problems.append(
                f"Restricted action '{action}' blocked — user approval required."
            )
            return False
        return True

    async def run(self) -> str:
        raise NotImplementedError


# ── Research Agent ────────────────────────────────────────────────────────────
class ResearchAgent(BaseAgent):
    """Otsib dokumentatsiooni, võrdleb allikaid, toodab kokkuvõtteid."""
    agent_type = "research"

    async def run(self) -> str:
        from agents.director import run_with_tools
        from memory.memory import get_context_for_prompt

        self._report("Kogumine: mälukontekst", 10, "Search memory")
        mem_ctx = get_context_for_prompt(self.task.objective)

        self._report("Analüüs: Perplexity + Claude paralleelne otsing", 40, "AI research", eta_sec=20)
        result, _ = await run_with_tools(
            f"[RESEARCH AGENT] {self.task.objective}\n\nContext:\n{mem_ctx}",
            memory_ctx=mem_ctx
        )

        self._report("Kokkuvõte salvestamine", 80, "Save to memory")
        try:
            from memory.memory import add_project_entry
            add_project_entry("Isiklik", "note", f"[Research] {self.task.objective[:60]}: {result[:300]}")
        except Exception:
            pass

        self._report("Valmis", 100, "")
        return result or "Uurimine lõpetatud, tulemused puuduvad."


# ── Coding Agent ──────────────────────────────────────────────────────────────
class CodingAgent(BaseAgent):
    """Analüüsib koodi, soovitab muudatusi, genereerib koodi."""
    agent_type = "coding"

    async def run(self) -> str:
        from agents.director import run_with_tools
        from memory.memory import get_context_for_prompt

        self._report("Konteksti laadimine", 15, "Load code context")
        mem_ctx = get_context_for_prompt(self.task.objective)

        self._report("Koodi analüüs + soovituste genereerimine", 50, "AI coding analysis", eta_sec=15)
        result, _ = await run_with_tools(
            f"[CODING AGENT] {self.task.objective}\n\nMemory:\n{mem_ctx}",
            memory_ctx=mem_ctx
        )
        self._report("Valmis", 100, "Review suggested changes")
        return result or "Koodi analüüs lõpetatud."


# ── Vision Agent ──────────────────────────────────────────────────────────────
class VisionAgent(BaseAgent):
    """Analüüsib pilte, võrdleb ülevaatusi, jälgib progressi."""
    agent_type = "vision"

    def __init__(self, task: AgentTask, image_b64: str = "", on_progress=None):
        super().__init__(task, on_progress)
        self.image_b64 = image_b64

    async def run(self) -> str:
        from agents.director import run_with_tools
        from memory.memory import get_context_for_prompt

        if not self.image_b64:
            return "Pildi analüüsiks on vaja pilti."

        self._report("Pildi eeltöötlus", 20, "Preprocess image")
        from engines.vision_engine import preprocess_image
        pre = preprocess_image(self.image_b64)
        if not pre.get("ok"):
            return f"Pildi töötlemine ebaõnnestus: {pre.get('reason')}"

        self._report("AI analüüs", 60, "Analyze with AI", eta_sec=10)
        mem_ctx = get_context_for_prompt(self.task.objective)
        result, _ = await run_with_tools(
            self.task.objective or "Analüüsi pilt.",
            image_b64=self.image_b64,
            memory_ctx=mem_ctx
        )
        self._report("Valmis", 100, "")
        return result or "Visioonanalüüs lõpetatud."


# ── Planning Agent ────────────────────────────────────────────────────────────
class PlanningAgent(BaseAgent):
    """Jagab suured eesmärgid ülesanneteks, hindab sõltuvusi."""
    agent_type = "planning"

    async def run(self) -> str:
        from core.planner import build_plan, format_plan_for_prompt
        from agents.director import run_with_tools

        self._report("Plaani koostamine", 30, "Build plan")
        steps = build_plan(self.task.objective, "planning")
        plan_text = format_plan_for_prompt(steps)

        self._report("Plaani täpsustamine AI-ga", 70, "AI refinement", eta_sec=8)
        result, _ = await run_with_tools(
            f"[PLANNING AGENT] Koosta üksikasjalik tegevusplaan:\n{self.task.objective}\n\nAlgne plaan:\n{plan_text}"
        )
        self._report("Valmis", 100, "Review plan")
        return result or plan_text


# ── Memory Agent ──────────────────────────────────────────────────────────────
class MemoryAgent(BaseAgent):
    """Organiseerib mälestusi, arhiveerib vana info, parandab otsimise kvaliteeti."""
    agent_type = "memory"

    async def run(self) -> str:
        from memory.memory import search_all_memory, archive_memory, search_memory_index

        self._report("Duplikaatide otsimine", 20, "Search duplicates")
        results = search_all_memory(self.task.objective or "")
        count = len(results)

        self._report("Vana info arhiveerimine", 60, "Archive old entries")
        archived = 0
        try:
            old_entries = search_memory_index("", min_importance=0.0, include_archived=False)
            for e in old_entries:
                if e.get("importance_score", 1.0) < 0.2 and e.get("access_count", 1) == 0:
                    archive_memory(e["id"])
                    archived += 1
                    if archived >= 10:
                        break
        except Exception as ex:
            self.task.progress.problems.append(str(ex))

        self._report("Valmis", 100, "")
        emit_sync(MEMORY_UPDATED, {"type": "memory_agent_cleanup", "archived": archived})
        return f"Mälu korraldatud. Leitud kirjeid: {count}. Arhiveeritud: {archived}."


# ── Monitoring Agent ──────────────────────────────────────────────────────────
class MonitoringAgent(BaseAgent):
    """Jälgib pikaajalisi töid, tuvastab vigu, teavitab kasutajat."""
    agent_type = "monitoring"

    def __init__(self, task: AgentTask, watch_task_id: str = "", on_progress=None):
        super().__init__(task, on_progress)
        self.watch_task_id = watch_task_id

    async def run(self) -> str:
        from core.monitor import get_audit_log
        self._report("Monitoringu alustamine", 10, "Start monitoring")
        log_entries = get_audit_log(20)
        errors = [e for e in log_entries if "error" in str(e).lower()]
        self._report("Analüüs", 80, "Analyze results")
        self._report("Valmis", 100, "")
        if errors:
            return f"Leitud {len(errors)} veateadet:\n" + "\n".join(str(e) for e in errors[:5])
        return "Süsteem töötab normaalselt. Vigu ei leitud."


# ── Agent Manager ─────────────────────────────────────────────────────────────
_AGENT_CLASSES = {
    "research":   ResearchAgent,
    "coding":     CodingAgent,
    "vision":     VisionAgent,
    "planning":   PlanningAgent,
    "memory":     MemoryAgent,
    "monitoring": MonitoringAgent,
}

_tasks: dict[str, AgentTask] = {}   # task_id → AgentTask
_MAX_TASKS = 50


class AgentManager:
    """
    Haldab agentide elutsüklit.
    Kasutaja pöördub direktori kaudu, mitte otse agentide poole.
    """

    def create_task(self, agent_type: str, objective: str, **kwargs) -> AgentTask:
        """Loo uus agendi ülesanne (ei käivita kohe)."""
        if agent_type not in _AGENT_CLASSES:
            raise ValueError(f"Unknown agent type: {agent_type}. Valid: {list(_AGENT_CLASSES)}")
        task_id = str(uuid.uuid4())[:8]
        task = AgentTask(task_id=task_id, agent_type=agent_type, objective=objective)
        _tasks[task_id] = task
        if len(_tasks) > _MAX_TASKS:
            oldest = min(_tasks, key=lambda k: _tasks[k].created_at)
            del _tasks[oldest]
        audit("agent_created", {"task_id": task_id, "agent_type": agent_type})
        return task

    async def run_task(self, task_id: str,
                       on_progress: Callable[[AgentTask], None] | None = None,
                       **kwargs) -> AgentTask:
        """Käivita ülesanne. Tagastab lõpliku AgentTask."""
        task = _tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found")
        if task.status == "running":
            return task

        cls = _AGENT_CLASSES[task.agent_type]
        agent = cls(task, on_progress=on_progress, **kwargs)
        task.status = "running"
        task.progress = Progress(step="Starting", percent=0)
        audit("agent_started", {"task_id": task_id, "agent_type": task.agent_type})

        try:
            result = await agent.run()
            task.result = result
            task.status = "done"
        except Exception as e:
            task.error = str(e)
            task.status = "failed"
            log.exception("Agent %s task %s failed", task.agent_type, task_id)
        finally:
            task.finished_at = time.time()
            audit("agent_finished", {"task_id": task_id, "status": task.status})

        return task

    async def run_task_background(self, task_id: str, **kwargs) -> str:
        """Käivita taustal — tagastab kohe task_id."""
        asyncio.create_task(self.run_task(task_id, **kwargs))
        return task_id

    def get_task(self, task_id: str) -> AgentTask | None:
        return _tasks.get(task_id)

    def list_tasks(self, agent_type: str = None, status: str = None) -> list[dict]:
        tasks = list(_tasks.values())
        if agent_type:
            tasks = [t for t in tasks if t.agent_type == agent_type]
        if status:
            tasks = [t for t in tasks if t.status == status]
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in tasks[:20]]

    def agent_types(self) -> list[str]:
        return list(_AGENT_CLASSES)


# Globaalne singleton
manager = AgentManager()
