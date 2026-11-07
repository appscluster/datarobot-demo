import React from 'react'
import { go, signIn } from './auth'

function Eye() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" fill="none" stroke="currentColor" strokeWidth="1.75" />
      <circle cx="12" cy="12" r="2.5" fill="none" stroke="currentColor" strokeWidth="1.75" />
    </svg>
  )
}

function EyeOff() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 3l18 18" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
      <path d="M10.5 6.2A10 10 0 0 1 12 6c6.5 0 10 6 10 6a18 18 0 0 1-3.2 3.8M6.1 8.2C3.8 9.8 2 12 2 12s3.5 6 10 6c1.2 0 2.3-.2 3.3-.6" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  )
}

export function LoginPage() {
  const [name, setName] = React.useState('analyst')
  const [password, setPassword] = React.useState('')
  const [showPassword, setShowPassword] = React.useState(false)
  const [error, setError] = React.useState('')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!signIn(name, password)) {
      setError('That sign in does not match the demo desk.')
      return
    }
    go('/brief')
  }

  return (
    <div className="gate">
      <div className="gate-wash" aria-hidden="true">
        <span className="orb orb-a" />
        <span className="orb orb-b" />
        <span className="orb orb-c" />
      </div>
      <form className="gate-card" onSubmit={submit}>
        <a className="gate-back" href="/">Casework</a>
        <h1>Sign in</h1>
        <p className="stage-lead">Sign in to Emirates NBD Demo. Use analyst and demo. This does not call the bank.</p>
        <div className="field">
          <label htmlFor="login-name">Name</label>
          <input id="login-name" value={name} onChange={e => setName(e.target.value)} autoComplete="username" />
        </div>
        <div className="field">
          <label htmlFor="login-password">Password</label>
          <div className="field-secret">
            <input id="login-password" type={showPassword ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" aria-invalid={error ? true : undefined} aria-describedby={error ? 'login-error' : undefined} />
            <button type="button" className="reveal" id="btn-reveal" aria-pressed={showPassword} aria-label={showPassword ? 'Hide password' : 'Show password'} onClick={() => setShowPassword(v => !v)}>
              {showPassword ? <EyeOff /> : <Eye />}
            </button>
          </div>
          {error && <p className="gate-error" id="login-error" role="alert">{error}</p>}
        </div>
        <button className="btn primary" id="btn-login" type="submit">Sign in</button>
      </form>
    </div>
  )
}
