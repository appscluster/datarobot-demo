import React from 'react'
import { getApiBase, getRunsBase } from './config'

type Finding = {
  finding_id: string
  node_id: string
  title: string
  severity: string
  status: string
  asset_ids: string[]
  updated_at: string
}

type RunEvent = { event: string; data: any }

export function App() {
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
  const [graphOpen, setGraphOpen] = React.useState(false)
  const [lastRunId, setLastRunId] = React.useState<string | null>(null)
  const [severityFilter, setSeverityFilter] = React.useState<string>('all')
  const [isMobile, setIsMobile] = React.useState<boolean>(false)
  const [activeMobileTab, setActiveMobileTab] = React.useState<'overview'|'run'|'graph'>('overview')
  const [eventTimes, setEventTimes] = React.useState<number[]>([])
  const [expanded, setExpanded] = React.useState<Record<number, boolean>>({})

  const API = React.useMemo(()=> getApiBase(), [])
  const RUNS = React.useMemo(()=> getRunsBase(), [])

  React.useEffect(() => {
    fetch(`${API}/api/session`).then(r => r.json()).then(setSession).catch(()=>{})
    fetch(`${API}/api/findings`).then(r => r.json()).then(d => setFindings(d.findings || [])).catch(()=>{})
  }, [API])

  React.useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)')
    const fn = () => setIsMobile(mq.matches)
    fn()
    mq.addEventListener('change', fn)
    return () => mq.removeEventListener('change', fn)
  }, [])

  React.useEffect(() => {
    if (!selected) return
    setDetail(null); setSubgraph(null); setRisk(null); setDraft(null); setEvents([]); setEventTimes([]); setExpanded({})
    fetch(`${API}/api/findings/${selected}`).then(r => r.json()).then(d => setDetail(d.finding)).catch(()=>{})
    fetch(`${API}/api/graph/enrich`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({tenant_id: session?.tenant_id, finding_id: selected, k_hops: 2})})
      .then(r=>r.json()).then(d=> setSubgraph(d.subgraph)).catch(()=>{})
  }, [selected, session?.tenant_id, API])

  function onKey(e: React.KeyboardEvent) {
    if (!findings.length) return
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

  async function triageRun() {
    if (!selected) return
    setEvents([]); setRisk(null); setDraft(null)
    const r = await fetch(`${API}/api/runs`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({finding_id: selected})}).then(r=>r.json())
    const runId = r.run_id
    setLastRunId(runId)
    const es = new EventSource(`${RUNS}/runs/${runId}/events`)
    // Expose a debug window buffer for SSE provenance capture
    ;(window as any).__SSE_EVENTS__ = (window as any).__SSE_EVENTS__ || []
    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data)
        const kind = (data && data.phase) ? 'step' : ev.type || 'message'
        // Debug log
        try { console.log('[sse]', kind, (data && data.phase) ? data.phase : ''); } catch {}
        ;(window as any).__SSE_EVENTS__.push({event: kind, data})
        // Reflect risk/draft/subgraph if present in payload (final event payload)
        if (data && (data.risk || data.draft)) {
          try { console.log('[sse]', 'final(set)'); } catch {}
          setRisk(data.risk); setDraft(data.draft); if (data.subgraph) setSubgraph(data.subgraph)
        }
        setEvents(prev => [...prev, {event: kind, data}]); setEventTimes(prev => [...prev, Date.now()])
      } catch { /* ignore */ }
    }
    es.addEventListener('step', (ev:any) => {
      try {
        const data = JSON.parse(ev.data)
        try { console.log('[sse]', 'step', data?.phase || ''); } catch {}
        ;(window as any).__SSE_EVENTS__.push({event: 'step', data})
        setEvents(prev => [...prev, {event: 'step', data}]); setEventTimes(prev => [...prev, Date.now()])
      } catch {}
    })
    es.addEventListener('final', (ev:any) => {
      try {
        const data = JSON.parse(ev.data)
        setRisk(data.risk); setDraft(data.draft); setSubgraph(data.subgraph)
        setEvents(prev => [...prev, {event:'final', data}]); setEventTimes(prev => [...prev, Date.now()])
        try { console.log('[sse]', 'final'); } catch {}
        ;(window as any).__SSE_EVENTS__.push({event: 'final', data})
      } catch {}
    })
    // Fallback: close on 'done' marker message seen by onmessage
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
        alert(`Refused: ${v.reason}`)
      }
    } finally {
      setLoading(false)
    }
  }

  async function refreshAudit() {
    const r = await fetch(`${API}/api/audit`).then(r=>r.json()).catch(()=>({audit:[]}))
    setAudit(r.audit || [])
  }

  async function screenScope() {
    const body = {tenant_id: session?.tenant_id, requested_action: scopeText, target_ids: []}
    const v = await fetch(`${API}/api/check_scope`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)}).then(r=>r.json())
    setScopeVerdict(v.verdict)
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
  const approveTitle = approveDisabled ? 'Requires a completed, checker-passed run' : undefined
  const filtered = findings.filter(f => severityFilter==='all' ? true : (f.severity||'').toLowerCase()===severityFilter)
  const openCount = findings.length

  function tenantDisplay(tid?: string): string {
    if (!tid) return ''
    if (tid.includes('tenant_demo_acme')) return 'Acme (demo)'
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
    if (d?.phase === 'metrics') return `Tokens ${d?.metrics?.prompt_tokens}${d?.metrics?.demo_simulated_metrics ? ' (simulated)' : ''}`
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

  return (
    <div className="app" onKeyDown={onKey} tabIndex={0} style={appStyle}>
      <div className="hdr panel" role="banner" id="hdr">
        <div className="hdr-left">
          <strong className="brand">ThreatAI</strong>
          <span className="demo-badge">Demo</span>
          <span className="tenant-badge" id="session-tenant">{tenantDisplay(session?.tenant_id)} ▾</span>
        </div>
        <div className="hdr-right">
          <span className="tenant-badge" id="session-actor">{actor.name}</span>
          <div className="avatar" aria-label="Analyst avatar" title={actor.name}>
            {actor.initials}
          </div>
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
          <div>Findings · {openCount} open</div>
        </div>
        <div className="filters" role="group" aria-label="Severity filters">
          {['all','critical','high','medium','low'].map(s=>(
            <span key={s} className={`pill filter ${severityFilter===s?'active':''}`} onClick={()=>setSeverityFilter(s)}>{s}</span>
          ))}
        </div>
        <div className="q-list panel-body">
          <ul className="queue" data-testid="queue" aria-label="Queue list">
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
                    {f.title}
                  </div>
                  <div className="meta">
                    <span>{f.asset_ids?.[0] || 'asset:unknown'}</span>
                    <span className="status-open">{f.status}</span>
                  </div>
                </div>
                <div className="meta">{formatRelative(f.updated_at)}</div>
              </li>
            ))}
          </ul>
        </div>
      </div>
      )}

      {(!isMobile || selected) && (
      <div className="panel main" role="main">
        <div className="toolbar" style={{gap:12}}>
          {isMobile && selected && <button className="btn outline" onClick={()=>setSelected(null)} aria-label="Back">← Back</button>}
          <div className="input-group" style={{flex:1, minWidth:220}}>
            <span className="addon" aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2"/>
                <line x1="16.5" y1="16.5" x2="21" y2="21" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </span>
            <input placeholder="Ask or check a request" value={scopeText} onChange={e=>setScopeText(e.target.value)} />
            <button className="btn" id="btn-check" onClick={screenScope}>Check</button>
          </div>
          <button className="btn primary" id="btn-run" onClick={triageRun} disabled={!selected}>Run triage</button>
          <button className="btn outline" id="btn-refresh-audit" onClick={refreshAudit}>Refresh audit</button>
        </div>
        <div className="main-body">
          {scopeVerdict && !scopeVerdict.allowed && (
            <div id="policy-banner" style={{marginBottom:12}}>
              <div className="icon">🛡</div>
              <div>
                <div style={{fontWeight:600}}>Request blocked by scope guard</div>
                <div className="summary" style={{color:'var(--muted)', marginTop:6}}>Destructive or cross-tenant action is not permitted in demo mode.</div>
                <div style={{marginTop:6}}><span className="pill" id="scope-pill">{scopeVerdict.reason}</span></div>
              </div>
            </div>
          )}
          {isMobile && selected && (
            <div role="tablist" aria-label="Detail tabs" style={{display:'flex', gap:8, margin:'6px 0 12px 0'}}>
              <button role="tab" aria-selected={activeMobileTab==='overview'} data-active={activeMobileTab==='overview'} className="btn" onClick={()=>setActiveMobileTab('overview')} data-testid="tab-overview">Overview</button>
              <button role="tab" aria-selected={activeMobileTab==='run'} data-active={activeMobileTab==='run'} className="btn" onClick={()=>setActiveMobileTab('run')} data-testid="tab-agent">Agent run</button>
              <button role="tab" aria-selected={activeMobileTab==='graph'} data-active={activeMobileTab==='graph'} className="btn" onClick={()=>setActiveMobileTab('graph')} data-testid="tab-graph">Graph</button>
            </div>
          )}
          {(!isMobile || activeMobileTab==='overview') && (
          <div className="main-grid">
          <section>
            <h3>Finding</h3>
            {detail ? (
              <div>
                <div className="finding-title"><span className={`pill ${sevClass(detail.severity)}`} style={{marginRight:8}}>{(detail.severity||'').toLowerCase()}</span>{detail.title}</div>
                <div className="meta-chips">
                  <span className="pill">Asset cam-01</span>
                  <span className="pill">Owner Facilities</span>
                  <span className="pill">Segment DMZ A</span>
                </div>
              </div>
            ) : <div>Loading...</div>}
          </section>
          <section>
            <h3>Risk & Remediation</h3>
            {risk ? (
              <div style={{display:'flex', alignItems:'center', gap:12}}>
                <span>Band:</span>
                <span className={`pill ${sevClass(risk.band)}`}>{risk.band}</span>
                <div className="riskbar"><div className="fill" style={{width:`${Math.round((risk.score||0)*100)}%`}} /></div>
                <div className="risk-score"><span>{Math.round((risk.score||0)*100)}</span><span className="of">/100</span><span className="band">· {risk.band}</span></div>
              </div>
            ) : <div>No data yet</div>}
            {draft ? (
              <ol>
                {draft.steps.map((s:any, i:number)=>(
                  <li key={i}>
                    <div style={{background:'var(--surface-2)', border:'1px solid var(--border)', borderRadius:8, padding:'8px 10px', margin:'6px 0'}}>
                      <div>{s.text}</div>
                      <div style={{display:'flex', gap:6, marginTop:6, flexWrap:'wrap'}}>
                        {s.cites?.map((c:string)=><span className="pill mono" key={c}>{c}</span>)}
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            ) : <div>No data yet</div>}
            <div className="actions-sticky">
              <div className="actions-row">
                <button className="btn primary" id="btn-approve" title={approveTitle} onClick={()=>decide('approve')} disabled={!selected||loading||approveDisabled}>Approve</button>
                <button className="btn outline" id="btn-escalate" onClick={()=>decide('escalate')} disabled={!selected||loading}>Escalate</button>
                <button className="btn ghost-danger" id="btn-reject" onClick={()=>decide('reject')} disabled={!selected||loading}>Reject</button>
              </div>
            </div>
          </section>
        </div>
        )}
        {/* Agent run stepper (always render container to satisfy viewport checks; hide content when not active) */}
        <div id="panel-trace" role="region" aria-label="Run trace" style={{visibility: (isMobile && activeMobileTab!=='run') ? 'hidden' : 'visible', minHeight: 160}}>
          {(!isMobile || activeMobileTab==='run') && (
          <>
            <h3 style={{margin:'12px 0'}}>Agent run</h3>
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
                      <div className="step-title"><span className="status-icon">✓</span>{title}{dur ? <span className="duration"> · {dur}</span> : null}</div>
                      {sum ? <div className="summary">{sum}</div> : null}
                      <button className="payload-toggle" onClick={()=> setExpanded(prev => ({...prev, [i]: !prev[i]})) }>{expanded[i] ? 'Hide payload' : 'View payload'}</button>
                      {expanded[i] && <pre className="payload mono">{JSON.stringify(d, null, 2)}</pre>}
                    </li>
                  )
                })}
              </ul>
            ) : <div>Waiting… Start a run to see steps. Metrics are labeled demo when simulated.</div>}
          </>
          )}
        </div>
        {/* Graph as a tab on mobile */}
        {isMobile && activeMobileTab==='graph' && (
          <div className="graph-disclosure" open={true}>
            <summary>Graph context</summary>
            {subgraph ? <div style={{marginTop:6}}><MiniGraph subgraph={subgraph} /></div> : <div>—</div>}
          </div>
        )}
        </div>
      </div>
      )}

      {!isMobile && (
      <div className="panel graph" role="region" aria-label="Graph context" id="panel-graph">
        <div className="toolbar"><strong>Context</strong></div>
        <div className="graph-body" style={{padding:8}}>
          {subgraph ? (
            <>
              <div className="graph-canvas"><MiniGraph subgraph={subgraph} /></div>
              <div style={{marginTop:8, fontSize:10, color:'var(--muted)'}}>
                <span style={{display:'inline-flex', alignItems:'center', gap:6, marginRight:12}}>
                  <span style={{width:8, height:8, borderRadius:8, background:'var(--accent)', display:'inline-block'}}></span> finding
                </span>
                <span style={{display:'inline-flex', alignItems:'center', gap:6, marginRight:12}}>
                  <span style={{width:8, height:8, borderRadius:8, background:'#4FB1F0', display:'inline-block'}}></span> asset
                </span>
                <span style={{display:'inline-flex', alignItems:'center', gap:6, marginRight:12}}>
                  <span style={{width:8, height:8, borderRadius:8, background:'#E2B93D', display:'inline-block'}}></span> segment
                </span>
                <span style={{display:'inline-flex', alignItems:'center', gap:6, marginRight:12}}>
                  <span style={{width:8, height:8, borderRadius:8, background:'#B084EB', display:'inline-block'}}></span> owner
                </span>
                <span style={{display:'inline-flex', alignItems:'center', gap:6}}>
                  <span style={{width:8, height:8, borderRadius:8, background:'#E5484D', display:'inline-block'}}></span> weakness
                </span>
              </div>
              <div style={{marginTop:8}}>
                <div style={{display:'flex', alignItems:'center', justifyContent:'space-between'}}>
                  <h4 style={{margin:'6px 0'}}>Audit (recent)</h4>
                  <button className="btn small" onClick={refreshAudit}>Refresh</button>
                </div>
                {audit.length ? (
                  <ul className="audit-list" style={{margin:0, maxHeight:180, overflow:'auto'}}>
                    {audit.map((a:any)=> (
                      <li key={a.audit_id} style={{display:'flex', alignItems:'center', gap:8, padding:'4px 0'}}>
                        <span className="status-icon">✓</span>
                        <span style={{color:'var(--muted)'}}>{formatRelative(a.ts)}</span>
                        <span>·</span>
                        <span className="audit-label">{auditLabel(a)}</span>
                      </li>
                    ))}
                  </ul>
                ) : <div>No data yet</div>}
              </div>
            </>
          ) : <div>—</div>}
        </div>
      </div>
      )}
      
    </div>
  )
}

