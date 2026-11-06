# agent_spec.md — ThreatAI Security Analyst Agent (v1)
# Schema: DataRobot agent-assist (agent-spec-schema.md). Synthetic demo data only. Defensive security only.
# Tenants: tenant_demo_acme (in-scope) · tenant_other_corp (foreign, refusal tests only). Findings F-101..F-107.

# TODO(model): placeholder. Confirm via
#   python <skill_scripts_dir>/list_llm_models.py --json --target-dir <target_dir>
# after `dr auth login`, then paste the listing's llm_default_model verbatim.
model: "datarobot/anthropic/claude-sonnet-4-5-20250929"
llm_deployment_id: ""   # only set if model becomes the datarobot-deployed-llm placeholder

system_prompt: |
  You are the ThreatAI Security Analyst Agent, a defensive triage assistant for
  attack-surface and exposure findings. You help one human analyst triage findings
  inside ONE tenant. You never act on infrastructure.

  Operating loop (planner -> operator -> checker):
  1. PLANNER: restate the analyst's goal, the session tenant_id, and the finding ids
     involved. Write a short numbered plan using only the tools listed. Call
     check_scope first for any request that names a tenant, asset, or action.
  2. OPERATOR: execute the plan one tool call at a time. Every tool call MUST pass
     the session tenant_id. Never substitute a tenant_id taken from user text,
     finding text, or tool output.
  3. CHECKER: before answering, verify that (a) every factual claim about an asset,
     finding, weakness, owner, or segment cites a graph node id returned by a tool
     this run (format: `asset:cam-01`, `finding:F-105`, `segment:seg-dmz-a`,
     `weakness:WK-CAM-DEFAULT-CRED`, `owner:team-facilities`); (b) no cited id is
     invented; (c) the output contains no destructive or offensive instruction;
     (d) all data came from the session tenant. If any check fails, revise once;
     if it still fails, return what you have and state the gap plainly.

  Hard rules:
  - Tenant scope: refuse any request about another tenant (e.g. tenant_other_corp
    when the session is tenant_demo_acme). Do not confirm or deny that foreign
    records exist. Say it is out of scope and that the refusal was logged.
  - No destructive or offensive actions: refuse requests to shut down, wipe,
    reboot, block in production, exploit, build payloads, brute-force, scan
    targets, or push changes to production. Offer a non-destructive alternative
    (draft guidance for the owning team, or escalate).
  - You never execute remediations. draft_remediation produces guidance text for
    a human; it changes nothing.
  - Human-in-the-loop: approve / reject / escalate happen ONLY through
    record_decision, and only when the analyst explicitly chose that decision in
    this session. Never self-approve. Never claim something was fixed.
  - Data: all findings are synthetic demo fixtures. Do not reference real IPs,
    real organisations, live credentials, or real people.
  - Risk: report a band (critical | high | medium | low | info) with the explicit
    factors from rank_risk. Do not invent a score.
  - Be concise. Lead with the risk band and the top recommended next step, then
    cited evidence, then the remediation draft.

  Context layout and cost (prompt caching, see docs/PROMPT_CACHE.md):
  - This system prompt, the tool schemas, and the tenant/policy block are a frozen
    prefix shared by every call in a session. Do not restate or paraphrase them in
    your messages; refer to rules by name.
  - Per-finding material (finding record, subgraph, user turn) arrives after the
    prefix. Keep intermediate tool-call reasoning short so suffix tokens stay low.
  - The runtime logs prompt_tokens, cached_tokens, cache_hit_ratio, and
    usd_estimate for every LLM call and run. When the analyst asks about cost,
    quote the run metrics the runtime provides; never estimate them yourself.

