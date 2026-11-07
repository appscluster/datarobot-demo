import { go, signOut } from './auth'

const BEATS = [
  {
    title: 'The problem',
    body: 'The category is consumer lending. Emirates NBD Demo is a UAE bank that offers personal loans. They want loan model v3 to score those loans, and it misses 4 more defaults per 100 than the model already scoring applications. A consultant who only reads the title will miss that v2 is still scoring that same book of loans.',
  },
  {
    title: 'The solution',
    body: 'The app is React and FastAPI, with a code first LangGraph loop: plan, read the graph, rank, draft, check. LangGraph keeps that path testable. The draft step asks OmniRoute for the reply. The graph answers which other model shares the use case. The checker requires a citation. The agent never deploys.',
  },
  {
    title: 'The live demo',
    body: 'Open Hold the new loan model. Draft the reply. You should see v3 and v2 on Personal loans, a high priority, and a reply that says do not promote. Then approve it. Then refuse another customer, and refuse shutting the live model down.',
  },
  {
    title: 'Challenges and learnings',
    body: 'A draft without a citation is rejected by the checker. A request for another tenant is refused and audited. The reply comes from the model through OmniRoute, and the trace shows that call\'s token count. The build is a working prototype, not a production system.',
  },
  {
    title: 'The vision',
    body: 'A DataRobot customer in consumer lending has this decision every time a new credit model is ready. Productize the loop as a governed template: one bank, a graph of the models, a cited draft, a human decision, and an audit. Scale the template. Do not skip the person.',
  },
]

const CODE_FIRST = [
  { name: 'Start', body: 'Draft reply calls run_triage in agent/runner.py with this bank and the open case.' },
  { name: 'Planner', body: 'Checks the request is still inside Emirates NBD Demo. A cross tenant request stops here.' },
  { name: 'Operator', body: 'Reads the case from SQLite GraphRAG, ranks it, and asks OmniRoute for the reply. LangChain Core builds that prompt in code.' },
  { name: 'Checker', body: 'Rejects a draft that cites nothing in the graph.' },
  { name: 'End', body: 'The run returns the draft. Approve, Escalate, or Reject is a person, after the graph has finished.' },
]

const SERVED = [
  {
    name: 'Credit risk',
    who: 'The team inside the bank that owns loan model v2 and loan model v3. They need a hold or promote answer before v3 scores live applications.',
    how: 'They do not sign in. The analyst opens the case, the agent drafts a reply that cites both models, and Approve stores that reply for credit risk. Nothing is emailed, and the model that scores loans stays v2.',
  },
  {
    name: 'Lending ops',
    who: 'The team that owns the application file, the weekly credit review, and the open retrain note.',
    how: 'Their requests sit in the same queue. The draft names the missing columns and the review that still has no owner. A request to rescore production is refused.',
  },
  {
    name: 'Casework analyst',
    who: 'The person signed in on this desk. They are the only user of the product.',
    how: 'They pick a request, watch the agent plan, read the graph, and draft through OmniRoute, then Approve, Escalate, or Reject. The checker blocks a reply that cites nothing.',
  },
  {
    name: 'Pod lead',
    who: 'The analyst\'s lead, when a case should not be closed on the desk.',
    how: 'Escalate records the case for the pod lead. It does not send a message, and it does not contact an applicant.',
  },
  {
    name: 'Applicant',
    who: 'A person who asked the bank for a personal loan. They are a row in the bank\'s application file, not a user of Casework.',
    how: 'They apply at the bank, outside this product. This desk never shows them a decision and never pays a loan. The file is why the model choice and the missing columns matter.',
  },
  {
    name: 'Another bank',
    who: 'A second customer on the same platform. This desk is Emirates NBD Demo only.',
    how: 'Their findings stay in their own tenant. A request from this desk to read them is refused and written to the audit.',
  },
]