function MiniGraph({subgraph}:{subgraph:any}) {
  const nodes = subgraph?.nodes||[]
  const edges = subgraph?.edges||[]
  const W = 340, H = 260, P = 28
  // simple circle layout
  const N = Math.max(nodes.length, 1)
  const positioned = nodes.map((n:any, i:number) => {
    const angle = (i / N) * Math.PI * 2
    const r = Math.min(W,H)/2 - P
    const cx = W/2 + r * Math.cos(angle)
    const cy = H/2 + r * Math.sin(angle)
    return {...n, cx, cy}
  })
  const byId: Record<string, any> = {}
  positioned.forEach((n:any)=> byId[n.id]=n)
  // color by type
  function colorFor(id: string): string {
    const t = (id.split(':',1)[0] || '').toLowerCase()
    if (t === 'finding') return 'var(--accent)'
    if (t === 'asset') return '#4FB1F0'
    if (t === 'segment') return '#E2B93D'
    if (t === 'owner') return '#B084EB'
    if (t === 'weakness') return '#E5484D'
    return 'var(--muted)'
  }
  return (
    <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Asset graph" preserveAspectRatio="xMidYMid meet">
      <g stroke="var(--border)" strokeWidth="1">
        {edges.map((e:any,i:number)=>{
          const s = byId[e.src], d = byId[e.dst]; if (!s||!d) return null
          return <line key={i} x1={s.cx} y1={s.cy} x2={d.cx} y2={d.cy} />
        })}
      </g>
      <g>
        {positioned.map((n:any)=>(
          <g key={n.id}>
            <circle cx={n.cx} cy={n.cy} r="7" fill="var(--surface-2)" stroke={colorFor(n.id)} />
            <title>{n.id}</title>
            <text x={n.cx+10} y={n.cy+4} fontSize="12" fill="var(--muted)">{String(n.label||n.id).length>20?String(n.label||n.id).slice(0,19)+'…':(n.label||n.id)}</text>
          </g>
        ))}
      </g>
    </svg>
  )
}
