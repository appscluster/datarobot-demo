import React from 'react'
import { getApiBase, getRunsBase } from './config'
import { go } from './auth'

type Finding = {
  finding_id: string
  node_id: string
  title: string
  severity: string
  status: string
  asset_ids: string[]
  asset_label?: string | null
  updated_at: string
  source_tool?: string | null
  approvable?: boolean
}

const TOOL_LABEL: Record<string, string> = {gitleaks: 'Gitleaks', trufflehog: 'TruffleHog', trivy: 'Trivy', semgrep: 'Semgrep', prowler: 'Prowler'}
const CONSOLE_MIN = 96
const CONSOLE_MAX = 520

function clampConsole(height: number): number {
  return Math.min(CONSOLE_MAX, Math.max(CONSOLE_MIN, Math.round(height)))
}

function storedConsoleHeight(): number {
  const fallback = typeof window !== 'undefined' && window.matchMedia('(max-width: 1024px)').matches ? 180 : 148
  try {
    const saved = sessionStorage.getItem('casework-console-h')
    const n = saved ? Number(saved) : NaN
    return Number.isFinite(n) ? clampConsole(n) : fallback
  } catch {
    return fallback
  }
}
function ToolBadge({tool}:{tool?: string | null}) {
  if (!tool) return null
  return <span className="pill tool-badge" data-tool={tool} title={`Source: ${TOOL_LABEL[tool] || tool} (open source scanner)`}>{TOOL_LABEL[tool] || tool}</span>
}

type RunEvent = { event: string; data: any }

