import React from 'react'
import {
  History,
  X,
  CheckCircle,
  AlertTriangle,
  Clock,
  Sparkles,
  ArrowRight,
} from 'lucide-react'

export function RunHistoryModal({ runs = [], onClose, onSelectRun, selectedRunId }) {
  const formatTime = (isoString) => {
    if (!isoString) return ''
    try {
      const d = new Date(isoString)
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } catch {
      return isoString
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal-container glass-panel">
        <div className="modal-header">
          <div className="card-title-group">
            <div className="icon-badge">
              <History size={18} />
            </div>
            <div>
              <h2 className="card-title">Agent Execution History</h2>
              <p className="card-subtitle">Select a past run to inspect its tool calls and verification proofs.</p>
            </div>
          </div>
          <button type="button" className="close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="runs-list-scroll">
          {runs.length === 0 ? (
            <div className="empty-history">
              <Clock size={32} className="text-muted" />
              <p>No historical runs found.</p>
            </div>
          ) : (
            runs.map((run) => (
              <div
                key={run.id}
                id={`run-history-item-${run.id}`}
                className={`run-history-row ${selectedRunId === run.id ? 'active' : ''}`}
                onClick={() => {
                  onSelectRun(run.id)
                  onClose()
                }}
              >
                <div className="run-row-info">
                  <div className="run-title-line">
                    <span className="run-id-tag">Run #{run.id}</span>
                    <span
                      className={`badge ${
                        run.status === 'verified'
                          ? 'badge-success'
                          : run.status === 'failed'
                          ? 'badge-danger'
                          : 'badge-primary'
                      }`}
                    >
                      {run.status}
                    </span>
                    <span className="run-date-tag">{run.target_date}</span>
                  </div>
                  <p className="run-goal-preview">{run.goal}</p>
                </div>

                <div className="run-action-arrow">
                  <ArrowRight size={16} />
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
