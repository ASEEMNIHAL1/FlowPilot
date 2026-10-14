import React, { useState } from 'react'
import {
  Activity,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronRight,
  Terminal,
  ShieldAlert,
  ArrowRightCircle,
  Clock,
  Layers,
} from 'lucide-react'

export function ExecutionTrace({ toolLogs = [], isRunning, runStatus }) {
  const [expandedLogs, setExpandedLogs] = useState({})

  const toggleExpand = (id) => {
    setExpandedLogs((prev) => ({
      ...prev,
      [id]: !prev[id],
    }))
  }

  const formatToolName = (name) => {
    switch (name) {
      case 'parse_goal':
        return { label: 'parse_goal', desc: 'Decomposing natural-language intent' }
      case 'get_calendar':
        return { label: 'get_calendar', desc: 'Querying day state from SQLite' }
      case 'get_tasks':
        return { label: 'get_tasks', desc: 'Fetching prioritized task backlog' }
      case 'propose_schedule':
        return { label: 'propose_schedule', desc: 'Calculating optimal time slots' }
      case 'create_event':
        return { label: 'create_event', desc: 'Committing calendar event to SQLite' }
      case 'delete_event':
        return { label: 'delete_event', desc: 'Conflict recovery: removing non-fixed item' }
      case 'update_event':
        return { label: 'update_event', desc: 'Adjusting scheduled event times' }
      case 'find_free_slots':
        return { label: 'find_free_slots', desc: 'Scanning for calendar openings' }
      case 'verify_schedule':
        return { label: 'verify_schedule', desc: 'Independent SQLite state audit' }
      default:
        return { label: name, desc: 'Agent tool execution' }
    }
  }

  return (
    <section className="trace-card glass-panel">
      <div className="card-header">
        <div className="card-title-group">
          <div className="icon-badge">
            <Activity size={18} />
          </div>
          <div>
            <div className="title-with-pill">
              <h2 className="card-title">Live Execution Trace</h2>
              <span className="badge badge-primary">{toolLogs.length} Tool Calls</span>
            </div>
            <p className="card-subtitle">
              Step-by-step audit feed showing tool invocations, parameters, and SQLite observations.
            </p>
          </div>
        </div>

        {isRunning && (
          <div className="running-indicator">
            <span className="pulse-dot" />
            <span className="text-sm">Executing Loop</span>
          </div>
        )}
      </div>

      <div className="trace-logs-stream">
        {toolLogs.length === 0 ? (
          <div className="empty-trace-state">
            <Terminal size={36} className="text-muted" />
            <p>No tool execution logs available.</p>
            <span className="text-muted text-sm">
              Launch a goal in the mission dispatcher to observe agent actions in real time.
            </span>
          </div>
        ) : (
          toolLogs.map((log, index) => {
            const toolInfo = formatToolName(log.tool_name)
            const isExpanded = !!expandedLogs[log.id || index]
            const isConflictRecovery =
              log.tool_name === 'delete_event' ||
              (log.tool_name === 'create_event' && !log.success && log.error?.includes('overlaps'))

            return (
              <div
                key={log.id || index}
                id={`tool-log-${index}`}
                className={`trace-log-item ${
                  log.success ? 'log-success' : 'log-failure'
                } ${isConflictRecovery ? 'log-conflict-recovery' : ''}`}
              >
                <div
                  className="log-summary-row"
                  onClick={() => toggleExpand(log.id || index)}
                  role="button"
                  tabIndex={0}
                >
                  <div className="log-index-badge">#{index + 1}</div>

                  <div className="log-status-icon">
                    {log.success ? (
                      <CheckCircle2 size={16} className="icon-success" />
                    ) : (
                      <XCircle size={16} className="icon-failure" />
                    )}
                  </div>

                  <div className="log-tool-details">
                    <div className="tool-title-row">
                      <span className="tool-name">{toolInfo.label}</span>
                      <span className="tool-desc">{toolInfo.desc}</span>
                      {isConflictRecovery && (
                        <span className="badge badge-warning">
                          <ShieldAlert size={11} />
                          {log.tool_name === 'delete_event' ? 'Conflict Recovered' : 'Overlap Detected'}
                        </span>
                      )}
                    </div>

                    {log.error && <p className="log-error-preview">{log.error}</p>}
                  </div>

                  <button
                    type="button"
                    className="log-expand-btn"
                    aria-label={isExpanded ? 'Collapse' : 'Expand'}
                  >
                    {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  </button>
                </div>

                {isExpanded && (
                  <div className="log-expanded-details">
                    <div className="detail-section">
                      <div className="detail-header">
                        <Layers size={13} />
                        <span>Arguments:</span>
                      </div>
                      <pre className="json-code-block">
                        {JSON.stringify(log.arguments, null, 2)}
                      </pre>
                    </div>

                    <div className="detail-section">
                      <div className="detail-header">
                        <Terminal size={13} />
                        <span>Observation Result:</span>
                      </div>
                      <pre className="json-code-block">
                        {typeof log.result === 'object'
                          ? JSON.stringify(log.result, null, 2)
                          : String(log.result || log.error || 'No result returned')}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
    </section>
  )
}
