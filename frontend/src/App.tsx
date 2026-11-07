import React from 'react'
import { getApiBase, getRunsBase } from './config'

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
}

const TOOL_LABEL: Record<string, string> = {gitleaks: 'Gitleaks', trufflehog: 'TruffleHog', trivy: 'Trivy', semgrep: 'Semgrep', prowler: 'Prowler'}
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
  const traceRef = React.useRef<HTMLDivElement | null>(null)
  const runToken = React.useRef(0)
  const streamRef = React.useRef<EventSource | null>(null)

  const API = React.useMemo(()=> getApiBase(), [])
  const RUNS = React.useMemo(()=> getRunsBase(), [])

  React.useEffect(() => {
    fetch(`${API}/api/session`).then(r => r.json()).then(setSession).catch(()=>{})
    fetch(`${API}/api/findings`).then(r => r.json()).then(d => setFindings(d.findings || [])).catch(()=>{})
    fetch(`${API}/api/audit`).then(r => r.json()).then(d => setAudit(d.audit || [])).catch(()=>{})
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
  }, [events])

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
  const filtered = findings.filter(f => severityFilter==='all' ? true : (f.severity||'').toLowerCase()===severityFilter)
  const openCount = findings.length

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

  const appStyle = React.useMemo<React.CSSProperties>(() => {
    if (isMobile && selected) {
      return { gridTemplateRows: '56px 1fr', gridTemplateAreas: `"hdr" "main"` };
    }
    return {};
  }, [isMobile, selected]);

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
          <div>Requests · {openCount} open</div>
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
                    <span className="status-open">{f.status}</span>
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
                  <p className="stage-lead" id="reply-audience">Reply for {detail.audience}. {detail.pipeline.summary}.</p>
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
          <section className="stage">
            <h3>Recommendation</h3>
            <p className="stage-lead">A reply you can send later. Nothing goes to Emirates NBD Demo until you decide.</p>
            {risk ? (
              <div className="risk-row">
                <span>Band</span>
                <span className={`pill ${sevClass(risk.band)}`}>{risk.band}</span>
                <div className="riskbar"><div className="fill" style={{width:`${Math.round((risk.score||0)*100)}%`}} /></div>
                <div className="risk-score"><span>{Math.round((risk.score||0)*100)}</span><span className="of">/100</span><span className="band">· {risk.band}</span></div>
              </div>
            ) : <div className="await-run">Draft the reply. You will see the priority, the reason, and the words to send. Nothing is sent.</div>}
            {risk?.factors?.length ? (
              <ul className="factor-list">
                {risk.factors.map((f:any, i:number)=>(
                  <li key={i}><strong>{f.name}</strong> {f.value}</li>
                ))}
              </ul>
            ) : null}
            {draft?.model && <p className="hint">Drafted by {draft.model} through OmniRoute.</p>}
            {draft ? (
              <ol>
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
            </div>
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
  const nodes = subgraph?.nodes || []
  const ids = new Set(nodes.map((n: any) => n.id))
  const sentence = ids.has('asset:cam-01') && ids.has('asset:cam-02') && ids.has('segment:seg-dmz-a')
    ? `${nodeName(subgraph, 'asset:cam-01')} and ${nodeName(subgraph, 'asset:cam-02')} serve ${nodeName(subgraph, 'segment:seg-dmz-a')}.`
    : 'Related work stays inside this customer.'
  const edges = (subgraph?.edges || []).filter((e: any) => e.type === 'SAME_SEGMENT' || e.type === 'HAS_FINDING' || e.type === 'OWNED_BY').slice(0, 8)
  return (
    <div>
      <div className="graph-sentence">{sentence}</div>
      <div className="graph-canvas"><MiniGraph subgraph={subgraph} /></div>
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

function MiniGraph({subgraph}:{subgraph:any}) {
  const nodes = subgraph?.nodes||[]
  const edges = subgraph?.edges||[]
  const W = 300, H = 200, P = 36
  const N = Math.max(nodes.length, 1)
  const positioned = nodes.map((n:any, i:number) => {
    const angle = (i / N) * Math.PI * 2 - Math.PI / 2
    const r = Math.min(W, H) / 2 - P
    const cx = W / 2 + r * Math.cos(angle)
    const cy = H / 2 + r * Math.sin(angle)
    return {...n, cx, cy}
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
        {positioned.map((n:any)=>(
          <g key={n.id}>
            <circle cx={n.cx} cy={n.cy} r="6" fill="#FFFFFF" stroke={colorFor(n.id)} strokeWidth="2" />
            <title>{n.id}</title>
            <text x={n.cx} y={n.cy + 16} fontSize="10" textAnchor="middle" fill="#12151C">{String(n.label||n.id).slice(0, 16)}</text>
          </g>
        ))}
      </g>
    </svg>
  )
}