const PATH = [
  { name: 'Intake', body: 'Lending ops receives the application file. Missing income and loan amount opens that case. An empty file invents no rows.' },
  { name: 'Scoring', body: 'Loan model v2 scores the book, including the west region. Nightly scoring has no owner.' },
  { name: 'Evidence', body: 'The holdout fact stays 4 more defaults per 100. Debt to income left the file, and loan model v3 still expects it.' },
  { name: 'Casework', body: 'The analyst opens the case. The agent plans, reads the graph, and drafts a reply through OmniRoute. The checker demands a real citation.' },
  { name: 'Decision', body: 'Approve stores the reply for credit risk or lending ops. Escalate records it for the pod lead. Reject returns it to the analyst. Nothing is sent.' },
  { name: 'Promotion', body: 'A request to put v3 live is refused. Promotion does not change v2. Loan model v2 stays the model that scores loans.' },
  { name: 'Lending ops', body: 'The weekly credit review has no owner. The retrain note has not started. A production rescore is refused.' },
  { name: 'Tenant wall', body: 'No pipeline reads another bank\'s book. A cross tenant request is refused and written to the audit.' },
]

const TOOLS = [
  {
    name: 'React',
    how: 'The landing page, the sign in, this explanation, and the analyst desk are React 18 components.',
    why: 'The assignment asks for a complete application a person can use, not a script that only prints a reply.',
  },
  {
    name: 'Vite',
    how: 'Vite builds the React app for the frontend container and can serve it on port 43123 during development.',
    why: 'The desk has to build cleanly into a static bundle the container can host.',
  },
  {
    name: 'serve',
    how: 'The frontend image uses the serve package to host the built files on port 43123.',
    why: 'The demo should open in a browser from one Compose stack, with no extra web server to install.',
  },
  {
    name: 'AOS',
    how: 'The landing page uses AOS to fade sections in as you scroll. It stays off when the browser asks for reduced motion.',
    why: 'The public page has to tell the lending story in order, without motion that fights the reader.',
  },
  {
    name: 'Source Sans 3',
    how: 'Fontsource ships Source Sans 3 with the app for the reading text.',
    why: 'The type stays inside the bundle, so the desk does not depend on a font service.',
  },
  {
    name: 'JetBrains Mono',
    how: 'Fontsource ships JetBrains Mono for finding ids, payloads, and other fixed width text.',
    why: 'Ids and payloads stay aligned and readable next to the prose.',
  },
  {
    name: 'FastAPI',
    how: 'FastAPI serves the session, the request queue, the graph, the run, the scope check, the decision, and the audit.',
    why: 'The agent needs one backend the desk can call, with the tenant bound on the server.',
  },
  {
    name: 'Uvicorn',
    how: 'Uvicorn runs the FastAPI app on port 54123.',
    why: 'The API has to stay up as its own process beside the frontend.',
  },
  {
    name: 'Pydantic',
    how: 'FastAPI uses Pydantic to read JSON bodies before a route runs.',
    why: 'A bad payload should fail at the door instead of halfway through a run.',
  },
  {
    name: 'LangGraph',
    how: 'The triage run is a LangGraph graph: planner, then operator, then checker.',
    why: 'The assignment asks for a code first agent. A fixed graph keeps that loop testable and visible on the desk.',
  },
  {
    name: 'LangChain Core',
    how: 'LangGraph runs on LangChain Core. The project pins that library next to LangGraph.',
    why: 'The agent loop needs that runtime to compile and invoke the graph.',
  },
  {
    name: 'sse-starlette',
    how: 'After Draft reply, the desk opens a Server Sent Events stream at /runs/{id}/events and paints each step as it arrives.',
    why: 'The analyst should see the plan, the graph read, the rank, the model call, and the check, not one silent wait.',
  },
  {
    name: 'SQLite',
    how: 'SQLite holds the asset graph, the audit log, and human decisions under backend/var.',
    why: 'One file is enough for the demo, and every row stays with its tenant. There is no separate database to operate.',
  },
  {
    name: 'Docker Compose',
    how: 'Compose builds and runs the frontend on port 43123 and the backend on port 54123.',
    why: 'The interview demo should start as one stack.',
  },
  {
    name: 'OmniRoute',
    how: 'The draft step calls the local OmniRoute gateway at /v1/chat/completions. The model id is gh/gpt-5.6-terra. The trace shows the model name and the token count from that response. This repo does not change OmniRoute.',
    why: 'The reply has to be written by a model. OmniRoute is the gateway already running here, so the agent does not keep provider keys of its own.',
  },
  {
    name: 'pytest',
    how: 'pytest runs the scope refusals, the seeded lending story, the reply parser, and the page contracts.',
    why: 'The guard and the story have to stay true when the desk changes.',
  },
  {
    name: 'Playwright',
    how: 'Playwright opens the desk, signs in, drafts a reply, and checks the refusal path.',
    why: 'The demo is a click path. A test that only calls the API would miss a broken button.',
  },
  {
    name: 'OpenTelemetry',
    how: 'Each triage run opens an OpenTelemetry span named casework.run. The span carries the finding, the model, the token counts, and whether the checker passed. When DATAROBOT_API_TOKEN, DATAROBOT_ENTITY_ID, and a DataRobot endpoint are set, that span is sent to DataRobot.',
    why: 'DataRobot external agent monitoring reads these spans. The run reports them now. Nothing is sent until those three values are set.',
  },
]

