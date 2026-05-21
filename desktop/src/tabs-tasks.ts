import { S } from "./state";
import { esc, fmtRel } from "./tabs-a";

export function tasksTab(): string {
  const tasks = S.taskState.tasks;
  const todo = tasks.filter((t) => t.status === "todo");
  const inProgress = tasks.filter((t) => t.status === "in_progress");
  const done = tasks.filter((t) => t.status === "done");

  function priorityBadge(priority: string): string {
    const colors: Record<string, string> = {
      urgent: "bad",
      high: "warn",
      medium: "info",
      low: "ok",
    };
    return `<span class="badge ${colors[priority] || "info"}">${esc(priority)}</span>`;
  }

  function taskCard(task: typeof tasks[0]): string {
    return `<div class="task-card">
  <div class="task-card-header">
    <div class="task-card-title">${esc(task.title)}</div>
    ${priorityBadge(task.priority)}
  </div>
  ${task.description ? `<div class="task-card-desc">${esc(task.description.slice(0, 120))}</div>` : ""}
  <div class="task-card-meta">
    ${task.due_at ? `<span>Due: ${esc(task.due_at.slice(0, 10))}</span>` : ""}
    <span>${fmtRel(task.updated_at)}</span>
  </div>
  <div class="task-card-actions">
    ${task.status !== "todo" ? `<button class="sm" data-task-id="${task.id}" data-task-status="todo">← Todo</button>` : ""}
    ${task.status !== "in_progress" ? `<button class="sm" data-task-id="${task.id}" data-task-status="in_progress">▶ In Progress</button>` : ""}
    ${task.status !== "done" ? `<button class="sm success" data-task-id="${task.id}" data-task-status="done">✓ Done</button>` : ""}
    <button class="sm danger" data-del-task="${task.id}">🗑</button>
  </div>
</div>`;
  }

  return `<div class="panel" style="padding-bottom:8px">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    📋 Tasks (${tasks.length}) <button id="btn-reload-tasks" class="sm">🔄 Refresh</button>
  </div>
</div>
<div class="task-columns">
  <div class="task-column">
    <div class="task-column-header">Todo (${todo.length})</div>
    ${todo.length ? todo.map(taskCard).join("") : `<div class="section-empty">No tasks</div>`}
  </div>
  <div class="task-column">
    <div class="task-column-header">In Progress (${inProgress.length})</div>
    ${inProgress.length ? inProgress.map(taskCard).join("") : `<div class="section-empty">No tasks</div>`}
  </div>
  <div class="task-column">
    <div class="task-column-header">Done (${done.length})</div>
    ${done.length ? done.map(taskCard).join("") : `<div class="section-empty">No tasks</div>`}
  </div>
</div>`;
}
