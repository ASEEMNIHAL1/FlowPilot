import React, { useState, useEffect, useCallback } from 'react'
import { api } from './api/client'
import { Header } from './components/Header'
import { GoalComposer } from './components/GoalComposer'
import { TimelineCalendar } from './components/TimelineCalendar'
import { ExecutionTrace } from './components/ExecutionTrace'
import { VerificationInspector } from './components/VerificationInspector'
import { FinalReportCard } from './components/FinalReportCard'
import { TaskBacklog } from './components/TaskBacklog'
import { RunHistoryModal } from './components/RunHistoryModal'
import { CheckCircle2, AlertCircle, Info } from 'lucide-react'
import './App.css'

export default function App() {
  // Tomorrow's date ISO string YYYY-MM-DD
  const getTomorrowStr = () => {
    const d = new Date()
    d.setDate(d.getDate() + 1)
    return d.toISOString().split('T')[0]
  }

  const [targetDate, setTargetDate] = useState(getTomorrowStr)
  const [healthInfo, setHealthInfo] = useState(null)
  const [calendarEvents, setCalendarEvents] = useState([])
  const [tasks, setTasks] = useState([])
  const [runs, setRuns] = useState([])

  const [currentRun, setCurrentRun] = useState(null)
  const [currentRunEvents, setCurrentRunEvents] = useState([])
  const [currentVerification, setCurrentVerification] = useState(null)

  const [isRunning, setIsRunning] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [showHistoryModal, setShowHistoryModal] = useState(false)
  const [toast, setToast] = useState(null)

  const showToast = (message, type = 'info') => {
    setToast({ message, type })
    setTimeout(() => {
      setToast(null)
    }, 4500)
  }

  // Load calendar events for selected targetDate
  const loadCalendar = useCallback(async (date) => {
    try {
      const data = await api.getCalendar(date)
      setCalendarEvents(data.events || [])
    } catch (err) {
      console.error('Failed to load calendar:', err)
    }
  }, [])

  // Load all foundational data
  const loadAllData = useCallback(async () => {
    setIsLoading(true)
    try {
      const [demoInfo, tasksList, runsList] = await Promise.all([
        api.getDemoInfo().catch(() => ({ status: 'error' })),
        api.getTasks().catch(() => []),
        api.listRuns().catch(() => []),
      ])
      setHealthInfo(demoInfo)
      setTasks(tasksList)
      setRuns(runsList)

      // If we don't have an active current run yet and historical runs exist, load the latest
      if (!currentRun && runsList.length > 0) {
        const latest = runsList[0]
        setCurrentRun(latest)
        try {
          const [events, verification] = await Promise.all([
            api.getRunEvents(latest.id).catch(() => []),
            api.getRunVerification(latest.id).catch(() => null),
          ])
          setCurrentRunEvents(events)
          setCurrentVerification(verification)
        } catch {
          // Ignore
        }
      }
    } finally {
      setIsLoading(false)
    }
  }, [currentRun])

  // Initial load
  useEffect(() => {
    loadAllData()
  }, [])

  // When target date changes, refresh calendar
  useEffect(() => {
    loadCalendar(targetDate)
  }, [targetDate, loadCalendar])

  // Handle Dispatching Agent Run
  const handleRunAgent = async (goal, date) => {
    setIsRunning(true)
    setCurrentRunEvents([])
    setCurrentVerification(null)
    try {
      const runSummary = await api.runAgent(goal, date)
      setCurrentRun(runSummary)

      // Refresh calendar immediately to show newly committed/rearranged items
      await loadCalendar(runSummary.target_date || date)

      // Fetch tool logs and independent verification proofs
      const [events, verification, updatedRuns] = await Promise.all([
        api.getRunEvents(runSummary.id).catch(() => []),
        api.getRunVerification(runSummary.id).catch(() => null),
        api.listRuns().catch(() => []),
      ])

      setCurrentRunEvents(events)
      setCurrentVerification(verification)
      setRuns(updatedRuns)

      if (runSummary.status === 'verified') {
        showToast('Autonomous run verified and persisted in SQLite!', 'success')
      } else {
        showToast(`Run completed with status: ${runSummary.status}`, 'info')
      }
    } catch (err) {
      console.error('Agent run failed:', err)
      showToast(err.message || 'Execution error encountered', 'error')
    } finally {
      setIsRunning(false)
    }
  }

  // Handle Cancel Agent Run
  const handleCancelRun = async () => {
    if (!currentRun?.id) return
    try {
      await api.cancelRun(currentRun.id)
      showToast('Agent cancellation requested', 'info')
      setIsRunning(false)
    } catch (err) {
      showToast(err.message || 'Failed to cancel run', 'error')
    }
  }

  // Handle Adding Calendar Event manually
  const handleAddEvent = async (eventData) => {
    try {
      await api.createEvent(eventData)
      await loadCalendar(targetDate)
      showToast(`Added: ${eventData.title}`, 'success')
    } catch (err) {
      showToast(err.message || 'Failed to create event', 'error')
      throw err
    }
  }

  // Handle Deleting Calendar Event
  const handleDeleteEvent = async (eventId) => {
    try {
      await api.deleteEvent(eventId)
      await loadCalendar(targetDate)
      showToast('Event removed', 'info')
    } catch (err) {
      showToast(err.message || 'Failed to delete event', 'error')
    }
  }

  // Handle Demo Reset
  const handleResetDemo = async () => {
    try {
      const res = await api.resetDemoData()
      await Promise.all([loadCalendar(targetDate), loadAllData()])
      showToast(
        `Database reset: ${res.created_events} events and ${res.created_tasks} tasks restored.`,
        'success'
      )
    } catch (err) {
      showToast(err.message || 'Failed to reset demo data', 'error')
    }
  }

  // Handle Selecting a Historical Run
  const handleSelectHistoricalRun = async (runId) => {
    try {
      const [runData, events, verification] = await Promise.all([
        api.getRun(runId),
        api.getRunEvents(runId).catch(() => []),
        api.getRunVerification(runId).catch(() => null),
      ])
      setCurrentRun(runData)
      setCurrentRunEvents(events)
      setCurrentVerification(verification)
      if (runData.target_date && runData.target_date !== targetDate) {
        setTargetDate(runData.target_date)
      }
      showToast(`Loaded Run #${runId}`, 'info')
    } catch (err) {
      showToast(err.message || 'Failed to load historical run', 'error')
    }
  }

  return (
    <div className="app-container">
      {/* Top Header */}
      <Header
        healthInfo={healthInfo}
        onResetDemo={handleResetDemo}
        onRefresh={() => {
          loadAllData()
          loadCalendar(targetDate)
        }}
        isLoading={isLoading}
        targetDate={targetDate}
        onDateChange={setTargetDate}
        onToggleHistory={() => setShowHistoryModal(true)}
        historyCount={runs.length}
      />

      {/* Main 2-Column Command Center */}
      <main className="grid-main">
        {/* Left Column: Mission Dispatcher, Live Trace, and Verification Inspector */}
        <div className="column-left" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <GoalComposer
            onRunAgent={handleRunAgent}
            isRunning={isRunning}
            onCancelRun={handleCancelRun}
            currentRunId={currentRun?.id}
            targetDate={targetDate}
          />

          {currentRun?.final_report && (
            <FinalReportCard
              finalReport={currentRun.final_report}
              runStatus={currentRun.status}
            />
          )}

          <VerificationInspector
            verification={currentVerification}
            finalReport={currentRun?.final_report}
          />

          <ExecutionTrace
            toolLogs={currentRunEvents}
            isRunning={isRunning}
            runStatus={currentRun?.status}
          />
        </div>

        {/* Right Column: Interactive Calendar Timeline and Backlog Tasks */}
        <div className="column-right" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <TimelineCalendar
            events={calendarEvents}
            targetDate={targetDate}
            onDeleteEvent={handleDeleteEvent}
            onAddEvent={handleAddEvent}
            isLoading={isLoading}
            workingHours={{
              start: healthInfo?.work_start || '09:00',
              end: healthInfo?.work_end || '19:00',
              lunchStart: healthInfo?.lunch_start || '12:00',
              lunchEnd: healthInfo?.lunch_end || '13:00',
            }}
          />

          <TaskBacklog
            tasks={tasks}
            onSelectTask={(task) => {
              showToast(`Task "${task.title}" selected`, 'info')
            }}
          />
        </div>
      </main>

      {/* History Modal */}
      {showHistoryModal && (
        <RunHistoryModal
          runs={runs}
          onClose={() => setShowHistoryModal(false)}
          onSelectRun={handleSelectHistoricalRun}
          selectedRunId={currentRun?.id}
        />
      )}

      {/* Toast Notification Container */}
      {toast && (
        <div className="toast-container">
          <div className={`toast toast-${toast.type}`}>
            {toast.type === 'success' ? (
              <CheckCircle2 size={16} />
            ) : toast.type === 'error' ? (
              <AlertCircle size={16} />
            ) : (
              <Info size={16} />
            )}
            <span>{toast.message}</span>
          </div>
        </div>
      )}
    </div>
  )
}
