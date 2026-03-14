import { useState, useEffect, useRef, useCallback } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'

const STATUS_CONFIG = {
  queued: { color: '#555', label: 'Queued' },
  dialing: { color: '#FBBF24', label: 'Dialing' },
  speaking: { color: '#60A5FA', label: 'On Call' },
  waiting: { color: '#A78BFA', label: 'Hold' },
  extracting: { color: '#818CF8', label: 'Processing' },
  finished: { color: '#34D399', label: 'Done' },
  failed: { color: '#F87171', label: 'Failed' },
}

function CallWidget({ agent, index }) {
  const config = STATUS_CONFIG[agent.status] || STATUS_CONFIG.queued
  const isActive = ['dialing', 'speaking', 'extracting'].includes(agent.status)
  const isDone = agent.status === 'finished'
  const isFailed = agent.status === 'failed'
  const transcriptRef = useRef(null)

  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight
    }
  }, [agent.transcript])

  const transcriptLines = (agent.transcript || '').split('\n').filter(l => l.trim())

  return (
    <div
      className={`call-widget ${isActive ? 'active' : ''} ${isDone ? 'done' : ''} ${isFailed ? 'failed' : ''}`}
      style={{ animationDelay: `${index * 0.08}s` }}
    >
      <div className="widget-top">
        <div className="widget-identity">
          <h3 className="widget-name">{agent.business_name}</h3>
          <span className="widget-phone">{agent.phone}</span>
        </div>
        <div className="widget-indicator" style={{ '--dot-color': config.color }}>
          {isActive && <span className="breathing-dot" />}
          <span className="indicator-label">{config.label}</span>
        </div>
      </div>

      {agent.error && <div className="widget-error">{agent.error}</div>}

      {isDone && agent.result?.available && (
        <div className="widget-availability">
          <span className="avail-label">Available</span>
          {agent.result.times?.length > 0 && (
            <span className="avail-times">{agent.result.times.join(' \u00b7 ')}</span>
          )}
          {agent.result.walk_in && <span className="avail-walkin">Walk-ins OK</span>}
          {agent.result.notes && <span className="avail-notes">{agent.result.notes}</span>}
        </div>
      )}

      <div className="widget-transcript-area" ref={transcriptRef}>
        {transcriptLines.length > 0 ? (
          transcriptLines.map((line, i) => {
            const isAgent = /^agent:/i.test(line) || /^assistant:/i.test(line)
            const isBiz = /^business:/i.test(line) || /^user:/i.test(line)
            return (
              <div
                key={i}
                className={`t-line ${isAgent ? 'agent-line' : ''} ${isBiz ? 'biz-line' : ''} ${i === transcriptLines.length - 1 ? 'newest' : ''}`}
              >
                {line}
              </div>
            )
          })
        ) : (
          <div className="t-placeholder">
            {agent.status === 'queued' && 'Waiting in queue...'}
            {agent.status === 'dialing' && 'Ringing...'}
            {agent.status === 'speaking' && 'Call in progress...'}
            {agent.status === 'extracting' && 'Analyzing conversation...'}
            {agent.status === 'waiting' && 'On hold...'}
            {agent.status === 'finished' && !agent.transcript && 'Call complete'}
            {agent.status === 'failed' && 'Call failed'}
          </div>
        )}
      </div>
    </div>
  )
}

