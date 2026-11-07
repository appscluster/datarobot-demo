import React from 'react'
import AOS from 'aos'

const AUDIENCE = [
  {
    title: 'You, the analyst',
    body: 'The only person who signs in. You open a request, read the draft, and Approve, Escalate, or Reject.',
  },
  {
    title: 'Credit risk',
    body: 'They own loan model v2 and loan model v3. They need a hold or promote answer. They do not sign in. Approve stores the reply for them.',
  },
  {
    title: 'Lending ops',
    body: 'They own the application file and the weekly credit review. Their requests sit in the same queue.',
  },
  {
    title: 'Pod lead',
    body: 'Escalate records a case for your lead. It does not send a message, and it does not contact an applicant.',
  },
  {
    title: 'Applicant',
    body: 'A person who asked the bank for a personal loan. They are a row in the file, not a user. This desk never pays a loan.',
  },
  {
    title: 'Another bank',
    body: 'Not served here. A request to read their book is refused and written to the audit.',
  },
]

const WORK = [
  {
    title: 'Hold the new loan model',
    body: 'Credit risk asked if loan model v3 may score personal loans. It misses 4 more defaults per 100 than loan model v2, which scores those loans today.',
  },
  {
    title: 'The agent reads the related models',
    body: 'v3 is proposed for the same personal loans that v2 scores today. The reply cites both models. A keyword search would miss that link.',
  },
  {
    title: 'You decide. Nothing is deployed.',
    body: 'Approve, escalate, or reject. The desk does not approve a person\'s loan. Another bank is refused. Shutting the live model down is refused.',
  },
]

const PILLARS = [
  { title: 'Problem solving', body: 'The category is consumer lending. A bank is waiting to switch the model that scores personal loans.' },
  { title: 'Strategic vision', body: 'The same promote or hold loop is how a DataRobot customer in lending would govern a model before it scores real applications.' },
  { title: 'Technical credibility', body: 'React, FastAPI, and a code first LangGraph loop. The graph, the checker, and the audit are in the running app.' },
  { title: 'Creativity', body: 'The agent drafts a reply a person can argue with. It does not hide the decision inside a chat box.' },
]

export function LandingPage() {
  React.useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    AOS.init({
      duration: reduced ? 0 : 900,
      easing: 'ease-out-cubic',
      once: true,
      offset: 48,
      disable: reduced,
    })
  }, [])

  return (
    <div className="landing">
      <header className="land-bar">
        <strong className="brand">Casework</strong>
        <span className="demo-badge">Demo</span>
        <a className="btn small" href="/login">Sign in</a>
      </header>

      <section className="hero">
        <div>
          <h1 data-aos="fade-up">The analyst's desk for a loan model decision.</h1>
          <p data-aos="fade-up" data-aos-delay="120">
            Casework is for one person: the analyst at Emirates NBD Demo, a fictional UAE bank that offers personal loans. Credit risk wants to know if loan model v3 may score those loans. The agent drafts the reply. You approve it. The desk does not approve a person's loan, pay a loan, or change the live model.
          </p>
          <div className="hero-actions" data-aos="fade-up" data-aos-delay="220">
            <a className="btn primary" href="/login">Sign in</a>
            <a className="btn" href="#who">Who it is for</a>
          </div>
        </div>
        <aside className="hero-aside" data-aos="fade-left" data-aos-delay="180">
          <div className="pill sev-high">high</div>
          <p className="hint">One request on the desk. Not a loan application.</p>
          <h2>Hold the new loan model</h2>
          <p>Credit risk wants loan model v3 to score personal loans. On the holdout, v3 misses 4 more defaults per 100 than loan model v2. v2 is the model scoring applications today. This request says hold v3.</p>
          <p className="hint">v3 is the challenger for that same book. It is not scoring live applications.</p>
        </aside>
      </section>

      <section id="who" className="land-section">
        <h2 data-aos="fade-up">Who it is for</h2>
        <p className="stage-lead" data-aos="fade-up" data-aos-delay="80">
          The reply is for bank staff. Applicants are the subject of the file. They are not the audience.
        </p>
        <div className="audience">
          {AUDIENCE.map((item, index) => (
            <article key={item.title} className="pillar" data-aos="fade-up" data-aos-delay={index * 80}>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="work" className="land-section">
        <h2 data-aos="fade-up">The work on the desk</h2>
        <p className="stage-lead" data-aos="fade-up" data-aos-delay="80">
          The queue is this bank's open requests. The first one is whether v3 may score personal loans.
        </p>
        {WORK.map((item, index) => (
          <article key={item.title} className="land-row" data-aos="fade-up" data-aos-delay={index * 100}>
            <h3>{item.title}</h3>
            <p>{item.body}</p>
          </article>
        ))}
      </section>

      <section id="platform" className="land-section">
        <h2 data-aos="fade-up">What the interview is scoring</h2>
        <div className="pillars">
          {PILLARS.map((item, index) => (
            <article key={item.title} className="pillar" data-aos="fade-up" data-aos-delay={index * 120}>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="land-section">
        <div className="land-cta" data-aos="zoom-in" data-aos-duration="700">
          <h2>Open the Emirates NBD Demo desk</h2>
          <p>Sign in with the demo analyst. The next page maps this app to the assignment, then you open today's requests.</p>
          <a className="btn primary" href="/login">Sign in</a>
        </div>
      </section>
    </div>
  )
}
