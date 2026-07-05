"""
Albert OS — Task & Automation Engine
Spek: 44_TASK_AND_AUTOMATION_ENGINE_BIBLE.md

Task Types:
  one-time, recurring, background_monitoring,
  project_task, agent_task, reminder

Safety Gates:
  Kõik pöördumatud toimingud nõuavad kinnitust enne täitmist.
"""
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Any

from core.events import emit_sync, MEMORY_UPDATED
from core.monitor import audit

log = logging.getLogger("albert.task_engine")


# ── Task Types (spec 44) ──────────────────────────────────────────────────────
class TaskType(str, Enum):
    ONE_TIME              = "one_time"
    RECURRING             = "recurring"
    BACKGROUND_MONITORING = "background_monitoring"
    PROJECT_TASK          = "project_task"
    AGENT_TASK            = "agent_task"
    REMINDER              = "reminder"


class TaskStatus(str, Enum):
    PENDING    = "pending"
    APPROVED   = "approved"
    RUNNING    = "running"
    COMPLETED  = "completed"
    FAILED     = "failed"
    CANCELLED  = "cancelled"
    WAITING_APPROVAL = "waiting_approval"


class TaskPriority(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"
    URGENT = "urgent"


# ── Toimingud mis nõuavad kinnitust (spec 44 — Safety) ───────────────────────
REQUIRES_APPROVAL = {
    "purchase", "send_message", "delete_data",
    "public_post", "irreversible",
}


# ── Task Object (spec 44) ─────────────────────────────────────────────────────
@dataclass
class ScheduledTask:
    task_id:      str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    title:        str = ""
    project:      str = ""
    task_type:    TaskType   = TaskType.ONE_TIME
    status:       TaskStatus = TaskStatus.PENDING
    priority:     TaskPriority = TaskPriority.MEDIUM
    due_at:       str | None  = None
    dependencies: list[str]   = field(default_factory=list)
    action:       str = ""        # tegevuse tüüp (nt "send_message", "summarize")
    params:       dict = field(default_factory=dict)
    recurrence:   str | None = None  # "daily" | "weekly" | "hourly"
    created_at:   str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: str | None = None
    result:       Any  = None
    error:        str | None = None
    approved:     bool = False

    def to_dict(self) -> dict:
        return {
            "task_id":      self.task_id,
            "title":        self.title,
            "project":      self.project,
            "task_type":    self.task_type.value,
            "status":       self.status.value,
            "priority":     self.priority.value,
            "due_at":       self.due_at,
            "dependencies": self.dependencies,
            "action":       self.action,
            "params":       self.params,
            "recurrence":   self.recurrence,
            "created_at":   self.created_at,
            "completed_at": self.completed_at,
            "approved":     self.approved,
        }

    def needs_approval(self) -> bool:
        return self.action in REQUIRES_APPROVAL


# ── Task Engine ───────────────────────────────────────────────────────────────
class TaskEngine:
    """
    Planeerib ja käivitab ülesandeid.
    Execution Flow: User Goal → Planner → Task List → Approval → Execution → Report
    """

    def __init__(self):
        self._tasks:   dict[str, ScheduledTask] = {}
        self._timers:  dict[str, asyncio.Task]  = {}
        self._handlers: dict[str, Callable]     = {}

    def register_handler(self, action: str, handler: Callable) -> None:
        """Registreeri tegevuse täitja."""
        self._handlers[action] = handler

    # ── Create ─────────────────────────────────────────────────────────────────
    def create(self, title: str, action: str = "", task_type: TaskType = TaskType.ONE_TIME,
               project: str = "", priority: TaskPriority = TaskPriority.MEDIUM,
               due_at: str | None = None, params: dict = None,
               recurrence: str | None = None, dependencies: list = None) -> ScheduledTask:
        task = ScheduledTask(
            title=title, action=action, task_type=task_type,
            project=project, priority=priority, due_at=due_at,
            params=params or {}, recurrence=recurrence,
            dependencies=dependencies or [],
        )
        if task.needs_approval():
            task.status = TaskStatus.WAITING_APPROVAL
        self._tasks[task.task_id] = task
        audit("task_created", {"task_id": task.task_id, "title": title, "action": action})
        log.info("Task created: %s [%s]", task.task_id, title)
        return task

    # ── Approve ────────────────────────────────────────────────────────────────
    def approve(self, task_id: str) -> dict:
        """Kasutaja kinnitus pöördumatu toimingu jaoks."""
        task = self._tasks.get(task_id)
        if not task:
            return {"ok": False, "error": "Task not found"}
        task.approved = True
        task.status   = TaskStatus.APPROVED
        audit("task_approved", {"task_id": task_id})
        return {"ok": True, "task_id": task_id}

    # ── Execute ────────────────────────────────────────────────────────────────
    async def execute(self, task_id: str) -> ScheduledTask:
        task = self._tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found")
        if task.needs_approval() and not task.approved:
            task.status = TaskStatus.WAITING_APPROVAL
            return task

        # Kontrolli dependency'id
        for dep_id in task.dependencies:
            dep = self._tasks.get(dep_id)
            if dep and dep.status != TaskStatus.COMPLETED:
                log.info("Task %s waiting for dependency %s", task_id, dep_id)
                task.status = TaskStatus.PENDING
                return task

        task.status = TaskStatus.RUNNING
        log.info("Executing task: %s [%s]", task_id, task.title)

        try:
            handler = self._handlers.get(task.action)
            if handler:
                task.result = await handler(task.params) \
                    if asyncio.iscoroutinefunction(handler) else handler(task.params)
            else:
                task.result = f"No handler for action '{task.action}'"
            task.status       = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow().isoformat()
            audit("task_completed", {"task_id": task_id, "action": task.action})
            emit_sync(MEMORY_UPDATED, {"type": "task_completed", "task_id": task_id},
                      source="TaskEngine")
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error  = str(e)
            log.error("Task %s failed: %s", task_id, e)
            audit("task_failed", {"task_id": task_id, "error": str(e)})

        # Recurring: loo järgmine
        if task.status == TaskStatus.COMPLETED and task.recurrence:
            self._schedule_recurrence(task)

        return task

    def _schedule_recurrence(self, task: ScheduledTask) -> None:
        """Loo järgmine korduv ülesanne."""
        intervals = {"hourly": 3600, "daily": 86400, "weekly": 604800}
        delay = intervals.get(task.recurrence, 86400)
        next_task = self.create(
            title=task.title, action=task.action,
            task_type=task.task_type, project=task.project,
            priority=task.priority, params=task.params,
            recurrence=task.recurrence,
        )
        next_task.approved = task.approved
        next_task.status   = TaskStatus.PENDING

        async def _delayed_exec():
            await asyncio.sleep(delay)
            await self.execute(next_task.task_id)

        timer = asyncio.create_task(_delayed_exec())
        self._timers[next_task.task_id] = timer
        log.info("Recurring task scheduled: %s (next in %ds)", next_task.task_id, delay)

    def cancel(self, task_id: str) -> dict:
        task = self._tasks.get(task_id)
        if not task:
            return {"ok": False, "error": "not found"}
        if timer := self._timers.pop(task_id, None):
            timer.cancel()
        task.status = TaskStatus.CANCELLED
        audit("task_cancelled", {"task_id": task_id})
        return {"ok": True}

    # ── Listing & queries ──────────────────────────────────────────────────────
    def list_tasks(self, project: str = None, status: str = None,
                   task_type: str = None) -> list[dict]:
        tasks = list(self._tasks.values())
        if project:
            tasks = [t for t in tasks if t.project == project]
        if status:
            tasks = [t for t in tasks if t.status.value == status]
        if task_type:
            tasks = [t for t in tasks if t.task_type.value == task_type]
        return [t.to_dict() for t in tasks]

    def get_task(self, task_id: str) -> ScheduledTask | None:
        return self._tasks.get(task_id)

    # ── Automation examples (spec 44) ─────────────────────────────────────────
    def create_daily_summary(self, project: str) -> ScheduledTask:
        return self.create(
            title=f"Päeva kokkuvõte: {project}",
            action="summarize",
            task_type=TaskType.RECURRING,
            project=project,
            recurrence="daily",
            params={"scope": project},
        )

    def create_reminder(self, title: str, due_at: str, project: str = "") -> ScheduledTask:
        return self.create(
            title=title,
            task_type=TaskType.REMINDER,
            project=project,
            due_at=due_at,
            action="remind",
        )


# ── Global singleton ──────────────────────────────────────────────────────────
task_engine = TaskEngine()
