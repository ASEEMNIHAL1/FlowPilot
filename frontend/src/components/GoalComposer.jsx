import React, { useState } from 'react'
import { Play, Sparkles, AlertCircle, StopCircle, ArrowRight, Lightbulb } from 'lucide-react'

const PRESET_GOALS = [
  {
    label: 'Standard Benchmark (DSA + Project + Meeting)',
    goal: 'Plan tomorrow. I need two hours of DSA practice, three hours for my project, lunch, and a team meeting at 2 PM. Finish by 7 PM.',
  },
  {
    label: 'Conflict Recovery (Overlaps 10 AM Office Hours)',
    goal: 'Schedule an emergency 2-hour architecture review tomorrow at 10 AM, lunch at 12:30 PM, and 2 hours for project work before 6 PM.',
  },
  {
    label: 'Sprint Focus (Code Review + Demo + Deep Work)',
    goal: 'Tomorrow I need two hours of code review, lunch, a 1-hour sprint demo at 3 PM, and two hours of deep work before 6:30 PM.',
  },
]

export function GoalComposer({
  onRunAgent,
  isRunning,
  onCancelRun,
  currentRunId,
  targetDate,
}) {
  const [goal, setGoal] = useState(PRESET_GOALS[0].goal)
  const [error, setError] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!goal.trim()) {
      setError('Please provide a scheduling goal.')
      return
    }
    setError('')
    onRunAgent(goal.trim(), targetDate)
  }

  const handleSelectPreset = (presetGoal) => {
    setGoal(presetGoal)
    setError('')
  }

  return (
    <section className="goal-composer-card glass-panel">
      <div className="card-header">
        <div className="card-title-group">
          <div className="icon-badge">
            <Sparkles size={18} />
          </div>
          <div>
            <h2 className="card-title">Autonomous Mission Dispatcher</h2>
            <p className="card-subtitle">
              Provide natural-language instructions. The agent parses requirements, queries calendar state,
              recovers from conflicts, and commits verified events.
            </p>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="goal-form">
        <div className="textarea-wrapper">
          <textarea
            id="agent-goal-input"
            className="goal-textarea"
            rows={4}
            value={goal}
            onChange={(e) => {
              setGoal(e.target.value)
              if (error) setError('')
            }}
            placeholder="E.g., Plan tomorrow. I need two hours of DSA practice, three hours for my project, lunch, and a team meeting at 2 PM. Finish by 7 PM."
            disabled={isRunning}
          />
        </div>

        {error && (
          <div className="form-error">
            <AlertCircle size={15} />
            <span>{error}</span>
          </div>
        )}

        <div className="presets-section">
          <div className="presets-label">
            <Lightbulb size={14} className="text-muted" />
            <span>Sample Benchmarks:</span>
          </div>
          <div className="presets-list">
            {PRESET_GOALS.map((preset, idx) => (
              <button
                key={idx}
                type="button"
                className={`preset-pill ${goal === preset.goal ? 'active' : ''}`}
                onClick={() => handleSelectPreset(preset.goal)}
                disabled={isRunning}
              >
                <span>{preset.label}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="form-footer">
          <div className="target-date-notice">
            <span>Targeting:</span>
            <strong>{targetDate}</strong>
          </div>

          <div className="cta-actions">
            {isRunning ? (
              <button
                type="button"
                id="btn-cancel-run"
                className="btn-danger"
                onClick={onCancelRun}
              >
                <StopCircle size={16} />
                <span>Cancel Execution</span>
              </button>
            ) : null}

            <button
              type="submit"
              id="btn-execute-run"
              className={`btn-primary ${isRunning ? 'pulse-glow' : ''}`}
              disabled={isRunning || !goal.trim()}
            >
              {isRunning ? (
                <>
                  <span className="loading-spinner" />
                  <span>Agent Executing...</span>
                </>
              ) : (
                <>
                  <Play size={16} fill="currentColor" />
                  <span>Dispatch Agent</span>
                  <ArrowRight size={15} />
                </>
              )}
            </button>
          </div>
        </div>
      </form>
    </section>
  )
}
