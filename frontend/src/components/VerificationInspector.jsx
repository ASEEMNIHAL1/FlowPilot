import React from 'react'
import {
  ShieldCheck,
  ShieldX,
  Check,
  X,
  Info,
  Clock,
  Database,
  FileCheck2,
} from 'lucide-react'

export function VerificationInspector({ verification, finalReport }) {
  if (!verification && !finalReport) {
    return (
      <section className="verification-card glass-panel">
        <div className="card-header">
          <div className="card-title-group">
            <div className="icon-badge">
              <ShieldCheck size={18} />
            </div>
            <div>
              <h2 className="card-title">Independent Verification Engine</h2>
              <p className="card-subtitle">
                Independent SQLite audit ensuring persistence, conflict-free bounds, and goal compliance.
              </p>
            </div>
          </div>
        </div>
        <div className="empty-verification-state">
          <Database size={36} className="text-muted" />
          <p>No verification report generated yet.</p>
          <span className="text-muted text-sm">
            Execute an agent run to view independent cryptographic audit proofs against SQLite.
          </span>
        </div>
      </section>
    )
  }

  const isPassed = verification ? verification.passed : finalReport?.verification_passed
  const checks = verification?.checks || []
  const evidence = verification?.evidence || {}

  return (
    <section className="verification-card glass-panel">
      <div className="card-header">
        <div className="card-title-group">
          <div className="icon-badge">
            <ShieldCheck size={18} />
          </div>
          <div>
            <div className="title-with-pill">
              <h2 className="card-title">Independent Verification</h2>
              <span className={`badge ${isPassed ? 'badge-success' : 'badge-danger'}`}>
                {isPassed ? (
                  <>
                    <ShieldCheck size={12} />
                    Audit Passed
                  </>
                ) : (
                  <>
                    <ShieldX size={12} />
                    Audit Failed
                  </>
                )}
              </span>
            </div>
            <p className="card-subtitle">
              Verified directly against persisted SQLite rows (isolated from model assumptions).
            </p>
          </div>
        </div>
      </div>

      <div className="verification-content">
        {/* Verification Summary Banner */}
        <div className={`verification-summary-banner ${isPassed ? 'banner-success' : 'banner-danger'}`}>
          <div className="banner-icon">
            {isPassed ? <FileCheck2 size={24} /> : <ShieldX size={24} />}
          </div>
          <div className="banner-text">
            <strong>
              {isPassed
                ? 'All SQLite persistence and constraint checks passed.'
                : 'Verification detected discrepancies in scheduled state.'}
            </strong>
            <p>
              Target Date: <code>{verification?.target_date || finalReport?.target_date || 'N/A'}</code>
            </p>
          </div>
        </div>

        {/* Itemized Checks */}
        {checks.length > 0 && (
          <div className="checks-list-container">
            <h3 className="section-mini-heading">Audit Checklist ({checks.length} Checks)</h3>
            <div className="checks-list">
              {checks.map((check, idx) => (
                <div
                  key={idx}
                  id={`verification-check-${idx}`}
                  className={`check-item ${check.passed ? 'check-passed' : 'check-failed'}`}
                >
                  <div className="check-status-icon">
                    {check.passed ? <Check size={15} /> : <X size={15} />}
                  </div>
                  <div className="check-details">
                    <div className="check-name-row">
                      <strong className="check-name">{check.name.replace(/_/g, ' ')}</strong>
                      <span className={`badge-sm ${check.passed ? 'text-success' : 'text-danger'}`}>
                        {check.passed ? 'PASS' : 'FAIL'}
                      </span>
                    </div>
                    <p className="check-description">{check.description}</p>
                    {check.details && <p className="check-details-text">{check.details}</p>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Evidence details */}
        {evidence && (evidence.scheduled_titles || evidence.missing_titles) && (
          <div className="evidence-container">
            <h3 className="section-mini-heading">SQLite Evidence</h3>
            <div className="evidence-grid">
              {evidence.scheduled_titles && (
                <div className="evidence-box">
                  <span className="evidence-label">Persisted Events:</span>
                  <div className="tags-wrap">
                    {evidence.scheduled_titles.map((title, i) => (
                      <span key={i} className="tag-chip tag-chip-success">
                        {title}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {evidence.missing_titles && evidence.missing_titles.length > 0 && (
                <div className="evidence-box">
                  <span className="evidence-label">Missing Items:</span>
                  <div className="tags-wrap">
                    {evidence.missing_titles.map((title, i) => (
                      <span key={i} className="tag-chip tag-chip-danger">
                        {title}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