export function BriefPage() {
  return (
    <div className="brief">
      <header className="land-bar">
        <strong className="brand">Casework</strong>
        <span className="demo-badge">Demo</span>
        <span className="tenant-badge">Emirates NBD Demo</span>
        <button className="btn small" type="button" onClick={() => { signOut(); go('/') }}>Sign out</button>
      </header>
      <main className="brief-body">
        <h1>How this meets the assignment</h1>
        <p className="stage-lead">
          The brief asks for a problem, a code first agent with a frontend and a backend, and a short talk: the problem, the solution, a live demo, the challenges, and how you would productize it for a DataRobot customer.
        </p>
        <div className="brief-grid">
          {BEATS.map(beat => (
            <article key={beat.title} className="brief-card">
              <h2>{beat.title}</h2>
              <p>{beat.body}</p>
            </article>
          ))}
        </div>
        <section aria-labelledby="code-first-heading">
          <h2 id="code-first-heading">Code first</h2>
          <p className="stage-lead">
            The agent is a Python program. LangGraph compiles three functions, planner then operator then checker, from agent/runner.py. The state they share is the typed TriageState in that file: tenant, case, subgraph, rank, draft, and whether the planner refused. Tests call the same functions.
          </p>
          <ol className="code-first-flow">
            {CODE_FIRST.map(step => (
              <li key={step.name}>
                <strong>{step.name}</strong>
                <p>{step.body}</p>
              </li>
            ))}
          </ol>
        </section>
        <section aria-labelledby="served-heading">
          <h2 id="served-heading">Who this serves</h2>
          <p className="stage-lead">
            Casework serves the bank staff who have to decide whether a new credit model may score personal loans. Applicants are the subject of the file. They are not the audience of the reply.
          </p>
          <div className="serve-grid">
            {SERVED.map(person => (
              <article key={person.name} className="brief-card">
                <h2>{person.name}</h2>
                <p><strong>Who.</strong> {person.who}</p>
                <p><strong>How.</strong> {person.how}</p>
              </article>
            ))}
          </div>
        </section>
        <section aria-labelledby="path-heading">
          <h2 id="path-heading">The path</h2>
          <p className="stage-lead">
            Applicants exist only as rows in the file. The reply is for credit risk or lending ops. Promotion does not change v2.
          </p>
          <div className="serve-grid">
            {PATH.map(step => (
              <article key={step.name} className="brief-card">
                <h2>{step.name}</h2>
                <p>{step.body}</p>
              </article>
            ))}
          </div>
        </section>
        <section aria-labelledby="tools-heading">
          <h2 id="tools-heading">The tools</h2>
          <p className="stage-lead">The tools this running desk uses, what each one does here, and why it is in the stack.</p>
          <div className="tool-grid">
            {TOOLS.map(tool => (
              <article key={tool.name} className="brief-card">
                <h2>{tool.name}</h2>
                <p><strong>How.</strong> {tool.how}</p>
                <p><strong>Why.</strong> {tool.why}</p>
              </article>
            ))}
          </div>
        </section>
        <button className="btn primary" id="btn-open-desk" type="button" onClick={() => go('/desk')}>Open today's requests</button>
      </main>
    </div>
  )
}