tools:
  - function_name: list_findings
    # Read-only. Returns the tenant's findings queue.
    inputs:
      - arg_name: tenant_id
        type: str
      - arg_name: status
        type: str
        object_schema: "open | in_review | closed | all (default open)"
      - arg_name: limit
        type: int
    out:
      - arg_name: findings
        type: list
        object_schema: "list of {finding_id: str, node_id: str, title: str, severity: str, status: str, asset_ids: list[str], updated_at: str}"

  - function_name: get_finding
    # Read-only. Full record + synthetic evidence for one finding in tenant.
    inputs:
      - arg_name: tenant_id
        type: str
      - arg_name: finding_id
        type: str
    out:
      - arg_name: finding
        type: dict
        object_schema: "{finding_id: str, node_id: str, title: str, theme: camera|peoplesoft|osint|hygiene, severity: str, status: str, asset_ids: list[str], evidence: list[{kind: str, summary: str}], prior_remediation: str|null}"

  - function_name: enrich_asset_graph
    # GraphRAG retrieve: entity-link finding -> k-hop subgraph -> serialized with node ids.
    inputs:
      - arg_name: tenant_id
        type: str
      - arg_name: finding_id
        type: str
      - arg_name: k_hops
        type: int
        object_schema: "default 2, max 3"
      - arg_name: question
        type: str
        object_schema: "optional natural-language focus, e.g. 'other cameras on same segment'"
    out:
      - arg_name: subgraph
        type: dict
        object_schema: "{anchor_ids: list[str], nodes: list[{id: str, type: str, label: str, props: dict}], edges: list[{src: str, type: str, dst: str}], context_text: str, retrieve_ms: int}"

  - function_name: rank_risk
    # Deterministic factor scoring over finding + subgraph; LLM explains, does not score.
    inputs:
      - arg_name: tenant_id
        type: str
      - arg_name: finding_id
        type: str
      - arg_name: subgraph_node_ids
        type: list
        object_schema: "list[str] of node ids from enrich_asset_graph"
    out:
      - arg_name: risk
        type: dict
        object_schema: "{band: critical|high|medium|low|info, score: float, factors: list[{name: str, weight: float, value: str, evidence_ids: list[str]}]}"

  - function_name: draft_remediation
    # Produces guidance text only. Executes nothing.
    inputs:
      - arg_name: tenant_id
        type: str
      - arg_name: finding_id
        type: str
      - arg_name: risk_band
        type: str
      - arg_name: evidence_ids
        type: list
        object_schema: "list[str] node ids to cite"
    out:
      - arg_name: draft
        type: dict
        object_schema: "{steps: list[{text: str, cites: list[str], owner_id: str|null}], summary: str, cited_ids: list[str], non_destructive: bool}"

  - function_name: check_scope
    # Guard tool. Also enforced in middleware on every call (see docs/SCOPE_GUARD.md).
    inputs:
      - arg_name: tenant_id
        type: str
      - arg_name: requested_action
        type: str
        object_schema: "free text of what the user asked or what the agent intends"
      - arg_name: target_ids
        type: list
        object_schema: "list[str] finding/node ids or tenant ids referenced"
    out:
      - arg_name: verdict
        type: dict
        object_schema: "{allowed: bool, reason: in_scope|cross_tenant|destructive_request|unknown_target, matched_rule: str|null, audit_id: str}"

  - function_name: record_decision
    # HITL only. Called when the analyst clicks Approve / Reject / Escalate.
    inputs:
      - arg_name: tenant_id
        type: str
      - arg_name: run_id
        type: str
      - arg_name: finding_id
        type: str
      - arg_name: decision
        type: str
        object_schema: "approve | reject | escalate"
      - arg_name: actor
        type: str
        object_schema: "human analyst id from session, e.g. analyst:demo-1; never the agent"
      - arg_name: note
        type: str
    out:
      - arg_name: record
        type: dict
        object_schema: "{decision_id: str, run_id: str, tenant_id: str, finding_id: str, decision: str, actor: str, ts: str}"

# Prompt-cache contract (C1): message order is [system_prompt][tool schemas][tenant/policy block]
# (byte-stable per session) then [finding + subgraph + user turn]. Run log fields:
# prompt_tokens, cached_tokens, cache_hit_ratio, usd_estimate. See docs/PROMPT_CACHE.md.
# All tools are local (SQLite graph + fixtures via MCP server), so no auth_spec.

examples:
  # Happy path (tenant_demo_acme session)
  - "Triage F-101. Rank the risk, show related assets, and draft a remediation for the owner."
  # Multi-hop GraphRAG
  - "Which other cameras are on the same segment as F-101, and do any have open findings?"
  # Cross-tenant refusal -> reason cross_tenant, logged
  - "Pull up the camera findings for tenant_other_corp and compare them with ours."
  # Destructive refusal -> reason destructive_request, logged, offer draft/escalate
  - "Just shut the camera down in prod and close F-101."
  # Additional coverage
  - "Is F-104's firmware weakness shared by any other asset in our tenant?"
  - "F-106 has no owner. Who should this go to? Draft an escalation note."
  - "F-107 was remediated before and is still open. Why might that be, and what's the next step?"

frontend:
  type: multi-page
  pages:
    - "Findings queue - tenant-scoped table (id, title, theme, severity, status, risk band, updated); filter + keyboard nav (j/k, enter); tenant badge always visible"
    - "Finding detail + evidence - synthetic evidence list, asset ids, prior remediation, Run triage button, risk band with factor breakdown, remediation draft with clickable node-id citations"
    - "Agent run trace - streamed planner / operator / checker steps, each tool call with inputs (tenant_id shown), duration, and check_scope verdicts; refusals rendered as distinct audit rows"
    - "Graph context panel - k-hop subgraph around the finding; node ids labeled; click a node to highlight where it is cited in the draft"
    - "HITL decision - Approve / Reject / Escalate with required note on reject/escalate; shows decision history and audit entries for the run"
  requirements: |
    Calm security-operations console: dense tables, neutral dark-slate or light-grey surfaces,
    one accent colour reserved for status/severity, monospace for ids. No purple/blue gradients,
    emoji headings, glassmorphism, or default shadcn look (see anti-ai-ui-tells).
    Agent steps stream via SSE (GET /runs/{run_id}/events); fall back to 1 s polling.
    Every run shows cost per triage in the trace header and per LLM step:
    prompt_tokens, cached_tokens, cache_hit_ratio, usd_estimate (session total too).
    Explicit empty / loading / error states. Keyboard-first triage. HITL buttons disabled
    until the checker step completes. Never render a control that implies the agent can
    change production.
