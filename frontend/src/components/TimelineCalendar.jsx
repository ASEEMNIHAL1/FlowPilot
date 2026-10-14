import React, { useState } from 'react'
import {
  Calendar as CalendarIcon,
  Clock,
  Lock,
  Trash2,
  Plus,
  Coffee,
  CheckCircle,
  AlertCircle,
  Sparkles,
} from 'lucide-react'

export function TimelineCalendar({
  events = [],
  targetDate,
  onDeleteEvent,
  onAddEvent,
  isLoading,
  workingHours = { start: '09:00', end: '19:00', lunchStart: '12:00', lunchEnd: '13:00' },
}) {
  const [showAddModal, setShowAddModal] = useState(false)
  const [newEventTitle, setNewEventTitle] = useState('')
  const [newEventStart, setNewEventStart] = useState('11:00')
  const [newEventEnd, setNewEventEnd] = useState('12:00')
  const [newEventFixed, setNewEventFixed] = useState(false)
  const [addError, setAddError] = useState('')

  // Sort events chronologically
  const sortedEvents = [...events].sort((a, b) => {
    return new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
  })

  // Format time (e.g. "14:00" or "02:00 PM")
  const formatTime = (isoString) => {
    if (!isoString) return ''
    try {
      const d = new Date(isoString)
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
    } catch {
      return isoString.split('T')[1]?.substring(0, 5) || isoString
    }
  }

  // Calculate duration in minutes
  const getDuration = (startIso, endIso) => {
    try {
      const diffMs = new Date(endIso).getTime() - new Date(startIso).getTime()
      return Math.round(diffMs / 60000)
    } catch {
      return 0
    }
  }

  const handleCreateSubmit = async (e) => {
    e.preventDefault()
    setAddError('')
    if (!newEventTitle.trim()) {
      setAddError('Title is required')
      return
    }
    const startIso = `${targetDate}T${newEventStart}:00+05:30`
    const endIso = `${targetDate}T${newEventEnd}:00+05:30`

    if (newEventEnd <= newEventStart) {
      setAddError('End time must be after start time')
      return
    }

    try {
      await onAddEvent({
        title: newEventTitle.trim(),
        start_time: startIso,
        end_time: endIso,
        is_fixed: newEventFixed,
        description: 'Manual schedule item',
      })
      setShowAddModal(false)
      setNewEventTitle('')
    } catch (err) {
      setAddError(err.message || 'Failed to add event')
    }
  }

  // Calculate total minutes booked
  const totalBookedMinutes = sortedEvents.reduce((acc, ev) => acc + getDuration(ev.start_time, ev.end_time), 0)
  const totalBookedHours = (totalBookedMinutes / 60).toFixed(1)

  return (
    <section className="timeline-card glass-panel">
      <div className="card-header">
        <div className="card-title-group">
          <div className="icon-badge">
            <CalendarIcon size={18} />
          </div>
          <div>
            <div className="title-with-pill">
              <h2 className="card-title">Calendar Timeline</h2>
              <span className="badge badge-neutral">{targetDate}</span>
            </div>
            <p className="card-subtitle">
              Live SQLite calendar state. Working hours {workingHours.start}–{workingHours.end} with lunch break.
            </p>
          </div>
        </div>

        <div className="timeline-actions">
          <button
            type="button"
            id="btn-add-event-toggle"
            className="btn-secondary"
            onClick={() => setShowAddModal(!showAddModal)}
          >
            <Plus size={16} />
            <span>Add Block</span>
          </button>
        </div>
      </div>

      {/* Timeline quick stats bar */}
      <div className="timeline-stats-bar">
        <div className="stat-item">
          <span className="stat-label">Total Events</span>
          <span className="stat-value">{sortedEvents.length}</span>
        </div>
        <div className="stat-divider" />
        <div className="stat-item">
          <span className="stat-label">Scheduled Time</span>
          <span className="stat-value">{totalBookedHours} hrs</span>
        </div>
        <div className="stat-divider" />
        <div className="stat-item">
          <span className="stat-label">Fixed Protected</span>
          <span className="stat-value">{sortedEvents.filter((e) => e.is_fixed).length}</span>
        </div>
      </div>

      {/* Manual Event Creation Modal / Dropdown */}
      {showAddModal && (
        <form onSubmit={handleCreateSubmit} className="add-event-form glass-panel">
          <div className="form-row">
            <input
              type="text"
              id="new-event-title"
              placeholder="Event Title (e.g. Architecture Sync)"
              className="form-input flex-1"
              value={newEventTitle}
              onChange={(e) => setNewEventTitle(e.target.value)}
              autoFocus
            />
          </div>
          <div className="form-row time-row">
            <div className="time-field">
              <label htmlFor="new-event-start">Start:</label>
              <input
                type="time"
                id="new-event-start"
                className="form-input"
                value={newEventStart}
                onChange={(e) => setNewEventStart(e.target.value)}
              />
            </div>
            <div className="time-field">
              <label htmlFor="new-event-end">End:</label>
              <input
                type="time"
                id="new-event-end"
                className="form-input"
                value={newEventEnd}
                onChange={(e) => setNewEventEnd(e.target.value)}
              />
            </div>
            <label className="checkbox-label">
              <input
                type="checkbox"
                id="new-event-fixed"
                checked={newEventFixed}
                onChange={(e) => setNewEventFixed(e.target.checked)}
              />
              <span>Fixed (Protected)</span>
            </label>
            <div className="modal-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setShowAddModal(false)}
              >
                Cancel
              </button>
              <button type="submit" id="btn-save-event" className="btn-primary">
                Save Block
              </button>
            </div>
          </div>
          {addError && (
            <div className="form-error">
              <AlertCircle size={14} />
              <span>{addError}</span>
            </div>
          )}
        </form>
      )}

      {/* Events List Timeline */}
      <div className="events-timeline-list">
        {sortedEvents.length === 0 ? (
          <div className="empty-timeline-state">
            <Clock size={36} className="text-muted" />
            <p>No calendar events scheduled for {targetDate}.</p>
            <span className="text-muted text-sm">
              Run the agent above or click "Add Block" to schedule items.
            </span>
          </div>
        ) : (
          sortedEvents.map((event) => {
            const startStr = formatTime(event.start_time)
            const endStr = formatTime(event.end_time)
            const durationMins = getDuration(event.start_time, event.end_time)
            const isLunch = event.title.toLowerCase().includes('lunch')
            const isAgent = event.source === 'agent'

            return (
              <div
                key={event.id}
                id={`calendar-event-${event.id}`}
                className={`timeline-event-card ${
                  event.is_fixed ? 'event-fixed' : isLunch ? 'event-break' : isAgent ? 'event-agent' : ''
                }`}
              >
                <div className="event-time-column">
                  <div className="event-time-range">
                    <span className="time-start">{startStr}</span>
                    <span className="time-dash">–</span>
                    <span className="time-end">{endStr}</span>
                  </div>
                  <span className="event-duration">{durationMins}m</span>
                </div>

                <div className="event-content-column">
                  <div className="event-title-row">
                    <h3 className="event-title">{event.title}</h3>

                    <div className="event-badges-row">
                      {event.is_fixed ? (
                        <span className="badge badge-danger" title="Fixed item: Protected against overwrite or deletion">
                          <Lock size={11} />
                          Fixed
                        </span>
                      ) : null}

                      {isAgent ? (
                        <span className="badge badge-primary" title="Created autonomously by agent">
                          <Sparkles size={11} />
                          Agent
                        </span>
                      ) : null}

                      {isLunch ? (
                        <span className="badge badge-warning" title="Scheduled Break">
                          <Coffee size={11} />
                          Break
                        </span>
                      ) : null}
                    </div>
                  </div>

                  {event.description && <p className="event-desc">{event.description}</p>}
                </div>

                <div className="event-action-column">
                  {!event.is_fixed ? (
                    <button
                      type="button"
                      id={`btn-delete-event-${event.id}`}
                      className="icon-action-btn delete-btn"
                      title="Remove event (creates free slot)"
                      onClick={() => onDeleteEvent(event.id)}
                    >
                      <Trash2 size={15} />
                    </button>
                  ) : (
                    <span className="lock-icon-indicator" title="Protected: cannot be removed without force">
                      <Lock size={15} className="text-muted" />
                    </span>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>
    </section>
  )
}