export function App({ onSignOut }: { onSignOut?: () => void }) {
  const [session, setSession] = React.useState<any>(null)
  const [findings, setFindings] = React.useState<Finding[]>([])
  const [selected, setSelected] = React.useState<string | null>(null)
  const [detail, setDetail] = React.useState<any>(null)
  const [subgraph, setSubgraph] = React.useState<any>(null)
  const [catalog, setCatalog] = React.useState<any>(null)
  const [risk, setRisk] = React.useState<any>(null)
  const [draft, setDraft] = React.useState<any>(null)
  const [events, setEvents] = React.useState<RunEvent[]>([])
  const [audit, setAudit] = React.useState<any[]>([])
  const [scopeText, setScopeText] = React.useState('')
  const [scopeVerdict, setScopeVerdict] = React.useState<any>(null)
  const [loading, setLoading] = React.useState(false)
  const [lastRunId, setLastRunId] = React.useState<string | null>(null)
  const [severityFilter, setSeverityFilter] = React.useState<string>('all')
  const [isMobile, setIsMobile] = React.useState<boolean>(false)
  const [activeMobileTab, setActiveMobileTab] = React.useState<'overview'|'run'|'graph'>('overview')
  const [eventTimes, setEventTimes] = React.useState<number[]>([])
  const [expanded, setExpanded] = React.useState<Record<number, boolean>>({})
  const [running, setRunning] = React.useState(false)
  const [decisionNote, setDecisionNote] = React.useState<string | null>(null)
  const [consoleHeight, setConsoleHeight] = React.useState(storedConsoleHeight)
  const consoleDrag = React.useRef<{ y: number; h: number } | null>(null)
  const traceRef = React.useRef<HTMLDivElement | null>(null)
  const consoleRef = React.useRef<HTMLDivElement | null>(null)
  const runToken = React.useRef(0)
  const streamRef = React.useRef<EventSource | null>(null)

  const API = React.useMemo(()=> getApiBase(), [])
  const RUNS = React.useMemo(()=> getRunsBase(), [])

  React.useEffect(() => {
    fetch(`${API}/api/session`).then(r => r.json()).then(setSession).catch(()=>{})
    fetch(`${API}/api/findings`).then(r => r.json()).then(d => setFindings(d.findings || [])).catch(()=>{})
    fetch(`${API}/api/audit`).then(r => r.json()).then(d => setAudit(d.audit || [])).catch(()=>{})
    fetch(`${API}/api/graph`).then(r => r.json()).then(setCatalog).catch(()=>{})
  }, [API])

  React.useEffect(() => {
    if (isMobile || selected || findings.length === 0) return
    setSelected(findings[0].finding_id)
  }, [findings, isMobile, selected])

  React.useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)')
    const fn = () => setIsMobile(mq.matches)
    fn()
    mq.addEventListener('change', fn)
    return () => mq.removeEventListener('change', fn)
  }, [])

  React.useEffect(() => {
    if (!selected) return
    runToken.current += 1
    streamRef.current?.close()
    streamRef.current = null
    setRunning(false)
    setDecisionNote(null)
    setScopeVerdict(null)
    setDetail(null); setSubgraph(null); setRisk(null); setDraft(null); setEvents([]); setEventTimes([]); setExpanded({})
    fetch(`${API}/api/findings/${selected}`).then(r => r.json()).then(d => setDetail(d.finding)).catch(()=>{})
    fetch(`${API}/api/graph/enrich`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({tenant_id: session?.tenant_id, finding_id: selected, k_hops: 3})})
      .then(r=>r.json()).then(d=> setSubgraph(d.subgraph)).catch(()=>{})
  }, [selected, session?.tenant_id, API])

  React.useEffect(() => {
    function onWin(e: KeyboardEvent) {
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
      if (!findings.length) return
      if (e.key !== 'j' && e.key !== 'k') return
      const idx = selected ? findings.findIndex(f=>f.finding_id===selected) : -1
      if (e.key === 'j') {
        const n = Math.min(idx+1, findings.length-1)
        setSelected(findings[n]?.finding_id ?? findings[0]?.finding_id)
      }
      if (e.key === 'k') {
        const n = Math.max(idx-1, 0)
        setSelected(findings[n]?.finding_id ?? findings[0]?.finding_id)
      }
    }
    window.addEventListener('keydown', onWin)
    return () => window.removeEventListener('keydown', onWin)
  }, [findings, selected])

  React.useEffect(() => {
    const last = traceRef.current?.querySelector('li:last-child')
    last?.scrollIntoView({block: 'nearest'})
    const log = consoleRef.current
    if (log) log.scrollTop = log.scrollHeight
  }, [events, decisionNote])

  async function triageRun() {
    if (!selected || running) return
    const token = ++runToken.current
    streamRef.current?.close()
    streamRef.current = null
    setRunning(true)
    setDecisionNote(null)
    setEvents([]); setRisk(null); setDraft(null); setEventTimes([]); setExpanded({})
    try {
      const resp = await fetch(`${API}/api/runs`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({finding_id: selected})})
      const body = await resp.json().catch(() => ({}))
      if (token !== runToken.current) return
      const runId = body.run_id
      if (!resp.ok || !runId) {
        setRunning(false)
        return
      }
      setLastRunId(runId)
      const es = new EventSource(`${RUNS}/runs/${runId}/events`)
      streamRef.current = es
      ;(window as any).__SSE_EVENTS__ = (window as any).__SSE_EVENTS__ || []
      const pushEvent = (kind: string, data: any) => {
        if (token !== runToken.current) return
        if (data && data.event === 'done') {
          es.close()
          if (streamRef.current === es) streamRef.current = null
          setRunning(false)
          return
        }
        if (data && data.error) {
          es.close()
          if (streamRef.current === es) streamRef.current = null
          setRunning(false)
        }
        if (data && (data.risk || data.draft)) {
          setRisk(data.risk); setDraft(data.draft); if (data.subgraph) setSubgraph(data.subgraph)
        }
        setEvents(prev => {
          if (data && data.seq && prev.some(e => e.data && e.data.seq === data.seq)) return prev
          setEventTimes(t => [...t, Date.now()])
          return [...prev, {event: kind, data}]
        })
        if (data && data.final) setRunning(false)
      }
      const onAny = (kindFallback: string) => (ev: MessageEvent) => {
        try {
          const data = JSON.parse(ev.data)
          const kind = (data && data.phase) ? 'step' : (data && data.final) ? 'final' : kindFallback
          try { console.log('[sse]', kind, (data && data.phase) ? data.phase : ''); } catch {}
          ;(window as any).__SSE_EVENTS__.push({event: kind, data})
          pushEvent(kind, data)
        } catch { /* ignore */ }
      }
      es.onmessage = onAny('message')
      es.addEventListener('step', onAny('step') as EventListener)
      es.addEventListener('final', onAny('final') as EventListener)
      es.onerror = () => {
        if (token !== runToken.current) return
        if (es.readyState === EventSource.CONNECTING) return
        setRunning(false)
      }
    } catch {
      if (token === runToken.current) setRunning(false)
    }
  }

  // Mirror rendered events into debug buffer to guarantee provenance capture
  React.useEffect(() => {
    try {
      (window as any).__SSE_EVENTS__ = (events || []).map(e => e)
    } catch {}
  }, [events])

  async function decide(decision: 'approve'|'reject'|'escalate') {
    if (!selected) return
    setLoading(true)
    try {
      const body = {tenant_id: session?.tenant_id, run_id: lastRunId, finding_id: selected, decision, actor: session?.actor, note: decision==='reject'?'Needs rework':''}
      const r = await fetch(`${API}/api/decisions`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)})
      if (r.status===403) {
        const v = await r.json()
        setDecisionNote(`Refused: ${v.reason}`)
        return
      }
      if (!r.ok) {
        setDecisionNote('The decision did not save.')
        return
      }
      const saved = await r.json()
      setDecisionNote(saved.delivery?.note || 'The decision did not save.')
    } finally {
      setLoading(false)
      refreshAudit()
    }
  }

  async function refreshAudit() {
    const r = await fetch(`${API}/api/audit`).then(r=>r.json()).catch(()=>({audit:[]}))
    setAudit(r.audit || [])
  }

  async function screenScope(action?: string, targetIds: string[] = []) {
    const requested = action ?? scopeText
    if (action !== undefined) setScopeText(action)
    const body = {tenant_id: session?.tenant_id, requested_action: requested, target_ids: targetIds}
    const v = await fetch(`${API}/api/check_scope`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)}).then(r=>r.json())
    setScopeVerdict(v.verdict)
    refreshAudit()
  }

  function formatRelative(iso: string): string {
    const t = new Date(iso).getTime()
    const now = Date.now()
    const s = Math.max(1, Math.round((now - t) / 1000))
    if (s < 60) return `${s}s ago`
    const m = Math.round(s / 60); if (m < 60) return `${m}m ago`
    const h = Math.round(m / 60); if (h < 24) return `${h}h ago`
    const d = Math.round(h / 24); return `${d}d ago`
  }

  function sevClass(s: string): string {
    const v = (s || '').toLowerCase()
    if (v === 'critical') return 'sev-critical'
    if (v === 'high') return 'sev-high'
    if (v === 'medium') return 'sev-medium'
    return 'sev-low'
  }

  const approveDisabled = !lastRunId || !risk || !draft
  const filtered = findings
    .filter(f => severityFilter==='all' ? true : (f.severity||'').toLowerCase()===severityFilter)
    .slice()
    .sort((a, b) => Number(Boolean(b.approvable)) - Number(Boolean(a.approvable)))
  const approvableCount = findings.filter(f => f.approvable).length

  function tenantDisplay(tid?: string): string {
    if (!tid) return ''
    if (tid.includes('tenant_demo_acme')) return 'Emirates NBD Demo'
    return tid
  }
  function actorDisplay(a?: string): {initials: string, name: string} {
    if (!a) return {initials:'AN', name:'Analyst'}
    if (a === 'analyst:demo-1') return {initials:'AD', name:'Demo analyst'}
    const tail = a.split(':').pop() || a
    return {initials: tail.substring(0,2).toUpperCase(), name: a}
  }
  const actor = actorDisplay(session?.actor)

  function auditLabel(a:any): string {
    if (!a) return ''
    if (a.tool === 'record_decision' && a.decision && String(a.decision).toLowerCase()==='allow') return 'Decision saved'
    if (a.tool === 'record_decision') return `Decision recorded`
    if (a.decision === 'allow' && a.reason === 'in_scope' && a.tool === 'check_scope') return 'Scope check passed'
    if (a.tool === 'get_finding' && a.decision === 'allow') return 'Finding loaded'
    if (a.tool === 'enrich_asset_graph' && a.decision === 'allow') return 'Asset graph enriched'
    if (a.tool === 'rank_risk' && a.decision === 'allow') return 'Risk ranked'
    if (a.tool === 'draft_remediation' && a.decision === 'allow') return 'Remediation drafted'
    if (a.tool === 'chat' && a.decision === 'allow') return 'Chat request checked'
    if (a.decision === 'refuse') return `Request blocked: ${a.reason}`
    return `${a.tool} ${a.decision}`
  }

  function stepTitle(phase?: string, tool?: string, final?: boolean): string {
    if (final) return 'Result'
    if (phase === 'planner') return 'Plan'
    if (phase === 'checker') return 'Check'
    if (phase === 'metrics') return 'Metrics'
    if (phase === 'monitoring') return 'Monitoring'
    if (phase === 'operator') {
      if (tool === 'enrich_asset_graph') return 'Enrich asset graph'
      if (tool === 'rank_risk') return 'Rank risk'
      if (tool === 'draft_remediation') return 'Draft remediation'
      return 'Operator'
    }
    return phase || ''
  }
  function stepSummary(e:any): string {
    const d = e?.data || e
    if (d?.phase === 'planner') return d?.verdict?.allowed ? 'Scope allow' : `Blocked: ${d?.verdict?.reason}`
    if (d?.phase === 'operator' && d?.tool === 'enrich_asset_graph') return `Found ${d?.result?.subgraph_nodes ?? 0} nodes`
    if (d?.phase === 'operator' && d?.tool === 'rank_risk') return `Band ${d?.result?.band ?? ''}`
    if (d?.phase === 'operator' && d?.tool === 'draft_remediation') return `Cited ${d?.result?.cited_count ?? 0} ids`
    if (d?.phase === 'checker') return d?.result?.passed ? 'Draft OK' : `Issues: ${(d?.result?.issues || []).join(',')}`
    if (d?.final) return `Band ${d?.risk?.band}; cites ${d?.draft?.cited_ids?.length || 0}`
    if (d?.phase === 'monitoring') return d?.result?.exported ? 'Span casework.run sent to DataRobot' : 'Span casework.run recorded'
    if (d?.phase === 'metrics') {
      const model = d?.metrics?.model ? ` · ${d.metrics.model}` : ''
      const via = d?.metrics?.provider === 'omniroute' ? ' · OmniRoute' : ''
      return `Tokens ${d?.metrics?.prompt_tokens}${model}${via}${d?.metrics?.demo_simulated_metrics ? ' (simulated)' : ''}`
    }
    return ''
  }
  function stepAttrPhase(e: RunEvent): string | undefined {
    const d = e.data
    if (d?.final) return 'final'
    if (d?.phase === 'operator' && d?.tool) return `operator-${d.tool}`
    return d?.phase
  }
  function stepDuration(i: number): string | null {
    if (!eventTimes[i]) return null
    const prev = i>0 ? eventTimes[i-1] : eventTimes[0]
    const ms = Math.max(0, (eventTimes[i] - (prev||eventTimes[i])))
    if (!isFinite(ms) || ms<=0) return null
    const s = (ms/1000).toFixed(1)
    return `${s}s`
  }

  React.useEffect(() => {
    try { sessionStorage.setItem('casework-console-h', String(consoleHeight)) } catch {}
  }, [consoleHeight])

  function nudgeConsole(delta: number) {
    setConsoleHeight(height => clampConsole(height + delta))
  }

  function onConsoleResizeDown(e: React.PointerEvent<HTMLButtonElement>) {
    consoleDrag.current = { y: e.clientY, h: consoleHeight }
    e.currentTarget.setPointerCapture(e.pointerId)
  }

  function onConsoleResizeMove(e: React.PointerEvent<HTMLButtonElement>) {
    const drag = consoleDrag.current
    if (!drag) return
    setConsoleHeight(clampConsole(drag.h + (drag.y - e.clientY)))
  }

  function onConsoleResizeUp() {
    consoleDrag.current = null
  }

  function onConsoleResizeKey(e: React.KeyboardEvent<HTMLButtonElement>) {
    const step = e.shiftKey ? 48 : 24
    if (e.key === 'ArrowUp') { e.preventDefault(); nudgeConsole(step) }
    if (e.key === 'ArrowDown') { e.preventDefault(); nudgeConsole(-step) }
    if (e.key === 'Home') { e.preventDefault(); setConsoleHeight(CONSOLE_MAX) }
    if (e.key === 'End') { e.preventDefault(); setConsoleHeight(CONSOLE_MIN) }
  }

  const appStyle = React.useMemo<React.CSSProperties>(() => {
    const sized = { ['--console-h' as string]: `${consoleHeight}px` } as React.CSSProperties
    if (isMobile && selected) {
      return { ...sized, gridTemplateRows: `56px minmax(0, 1fr) ${consoleHeight}px`, gridTemplateAreas: `"hdr" "main" "console"` };
    }
    return sized;
  }, [isMobile, selected, consoleHeight]);

  const segmentLabel = (subgraph?.nodes || []).find((n: any) => n.type === 'segment')?.label
  const ownerLabel = (subgraph?.nodes || []).find((n: any) => n.type === 'owner')?.label

  return (
    <div className="app" tabIndex={0} style={appStyle}>
      <div className="hdr panel" role="banner" id="hdr">
        <div className="hdr-left">
          <strong className="brand">Casework</strong>
          <span className="demo-badge">Demo</span>
          <span className="tenant-badge" id="session-tenant">{tenantDisplay(session?.tenant_id)}</span>
          <span className="tagline">Read the request. Draft the reply. Send nothing until you decide.</span>
        </div>
        <div className="hdr-right">
          <span className="tenant-badge" id="session-actor">{actor.name}</span>
          <button className="btn small" id="btn-explanation" type="button" onClick={() => go('/brief')}>Explanation</button>
          {onSignOut && <button className="btn small" type="button" onClick={onSignOut}>Sign out</button>}
          <div className="avatar" aria-label="Analyst avatar" title={actor.name}>{actor.initials}</div>
        </div>
      </div>

      {(!isMobile || !selected) && (
      <div className="panel q" role="complementary" aria-label="Findings queue" id="queue">
        <div className="toolbar">
          <input placeholder="Filter..." className="input" style={{flex:1}} onChange={e=>{
            const q = e.target.value.toLowerCase()
            fetch(`${API}/api/findings`).then(r=>r.json()).then(d=>{
              const all = d.findings||[]
              setFindings(all.filter((f:Finding)=> f.title.toLowerCase().includes(q) || f.finding_id.toLowerCase().includes(q)))
            })
          }} />
        </div>
        <div className="q-header">
          <div id="queue-count">{approvableCount} can be approved</div>
          <p className="hint">Green means the reply is safe to record. Hold means the reply says wait. Neither one has been rejected.</p>
        </div>
        <div className="filters" role="group" aria-label="Severity filters">
          {['all','critical','high','medium','low'].map(s=>(
            <span key={s} className={`pill filter ${severityFilter===s?'active':''}`} onClick={()=>setSeverityFilter(s)}>{s}</span>
          ))}
        </div>
        <div className="q-list panel-body">
          <ul className="queue" data-testid="queue" aria-label="Queue list">
            {filtered.length === 0 && <li className="hint empty-queue">No requests at this priority.</li>}
            {filtered.map(f => (
              <li key={f.finding_id}
                  onClick={()=>{ setSelected(f.finding_id); if (isMobile) setActiveMobileTab('overview') }}
                  className={selected===f.finding_id?'selected row-focus':''}
                  aria-current={selected===f.finding_id}
                  style={{cursor:'pointer'}}>
                <div className="leftbar" aria-hidden="true" />
                <div>
                  <div className="title">
                    <span className={`pill ${sevClass(f.severity)}`} style={{marginRight:8}}>{(f.severity||'').toLowerCase()}</span>
                    <ToolBadge tool={f.source_tool} />
                    {f.title}
                  </div>
                  <div className="reason">{caseReason(f.finding_id)}</div>
                  <div className="meta">
                    <span className="mono">{f.finding_id}</span>
                    <span>{f.asset_label || assetShort(f.asset_ids?.[0])}</span>
                    {f.approvable ? <span className="pill can-approve">Can approve</span> : <span className="status-hold">Hold</span>}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
      )}

      {(!isMobile || selected) && (
      <div className="panel main" role="main">
        <div className="toolbar" style={{gap:12}}>
          {isMobile && selected && <button className="btn outline" onClick={()=>setSelected(null)} aria-label="Back">Back</button>}
          <div className="input-group" style={{flex:1, minWidth:220}}>
            <span className="addon" aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2"/>
                <line x1="16.5" y1="16.5" x2="21" y2="21" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </span>
            <input placeholder="Ask or check a request" value={scopeText} onChange={e=>setScopeText(e.target.value)} />
            <button className="btn" id="btn-check" onClick={()=>screenScope()}>Check</button>
          </div>
          <button className="btn primary" id="btn-run" onClick={triageRun} disabled={!selected || running} aria-busy={running}>{running ? 'Drafting…' : 'Draft reply'}</button>
          <button className="btn outline" id="btn-refresh-audit" onClick={refreshAudit}>Refresh audit</button>
        </div>
        {isMobile && selected && (
          <div role="tablist" aria-label="Detail tabs" style={{display:'flex', gap:8, margin:'6px 8px'}}>
            <button role="tab" aria-selected={activeMobileTab==='overview'} className="btn" onClick={()=>setActiveMobileTab('overview')} data-testid="tab-overview">Overview</button>
            <button role="tab" aria-selected={activeMobileTab==='run'} className="btn" onClick={()=>setActiveMobileTab('run')} data-testid="tab-agent">Agent run</button>
            <button role="tab" aria-selected={activeMobileTab==='graph'} className="btn" onClick={()=>setActiveMobileTab('graph')} data-testid="tab-graph">Graph</button>
          </div>
        )}
        {(!isMobile || activeMobileTab==='overview') && (
          <section className="stage finding-stage">
            {detail ? (
              <div>
                <h2 className="finding-title"><span className={`pill ${sevClass(detail.severity)}`} style={{marginRight:8}}>{(detail.severity||'').toLowerCase()}</span>{detail.title}</h2>
                <p className="stage-lead">{detail.ask || 'Emirates NBD Demo only. The agent reads this customer graph. It does not call their systems.'}</p>
                {detail.audience && detail.pipeline?.summary && (
                  <p className="stage-lead" id="reply-audience">Reply for {detail.audience}. {detail.pipeline.summary}</p>
                )}
                {detail.approval?.ready && (
                  <div id="approval-why" className="approval-why">
                    <p><strong>Why this can be approved.</strong> {detail.approval.why}</p>
                    <p><strong>How.</strong> {detail.approval.how}</p>
                  </div>
                )}
                {detail.source_tool ? (
                <div className="meta-chips">
                  <ToolBadge tool={detail.source_tool} />
                  <span className="pill mono" title={detail.rule_id}>{String(detail.rule_id||'').split('.').pop()}</span>
                  {detail.file && <span className="pill mono">{detail.file}{detail.line ? `:${detail.line}` : ''}</span>}
                  {detail.masked_preview && <span className="pill mono" title="Secret value is never stored">{detail.masked_preview}</span>}
                  {detail.synthetic && <span className="pill">Synthetic</span>}
                </div>
                ) : (
                <div className="meta-chips">
                  <span className="pill">{detail.asset_label || assetShort(detail.asset_ids?.[0])}</span>
                  {segmentLabel && <span className="pill">{segmentLabel}</span>}
                  {ownerLabel && <span className="pill">{ownerLabel}</span>}
                </div>
                )}
              </div>
            ) : <div className="hint">Loading the first case.</div>}
          </section>
        )}
        <div className="main-body">
          {scopeVerdict && !scopeVerdict.allowed && (
            <div id="policy-banner">
              <strong>Request blocked by scope guard</strong>
              <div>This request is blocked because it is {String(scopeVerdict.reason || '').replaceAll('_', ' ')}.</div>
              <div style={{marginTop:6}}><span className="pill" id="scope-pill">{scopeVerdict.reason}</span></div>
            </div>
          )}
          {scopeVerdict && scopeVerdict.allowed && (
            <div id="scope-allow">This request stays in Emirates NBD Demo.</div>
          )}
          {(!isMobile || activeMobileTab==='overview') && (
          <section className="stage" id="reply-review">
            <h3>Reply to review</h3>
            <p className="stage-lead">Read this before you decide. Nothing goes to Emirates NBD Demo until you choose.</p>
            {risk ? (
              <div className="risk-row">
                <span>Band</span>
                <span className={`pill ${sevClass(risk.band)}`}>{risk.band}</span>
                <div className="riskbar"><div className="fill" style={{width:`${Math.round((risk.score||0)*100)}%`}} /></div>
                <div className="risk-score"><span>{Math.round((risk.score||0)*100)}</span><span className="of">/100</span><span className="band">· {risk.band}</span></div>
              </div>
            ) : <div className="await-run">Draft the reply. The words to review appear here. Nothing is sent.</div>}
            {risk?.factors?.length ? (
              <ul className="factor-list">
                {risk.factors.map((f:any, i:number)=>(
                  <li key={i}><strong>{f.name}</strong> {f.value}</li>
                ))}
              </ul>
            ) : null}
            {draft?.model && <p className="hint">Drafted by {draft.model} through OmniRoute.</p>}
            {draft ? (
              <ol className="reply-text">
                {draft.steps.map((s:any, i:number)=>(
                  <li key={i}>
                    <div className="draft-step">
                      <div>{s.text}</div>
                      <div className="draft-cites">
                        {s.cites?.map((c:string)=><span className="pill" key={c} title={c}>{citeLabel(subgraph, c)}</span>)}
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            ) : null}
          </section>
          )}
          {isMobile && activeMobileTab==='graph' && (
            <div className="graph-disclosure" open={true}>
              <GraphReadout subgraph={subgraph} />
              {catalog?.nodes?.length ? <GraphRagView catalog={catalog} /> : null}
            </div>
          )}
        </div>
        <div id="panel-trace" ref={traceRef} role="region" aria-label="Run trace" style={{visibility: (isMobile && activeMobileTab!=='run') ? 'hidden' : 'visible'}}>
          {(!isMobile || activeMobileTab==='run') && (
          <>
            <h3>Agent</h3>
            {events.length ? (
              <ul>
                {events.map((e, i)=> {
                  const d = e.data
                  const title = stepTitle(d?.phase, d?.tool, d?.final)
                  const sum = stepSummary(e)
                  const phaseAttr = stepAttrPhase(e)
                  const dur = stepDuration(i)
                  if (!(d?.final || d?.phase)) return null
                  return (
                    <li key={i} data-phase={phaseAttr}>
                      <div className="step-line">
                        <div className="step-title"><span className="status-icon">+</span>{title}{dur ? <span className="duration"> · {dur}</span> : null}</div>
                        {sum ? <div className="summary">{sum}</div> : null}
                        <button className="payload-toggle" onClick={()=> setExpanded(prev => ({...prev, [i]: !prev[i]})) }>{expanded[i] ? 'Hide payload' : 'View payload'}</button>
                      </div>
                      {expanded[i] && <pre className="payload mono">{JSON.stringify(d, null, 2)}</pre>}
                    </li>
                  )
                })}
              </ul>
            ) : (
              <ol className="preview-steps">
                <li>Check the request stays in Emirates NBD Demo</li>
                <li>Read the related models</li>
                <li>Rank the decision</li>
                <li>Draft the reply</li>
              </ol>
            )}
          </>
          )}
        </div>
        {(!isMobile || activeMobileTab==='overview') && (
        <div className="decision-bar">
          <h3>Decision</h3>
          <div className="decision-actions">
            <button className="btn primary" id="btn-approve" onClick={()=>decide('approve')} disabled={!selected||loading||approveDisabled}>Approve</button>
            <button className="btn outline" id="btn-escalate" onClick={()=>decide('escalate')} disabled={!selected||loading}>Escalate</button>
            <button className="btn ghost-danger" id="btn-reject" onClick={()=>decide('reject')} disabled={!selected||loading}>Reject</button>
            {approveDisabled && <span className="hint">Draft the reply first</span>}
          </div>
          {decisionNote && <p id="decision-status">{decisionNote}</p>}
          <div className="decision-notes">
            <span className="hint">Approve records the reply for the team that owns it. Nothing is sent.</span>
            <span className="hint">Escalate records it for the pod lead. Nothing is sent.</span>
            <span className="hint">Reject returns the draft to the analyst.</span>
          </div>
        </div>
        )}
      </div>
      )}

      {!isMobile && (
      <div className="panel graph" role="region" aria-label="Graph context" id="panel-graph">
        <div className="toolbar"><strong>Why this reply</strong></div>
        <div className="graph-body">
          <div className="rail-block">
            <h3>Connected work</h3>
            {subgraph ? <GraphReadout subgraph={subgraph} /> : <div className="hint">The related assets appear with the case.</div>}
          </div>
          <div className="rail-block">
            <h3>GraphRAG</h3>
            {catalog?.nodes?.length ? <GraphRagView catalog={catalog} /> : <div className="hint">The graph for this bank loads with the desk.</div>}
          </div>
          <div className="rail-block">
            <h3>Refusals</h3>
            <p className="stage-lead">Two requests this desk must refuse.</p>
            <div className="scope-actions">
              <button className="btn" id="btn-scope-foreign" type="button" onClick={()=>screenScope('Open tenant_other_corp', ['finding:F-901'])}>Open tenant_other_corp</button>
              <button className="btn ghost-danger" id="btn-scope-destructive" type="button" onClick={()=>screenScope('Shut the model down in prod')}>Shut the model down in prod</button>
            </div>
          </div>
          <div className="rail-block">
            <h3>Audit</h3>
            {audit.length ? (
              <ul className="audit-list">
                {audit.map((a:any)=> (
                  <li key={a.audit_id}>
                    <span style={{color:'var(--muted)'}}>{formatRelative(a.ts)}</span>
                    <span className="audit-label">{auditLabel(a)}</span>
                  </li>
                ))}
              </ul>
            ) : <div className="hint">No decisions yet. Run a check or record one.</div>}
          </div>
        </div>
      </div>
      )}

      <section id="ai-console" className="panel ai-console" aria-label="AI console">
        <button
          type="button"
          id="console-resize"
          className="console-resize"
          role="separator"
          aria-orientation="horizontal"
          aria-label="Resize AI console"
          aria-valuemin={CONSOLE_MIN}
          aria-valuemax={CONSOLE_MAX}
          aria-valuenow={consoleHeight}
          onPointerDown={onConsoleResizeDown}
          onPointerMove={onConsoleResizeMove}
          onPointerUp={onConsoleResizeUp}
          onPointerCancel={onConsoleResizeUp}
          onKeyDown={onConsoleResizeKey}
        />
        <div className="console-head">
          <h3>AI console</h3>
          <div className="console-tools">
            <span className="pill tool-langgraph" title="The agent loop. It plans the run, reads the case, ranks it, and checks the draft.">LangGraph</span>
            <span className="pill tool-langchain" title="Builds the system and user messages that the model reads.">LangChain Core</span>
            <span className="pill tool-rag" title="Reads this tenant's case map. The draft may cite only those nodes.">SQLite GraphRAG</span>
            <span className="pill tool-omni" title="The model gateway. gpt-5.6-terra writes the reply and reports the token counts.">OmniRoute</span>
            <span className="pill tool-otel" title="Records span casework.run. It sends the span only when DataRobot monitoring is configured.">OpenTelemetry</span>
          </div>
          <div className="console-size">
            <button type="button" className="btn small" id="btn-console-shrink" onClick={() => nudgeConsole(-48)} disabled={consoleHeight <= CONSOLE_MIN}>Shrink</button>
            <button type="button" className="btn small" id="btn-console-expand" onClick={() => nudgeConsole(48)} disabled={consoleHeight >= CONSOLE_MAX}>Expand</button>
          </div>
        </div>
        <div className="console-log" ref={consoleRef}>
          {events.some(e => e.data?.line) || decisionNote ? (
            <ol>
              {events.map((e, i) => e.data?.line ? <li key={i} data-tool={consoleTool(e.data)}>{e.data.line}</li> : null)}
              {decisionNote ? <li>{decisionNote}</li> : null}
            </ol>
          ) : (
            <p className="hint">Draft reply to start the run. LangGraph plans it. LangChain Core writes the prompt. SQLite GraphRAG supplies the case.</p>
          )}
        </div>
      </section>
    </div>
  )
}

const CASE_REASON: Record<string, string> = {
  'F-101': 'Personal loans, do not promote',
  'F-102': 'Application file broke',
  'F-103': 'Weekly credit review',
  'F-104': 'Missing debt to income',
  'F-105': 'West region still on v2',
  'F-106': 'No owner on nightly scoring',
  'F-107': 'Retrain note still open',
  'F-108': 'Approved on Loan model v2',
  'F-109': 'Ready for the next batch',
}

function consoleTool(data: any): string {
  if (data?.phase === 'monitoring') return 'otel'
  if (data?.phase === 'metrics' || data?.tool === 'draft_remediation') return data?.tool === 'draft_remediation' ? 'langchain' : 'omni'
  if (data?.tool === 'enrich_asset_graph') return 'rag'
  if (data?.phase === 'graph' || data?.phase === 'planner' || data?.phase === 'checker' || data?.tool === 'rank_risk') return 'langgraph'
  return 'desk'
}

function caseReason(id: string): string {
  return CASE_REASON[id] || 'Open request'
}

function assetShort(id?: string): string {
  if (!id) return 'asset unknown'
  const tail = id.split(':')[1] || id
  return `Asset ${tail}`
}

function citeLabel(subgraph: any, id: string): string {
  return nodeName(subgraph, id)
}

function nodeName(subgraph: any, id: string): string {
  const n = (subgraph?.nodes || []).find((x: any) => x.id === id)
  return n?.label || id
}

function GraphReadout({subgraph}:{subgraph:any}) {
  const guideRef = React.useRef<HTMLDialogElement>(null)
  const mapRef = React.useRef<HTMLDialogElement>(null)
  const nodes = subgraph?.nodes || []
  const ids = new Set(nodes.map((n: any) => n.id))
  const sentence = ids.has('asset:cam-01') && ids.has('asset:cam-02') && ids.has('segment:seg-dmz-a')
    ? `${nodeName(subgraph, 'asset:cam-01')} and ${nodeName(subgraph, 'asset:cam-02')} score ${nodeName(subgraph, 'segment:seg-dmz-a')}.`
    : 'Related work stays inside this customer.'
  const edges = (subgraph?.edges || []).filter((e: any) => e.type === 'SAME_SEGMENT' || e.type === 'HAS_FINDING' || e.type === 'OWNED_BY').slice(0, 8)
  return (
    <div>
      <div className="graph-head">
        <div className="graph-sentence">{sentence}</div>
        <button className="btn small" id="btn-graph-guide" type="button" onClick={() => guideRef.current?.showModal()}>What is this?</button>
      </div>
      <dialog ref={guideRef} id="graph-guide" className="guide">
        <h2>Why this reply</h2>
        <p><strong>Who.</strong> This picture is for the analyst on this desk, and for the credit risk or lending ops team the reply is written for. An applicant never sees it.</p>
        <p><strong>What it is for.</strong> The draft may only cite things on this map. You use it to check that the reply is about this bank's models, not a loose paragraph.</p>
        <p><strong>The dots.</strong> A request is an open case, such as F-101. A model is loan model v2 or v3. A use case is the book they score, Personal loans. A pod is the team that owns the work. Evidence is the fact the reply relies on, such as the holdout drop.</p>
        <p><strong>The links.</strong> HAS_FINDING means this model is named in that request. SAME_SEGMENT means these models score the same book of loans. OWNED_BY means that team owns the model.</p>
        <p>The line at the top is the decision in one sentence. Loan model v3 and loan model v2 score Personal loans.</p>
        <button className="btn" type="button" onClick={() => guideRef.current?.close()}>Close</button>
      </dialog>
      <button className="graph-canvas graph-open" id="btn-expand-graph" type="button" aria-label="Expand map" onClick={() => mapRef.current?.showModal()}>
        <MiniGraph subgraph={subgraph} />
      </button>
      <dialog ref={mapRef} id="graph-expanded" className="guide guide-map">
        <div className="guide-bar">
          <h2>The map</h2>
          <button className="btn" type="button" onClick={() => mapRef.current?.close()}>Close</button>
        </div>
        <p className="stage-lead">Full names for this case. The small picture in the side panel is the same map.</p>
        <div className="graph-canvas graph-canvas-large">
          <MiniGraph subgraph={subgraph} width={920} height={440} pad={100} font={14} labelLimit={48} />
        </div>
        <ul className="map-names">
          {nodes.map((n: any) => (
            <li key={n.id}><span className="edge-type">{kindLabel(n.id)}</span> {n.label || n.id}</li>
          ))}
        </ul>
      </dialog>
      <div className="legend">
        <span><i className="swatch" style={{background:'var(--accent)'}} /> request</span>
        <span><i className="swatch" style={{background:'#0E7C86'}} /> model</span>
        <span><i className="swatch" style={{background:'#C2410C'}} /> use case</span>
        <span><i className="swatch" style={{background:'#6D28D9'}} /> pod</span>
        <span><i className="swatch" style={{background:'#BE123C'}} /> evidence</span>
      </div>
      <ul className="edge-list">
        {edges.map((e: any, i: number) => (
          <li key={i}>{nodeName(subgraph, e.src)} <span className="edge-type">{e.type}</span> {nodeName(subgraph, e.dst)}</li>
        ))}
      </ul>
    </div>
  )
}

function GraphRagView({catalog}:{catalog:any}) {
  const mapRef = React.useRef<HTMLDialogElement>(null)
  const counts = catalog?.counts || { nodes: (catalog?.nodes || []).length, edges: (catalog?.edges || []).length }
  return (
    <div>
      <p className="graph-sentence">{counts.nodes} nodes, {counts.edges} edges.</p>
      <button className="graph-canvas graphrag-canvas graph-open" id="btn-expand-graphrag" type="button" aria-label="Expand GraphRAG" onClick={() => mapRef.current?.showModal()}>
        <GraphMap graph={catalog} mapId="graphrag-map" fit />
      </button>
      <dialog ref={mapRef} id="graphrag-expanded" className="guide guide-map guide-graphrag">
        <div className="guide-bar">
          <h2>GraphRAG</h2>
          <button className="btn" type="button" onClick={() => mapRef.current?.close()}>Close</button>
        </div>
        <div className="graphrag-stage">
          <GraphMap graph={catalog} mapId="graphrag-map-large" />
        </div>
        <div className="legend">
          {EDGE_KINDS.map(([type, title, color]) => (
            <span key={type}><i className="swatch" style={{background: color}} /> {title}</span>
          ))}
        </div>
      </dialog>
    </div>
  )
}

function kindLabel(id: string): string {
  const t = (id.split(':', 1)[0] || '').toLowerCase()
  if (t === 'finding') return 'request'
  if (t === 'asset') return 'model'
  if (t === 'segment') return 'use case'
  if (t === 'owner') return 'pod'
  if (t === 'weakness') return 'evidence'
  return t || 'item'
}

const GRAPH_COLUMNS: [string, string, string, string][] = [
  ['finding', 'Requests', '#0C6B4D', '#E5F6EE'],
  ['asset', 'Models', '#0E7C86', '#E0F2FE'],
  ['segment', 'Use cases', '#C2410C', '#FFEDD5'],
  ['owner', 'Pods', '#6D28D9', '#EDE9FE'],
  ['weakness', 'Evidence', '#BE123C', '#FFE4E6'],
]

const EDGE_KINDS: [string, string, string][] = [
  ['HAS_FINDING', 'Named in', '#16324F'],
  ['SAME_SEGMENT', 'Same book', '#0E7C86'],
  ['OWNED_BY', 'Owned by', '#6D28D9'],
  ['RELATED_WEAKNESS', 'Evidence', '#BE123C'],
  ['RUNS_ON', 'Runs on', '#854D0E'],
]

function MiniGraph({subgraph, width=300, height=200, pad=36, font=10, labelLimit=16}:{subgraph:any, width?:number, height?:number, pad?:number, font?:number, labelLimit?:number}) {
  const nodes = subgraph?.nodes||[]
  const edges = subgraph?.edges||[]
  const W = width, H = height, P = pad
  const N = Math.max(nodes.length, 1)
  const positioned = nodes.map((n:any, i:number) => {
    const angle = (i / N) * Math.PI * 2 - Math.PI / 2
    const r = Math.min(W, H) / 2 - P
    const cx = W / 2 + r * Math.cos(angle)
    const cy = H / 2 + r * Math.sin(angle)
    return {...n, cx, cy, angle}
  })
  const byId: Record<string, any> = {}
  positioned.forEach((n:any)=> byId[n.id]=n)
  function colorFor(id: string): string {
    const t = (id.split(':', 1)[0] || '').toLowerCase()
    if (t === 'finding') return 'var(--accent)'
    if (t === 'asset') return '#0E7C86'
    if (t === 'segment') return '#C2410C'
    if (t === 'owner') return '#6D28D9'
    if (t === 'weakness') return '#BE123C'
    return 'var(--muted)'
  }
  return (
    <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Asset graph" preserveAspectRatio="xMidYMid meet">
      <g stroke="#C9D6EE" strokeWidth="1.5">
        {edges.map((e:any,i:number)=>{
          const s = byId[e.src], d = byId[e.dst]; if (!s||!d) return null
          return <line key={i} x1={s.cx} y1={s.cy} x2={d.cx} y2={d.cy}><title>{e.type}</title></line>
        })}
      </g>
      <g>
        {positioned.map((n:any)=>{
          const label = String(n.label||n.id).slice(0, labelLimit)
          const lx = n.cx + Math.cos(n.angle) * (font + 8)
          const ly = n.cy + Math.sin(n.angle) * (font + 8)
          const anchor = Math.cos(n.angle) > 0.35 ? 'start' : Math.cos(n.angle) < -0.35 ? 'end' : 'middle'
          return (
          <g key={n.id}>
            <circle cx={n.cx} cy={n.cy} r={font > 12 ? 8 : 6} fill="#FFFFFF" stroke={colorFor(n.id)} strokeWidth="2" />
            <title>{n.label || n.id}</title>
            <text x={lx} y={ly} fontSize={font} textAnchor={anchor} fill="#12151C" stroke="#FFFFFF" strokeWidth="4" paintOrder="stroke">{label}</text>
          </g>
          )
        })}
      </g>
    </svg>
  )
}

function GraphMap({graph, mapId, fit=false}:{graph:any, mapId?: string, fit?: boolean}) {
  const font = 13
  const rowH = 40
  const pillH = 28
  const gutter = 64
  const top = 36
  const nodes = graph?.nodes || []
  const edges = graph?.edges || []
  const known = new Set(GRAPH_COLUMNS.map(([type]) => type))
  const columns: any[][] = GRAPH_COLUMNS.map(([type]) => nodes.filter((n: any) => n.type === type))
  const extra = nodes.filter((n: any) => !known.has(n.type))
  if (extra.length) columns.push(extra)
  const byNode: Record<string, any> = {}
  nodes.forEach((n: any) => { byNode[n.id] = n })
  function linkedLabel(n: any, type: string): string {
    const labels: string[] = []
    edges.forEach((e: any) => {
      const otherId = e.src === n.id ? e.dst : e.dst === n.id ? e.src : ''
      const other = otherId ? byNode[otherId] : null
      if (other && other.type === type) labels.push(String(other.label || other.id))
    })
    labels.sort()
    return labels[0] || 'zzz'
  }
  columns[0].sort((a: any, b: any) => linkedLabel(a, 'asset').localeCompare(linkedLabel(b, 'asset')) || String(a.label || a.id).localeCompare(String(b.label || b.id)))
  const slot: Record<string, number> = {}
  columns[0].forEach((n: any, i: number) => { slot[n.id] = i })
  for (let ci = 1; ci < columns.length; ci += 1) {
    const ranked = columns[ci].map((n: any) => {
      const ys: number[] = []
      edges.forEach((e: any) => {
        if (e.src === n.id && slot[e.dst] != null) ys.push(slot[e.dst])
        if (e.dst === n.id && slot[e.src] != null) ys.push(slot[e.src])
      })
      ys.sort((a, b) => a - b)
      return { n, target: ys.length ? ys[Math.floor((ys.length - 1) / 2)] : null }
    }).sort((a, b) => (a.target ?? 99) - (b.target ?? 99) || String(a.n.label).localeCompare(String(b.n.label)))
    let cursor = 0
    ranked.forEach(item => {
      const next = item.target == null ? cursor : Math.max(cursor, item.target)
      slot[item.n.id] = next
      cursor = next + 1
    })
    columns[ci] = ranked.map(item => item.n)
  }
  for (let ci = 1; ci < columns.length; ci += 1) {
    const ranked = columns[ci].map((n: any) => {
      const ys: number[] = []
      edges.forEach((e: any) => {
        if (e.src === n.id && slot[e.dst] != null) ys.push(slot[e.dst])
        if (e.dst === n.id && slot[e.src] != null) ys.push(slot[e.src])
      })
      ys.sort((a, b) => a - b)
      return { n, target: ys.length ? ys[Math.floor((ys.length - 1) / 2)] : null }
    }).sort((a, b) => (a.target ?? 99) - (b.target ?? 99) || String(a.n.label).localeCompare(String(b.n.label)))
    let cursor = 0
    ranked.forEach(item => {
      const next = item.target == null ? cursor : Math.max(cursor, item.target)
      slot[item.n.id] = next
      cursor = next + 1
    })
  }
  const placed: Record<string, any> = {}
  let x = 20
  let maxBottom = top
  columns.forEach((col, ci) => {
    const width = Math.max(88, ...col.map((n: any) => Math.ceil(String(n.label || n.id).length * font * 0.58) + 34))
    col.forEach((n: any) => {
      const y = top + slot[n.id] * rowH
      placed[n.id] = { ...n, x, y, w: width, h: pillH }
      maxBottom = Math.max(maxBottom, y + pillH)
    })
    x += width + gutter
    if (ci === columns.length - 1) x -= gutter
  })
  const W = x + 20
  const H = maxBottom + 20
  const nodeCount = graph?.counts?.nodes ?? nodes.length
  const edgeCount = graph?.counts?.edges ?? edges.length
  function tone(type: string): [string, string] {
    const row = GRAPH_COLUMNS.find(([kind]) => kind === type)
    return row ? [row[2], row[3]] : ['#3E4C5E', '#F6F8FA']
  }
  function edgeColor(type: string): string {
    return EDGE_KINDS.find(([kind]) => kind === type)?.[2] || '#8B99A8'
  }
  return (
    <svg id={mapId} width={fit ? '100%' : W} height={fit ? '100%' : H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`GraphRAG, ${nodeCount} nodes, ${edgeCount} edges`} preserveAspectRatio="xMidYMid meet">
      {columns.map((col, ci) => col[0] && (
        <text key={GRAPH_COLUMNS[ci]?.[0] || 'other'} x={placed[col[0].id].x} y={20} fontSize={12} fontWeight={700} fill="#3E4C5E">{GRAPH_COLUMNS[ci]?.[1] || 'Other'}</text>
      ))}
      <g fill="none">
        {edges.map((e: any, i: number) => {
          const s = placed[e.src], d = placed[e.dst]
          if (!s || !d) return null
          const forward = s.x <= d.x
          const x1 = forward ? s.x + s.w : s.x
          const x2 = forward ? d.x : d.x + d.w
          const y1 = s.y + s.h / 2
          const y2 = d.y + d.h / 2
          const bend = Math.max(28, Math.abs(x2 - x1) / 2)
          const c1 = x1 + (forward ? bend : -bend)
          const c2 = x2 + (forward ? -bend : bend)
          return <path key={i} d={`M ${x1} ${y1} C ${c1} ${y1}, ${c2} ${y2}, ${x2} ${y2}`} stroke={edgeColor(e.type)} strokeWidth="1.5" opacity="0.55"><title>{e.type}</title></path>
        })}
      </g>
      <g>
        {Object.values(placed).map((n: any) => {
          const [ink, wash] = tone(n.type)
          return (
            <g key={n.id}>
              <rect x={n.x} y={n.y} width={n.w} height={n.h} rx="8" fill={wash} stroke={ink} />
              <circle cx={n.x + 12} cy={n.y + n.h / 2} r="4" fill={ink} />
              <text x={n.x + 22} y={n.y + n.h / 2 + 4} fontSize={font} fill="#12171F">{n.label || n.id}</text>
              <title>{n.label || n.id}</title>
            </g>
          )
        })}
      </g>
    </svg>
  )
}