function App() {
  const [view, setView] = useState('chat')
  const [tasks, setTasks] = useState({})
  const [activeTaskId, setActiveTaskId] = useState(null)
  const [query, setQuery] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [connected, setConnected] = useState(false)
  const [transitioning, setTransitioning] = useState(false)
  const [demo, setDemo] = useState(false)
  const wsRef = useRef(null)
  const inputRef = useRef(null)

  const connectWs = useCallback(() => {
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws
    ws.onopen = () => setConnected(true)
    ws.onclose = () => {
      setConnected(false)
      setTimeout(connectWs, 2000)
    }
    ws.onerror = () => ws.close()
    ws.onmessage = (event) => {
      try {
        const task = JSON.parse(event.data)
        if (task.task_id) {
          setTasks(prev => ({ ...prev, [task.task_id]: task }))
        }
      } catch { /* ignore */ }
    }
  }, [])

  useEffect(() => {
    connectWs()
    return () => wsRef.current?.close()
  }, [connectWs])

  useEffect(() => {
    if (view === 'chat' && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 300)
    }
  }, [view])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim() || submitting) return
    setSubmitting(true)
    try {
      const res = await fetch(`${API_URL}/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim(), demo }),
      })
      const task = await res.json()
      setTasks(prev => ({ ...prev, [task.task_id]: task }))
      setActiveTaskId(task.task_id)
      setTransitioning(true)
      setTimeout(() => {
        setView('dashboard')
        setQuery('')
        setTransitioning(false)
      }, 400)
    } catch (err) {
      console.error('Failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  const handleBack = () => {
    setTransitioning(true)
    setTimeout(() => {
      setView('chat')
      setActiveTaskId(null)
      setTransitioning(false)
    }, 300)
  }

  const activeTask = activeTaskId ? tasks[activeTaskId] : null
  const agents = activeTask?.agents || []
  const activeCount = agents.filter(a => ['dialing', 'speaking', 'extracting'].includes(a.status)).length
  const doneCount = agents.filter(a => a.status === 'finished').length
  const isComplete = activeTask?.status === 'task_complete'
  const isFailed = activeTask?.status === 'task_failed'

  return (
    <div className={`app ${transitioning ? 'transitioning' : ''}`}>
      <div className={`conn-indicator ${connected ? 'on' : 'off'}`} title={connected ? 'Connected' : 'Disconnected'} />

      {view === 'chat' && (
        <div className="chat-screen">
          <div className="chat-content">
            <div className="brand-block">
              <h1 className="brand-name">CallSwarm</h1>
              <p className="brand-tagline">Tell me what you need. I'll call every place and get you answers.</p>
            </div>
            <form className="prompt-form" onSubmit={handleSubmit}>
              <div className="prompt-field">
                <input
                  ref={inputRef}
                  type="text"
                  className="prompt-input"
                  placeholder="Find me a haircut in downtown SF today..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  disabled={submitting}
                  autoComplete="off"
                />
                <button
                  type="submit"
                  className="prompt-send"
                  disabled={submitting || !query.trim()}
                  aria-label="Send"
                >
                  {submitting ? (
                    <span className="spin-icon" />
                  ) : (
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="5" y1="12" x2="19" y2="12" />
                      <polyline points="12 5 19 12 12 19" />
                    </svg>
                  )}
                </button>
              </div>
            </form>
            <button
              className={`demo-toggle ${demo ? 'on' : ''}`}
              onClick={() => setDemo(d => !d)}
              type="button"
            >
              {demo ? 'Demo Mode ON' : 'Demo Mode'}
            </button>
          </div>
        </div>
      )}

      {view === 'dashboard' && (
        <div className="dash-screen">
          <header className="dash-bar">
            <button className="btn-back" onClick={handleBack} aria-label="Back">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="19" y1="12" x2="5" y2="12" />
                <polyline points="12 19 5 12 12 5" />
              </svg>
              <span>Back</span>
            </button>
            <div className="bar-center">
              <span className="bar-query">{activeTask?.query || '...'}</span>
              <div className="bar-meta">
                {!isComplete && !isFailed && (
                  <>
                    <span className="meta-item live"><span className="live-dot" /> {activeCount} calling</span>
                    <span className="meta-item">{doneCount}/{agents.length} done</span>
                  </>
                )}
                {isComplete && <span className="meta-item complete">Complete</span>}
                {isFailed && <span className="meta-item error">Failed</span>}
              </div>
            </div>
            <div className="bar-spacer" />
          </header>

          <main className="dash-body">
            {agents.length > 0 ? (
              <div className="widgets-grid">
                {agents.map((agent, i) => (
                  <CallWidget key={agent.agent_id || i} agent={agent} index={i} />
                ))}
              </div>
            ) : (
              <div className="dash-loading">
                <span className="spin-icon large" />
                <p>Searching for businesses...</p>
              </div>
            )}

            {activeTask?.summary && (
              <div className="summary-panel">
                <div className="summary-label">Summary</div>
                <p className="summary-body">{activeTask.summary}</p>
              </div>
            )}
          </main>
        </div>
      )}
    </div>
  )
}

export default App
