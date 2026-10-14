import React from 'react'
import {
  FileText,
  CheckCircle,
  HelpCircle,
  Info,
  CalendarCheck,
  Cpu,
  Sparkles,
} from 'lucide-react'

export function FinalReportCard({ finalReport, runStatus }) {
  if (!finalReport) return null

  const {
    outcome,
    provider_mode,
    assistant_summary,
    target_date,
    scheduled_titles = [],
    documented_defaults = [],
    tool_call_count,
    notes = [],
  } = finalReport

  return (
    <section className="report-card glass-panel">
      <div className="card-header">
        <div className="card-title-group">
          <div className="icon-badge">
            <FileText size={18} />
          </div>
          <div>
            <div className="title-with-pill">
              <h2 className="card-title">Mission Synthesis & Evidence</h2>
              <span className={`badge ${outcome === 'verified' ? 'badge-success' : 'badge-primary'}`}>
                {outcome?.toUpperCase() || runStatus?.toUpperCase()}
              </span>
            </div>
            <p className="card-subtitle">
              Generated from tool observations and verified SQLite state.
            </p>
          </div>
        </div>
      </div>

      <div className="report-body">
        {/* Assistant Summary */}
        <div className="summary-callout">
          <p className="summary-text">{assistant_summary}</p>
        </div>

        {/* Scheduled Titles Chips */}
        {scheduled_titles.length > 0 && (
          <div className="report-section">
            <h3 className="section-mini-heading">
              <CalendarCheck size={14} />
              <span>Confirmed Calendar Commitments:</span>
            </h3>
            <div className="tags-wrap">
              {scheduled_titles.map((title, idx) => (
                <span key={idx} className="tag-chip tag-chip-primary">
                  {title}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Documented Defaults Applied */}
        {documented_defaults.length > 0 && (
          <div className="report-section">
            <h3 className="section-mini-heading">
              <Info size={14} />
              <span>Documented Scheduling Defaults:</span>
            </h3>
            <ul className="defaults-list">
              {documented_defaults.map((def, idx) => (
                <li key={idx} className="default-item">
                  <span className="bullet-dot" />
                  <span>{def}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Metadata Footer */}
        <div className="report-footer-meta">
          <div className="meta-pill">
            <Cpu size={13} />
            <span>Mode: {provider_mode === 'dev' ? 'Deterministic Planner' : 'OpenAI'}</span>
          </div>
          <div className="meta-pill">
            <Sparkles size={13} />
            <span>{tool_call_count} Tool Interactions</span>
          </div>
        </div>
      </div>
    </section>
  )
}
