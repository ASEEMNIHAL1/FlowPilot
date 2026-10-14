import React, { useState } from 'react'
import {
  Sparkles,
  RotateCcw,
  RefreshCw,
  Clock,
  Cpu,
  ShieldCheck,
  Calendar as CalendarIcon,
  CheckCircle2,
  AlertTriangle,
  History,
} from 'lucide-react'

export function Header({
  healthInfo,
  onResetDemo,
  onRefresh,
  isLoading,
  targetDate,
  onDateChange,
  onToggleHistory,
  historyCount = 0,
}) {
  const [resetConfirm, setResetConfirm] = useState(false)
  const [resetting, setResetting] = useState(false)

  const handleReset = async () => {
    if (!resetConfirm) {
      setResetConfirm(true)
      setTimeout(() => setResetConfirm(false), 4000)
      return
    }
    setResetting(true)
    setResetConfirm(false)
    try {
      await onResetDemo()
    } finally {
      setResetting(false)
    }
  }

  // Quick helper dates: today and tomorrow in YYYY-MM-DD
  const todayStr = new Date().toISOString().split('T')[0]
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  const tomorrowStr = tomorrow.toISOString().split('T')[0]

  return (
    <header className="header-wrapper glass-panel">
      <div className="header-top">
        <div className="brand-group">
          <div className="brand-icon">
            <Sparkles className="icon-sparkle" size={24} />
          </div>
          <div>
            <div className="brand-title-row">
              <h1 className="brand-title">FlowPilot</h1>
              <span className="badge badge-primary">Autonomous Agent</span>
            </div>
            <p className="brand-tagline">
              Self-verifying calendar agent with goal decomposition & conflict recovery
            </p>
          </div>
        </div>

        <div className="system-status-pills">
          <div className="status-pill" title="Backend Server Status">
            <span className={`status-dot ${healthInfo?.status === 'ok' ? 'online' : 'offline'}`} />
            <span className="pill-label">Backend:</span>
            <span className="pill-value">{healthInfo?.status === 'ok' ? 'Active' : 'Offline'}</span>
          </div>

          <div
            className="status-pill"
            title="Provider mode: Deterministic Dev Mode guarantees 100% testable, cost-free execution."
          >
            <Cpu size={14} className="pill-icon" />
            <span className="pill-label">Provider:</span>
            <span className="pill-value highlight">
              {healthInfo?.provider_mode === 'dev' ? 'Deterministic Dev' : 'OpenAI LLM'}
            </span>
          </div>

          <div className="status-pill" title="Timezone context">
            <Clock size={14} className="pill-icon" />
            <span className="pill-value">{healthInfo?.timezone || 'Asia/Kolkata'}</span>
          </div>
        </div>
      </div>

      <div className="header-controls">
        <div className="date-selector-group">
          <CalendarIcon size={16} className="text-muted" />
          <span className="control-label">Target Day:</span>
          <div className="quick-date-buttons">
            <button
              type="button"
              id="btn-date-today"
              className={`quick-date-btn ${targetDate === todayStr ? 'active' : ''}`}
              onClick={() => onDateChange(todayStr)}
            >
              Today
            </button>
            <button
              type="button"
              id="btn-date-tomorrow"
              className={`quick-date-btn ${targetDate === tomorrowStr ? 'active' : ''}`}
              onClick={() => onDateChange(tomorrowStr)}
            >
              Tomorrow
            </button>
          </div>
          <input
            type="date"
            id="target-date-picker"
            className="date-input"
            value={targetDate}
            onChange={(e) => onDateChange(e.target.value)}
          />
        </div>

        <div className="action-button-group">
          <button
            type="button"
            id="btn-history-toggle"
            className="btn-secondary"
            onClick={onToggleHistory}
            title="View Past Agent Runs"
          >
            <History size={16} />
            <span>Runs ({historyCount})</span>
          </button>

          <button
            type="button"
            id="btn-refresh-data"
            className="btn-secondary"
            onClick={onRefresh}
            disabled={isLoading}
            title="Refresh Calendar & Tasks"
          >
            <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
            <span>Sync</span>
          </button>

          <button
            type="button"
            id="btn-reset-demo"
            className={`btn-reset ${resetConfirm ? 'confirming' : ''}`}
            onClick={handleReset}
            disabled={resetting}
            title="Reset database to initial demo state (seeds standard events and tasks)"
          >
            <RotateCcw size={16} className={resetting ? 'animate-spin' : ''} />
            <span>{resetting ? 'Resetting...' : resetConfirm ? 'Confirm Reset?' : 'Demo Reset'}</span>
          </button>
        </div>
      </div>
    </header>
  )
}
