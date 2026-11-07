import React from 'react'
import AOS from 'aos'

const WORK = [
  {
    title: 'Hold the new loan model',
    body: 'Emirates NBD Demo is a UAE bank that offers personal loans. They want loan model v3 to score personal loans. It misses 4 more defaults per 100 than the model already scoring applications.',
  },
  {
    title: 'The agent reads the related models',
    body: 'v3 and v2 score the same personal loans. The reply cites both. A keyword search would miss that hop.',
  },
  {
    title: 'You decide. Nothing is deployed.',
    body: 'Approve, escalate, or reject. Another customer is refused. Shutting the live model down is refused.',
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
          <h1 data-aos="fade-up">Should this bank put the new credit model live?</h1>
          <p data-aos="fade-up" data-aos-delay="120">
            Consumer lending. Emirates NBD Demo scores personal loan applications. The new model misses 4 more defaults per 100 than the one already in use. Casework drafts the reply to credit risk. You approve it. Nothing is deployed.
          </p>
          <div className="hero-actions" data-aos="fade-up" data-aos-delay="220">
            <a className="btn primary" href="/login">Sign in</a>
            <a className="btn" href="#work">See the work</a>
          </div>
        </div>
        <aside className="hero-aside" data-aos="fade-left" data-aos-delay="180">
          <div className="pill sev-high">high</div>
          <h2>Hold the new loan model</h2>
          <p>Emirates NBD Demo wants loan model v3 to score personal loans. It misses 4 more defaults per 100 than the model scoring applications today.</p>
          <p className="hint">Loan model v3 and Loan model v2 both score Personal loans.</p>
        </aside>
      </section>

      <section id="work" className="land-section">
        <h2 data-aos="fade-up">The work on the desk</h2>
        <p className="stage-lead" data-aos="fade-up" data-aos-delay="80">
          Emirates NBD Demo is a UAE bank that offers personal loans. Seven open requests. The first one is the personal-loan decision.
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
