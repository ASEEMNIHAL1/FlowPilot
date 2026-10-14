import React from 'react'
import {
  CheckSquare,
  Clock,
  Calendar,
  AlertCircle,
  PlusCircle,
  ArrowUpRight,
} from 'lucide-react'

export function TaskBacklog({ tasks = [], onSelectTask }) {
  const getPriorityBadge = (priority) => {
    switch (priority) {
      case 1:
        return <span className="badge badge-danger">P1 Urgent</span>
      case 2:
        return <span className="badge badge-warning">P2 Normal</span>
      case 3:
        return <span className="badge badge-primary">P3 Low</span>
      default:
        return <span className="badge badge-neutral">P{priority}</span>
    }
  }

  const formatDeadline = (deadlineStr) => {
    if (!deadlineStr) return null
    try {
      const d = new Date(deadlineStr)
      return d.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    } catch {
      return deadlineStr
    }
  }

  return (
    <section className="backlog-card glass-panel">
      <div className="card-header">
        <div className="card-title-group">
          <div className="icon-badge">
            <CheckSquare size={18} />
          </div>
          <div>
            <div className="title-with-pill">
              <h2 className="card-title">Backlog Tasks</h2>
              <span className="badge badge-neutral">{tasks.length} Available</span>
            </div>
            <p className="card-subtitle">
              Prioritized tasks stored in SQLite ready to be planned and scheduled.
            </p>
          </div>
        </div>
      </div>

      <div className="tasks-list">
        {tasks.length === 0 ? (
          <div className="empty-backlog-state">
            <CheckSquare size={32} className="text-muted" />
            <p>No pending backlog tasks.</p>
          </div>
        ) : (
          tasks.map((task) => (
            <div key={task.id} id={`backlog-task-${task.id}`} className="task-item-card">
              <div className="task-main-col">
                <div className="task-title-row">
                  <h3 className="task-title">{task.title}</h3>
                  {getPriorityBadge(task.priority)}
                </div>

                <div className="task-meta-row">
                  <span className="meta-info">
                    <Clock size={12} />
                    {task.duration_minutes} mins
                  </span>

                  {task.deadline && (
                    <span className="meta-info text-warning">
                      <Calendar size={12} />
                      Due {formatDeadline(task.deadline)}
                    </span>
                  )}
                </div>
              </div>

              {onSelectTask && (
                <button
                  type="button"
                  id={`btn-add-task-${task.id}`}
                  className="icon-action-btn select-task-btn"
                  title="Include task in agent goal"
                  onClick={() => onSelectTask(task)}
                >
                  <PlusCircle size={16} />
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </section>
  )
}
