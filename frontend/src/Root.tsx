import { App } from './App'
import { go, isAuthed, signOut } from './auth'
import { BriefPage } from './BriefPage'
import { LandingPage } from './LandingPage'
import { LoginPage } from './LoginPage'

function path(): string {
  const raw = window.location.pathname.replace(/\/$/, '')
  return raw || '/'
}

export function Root() {
  const here = path()
  if (here === '/login') return <LoginPage />
  if (here === '/brief') return isAuthed() ? <BriefPage /> : <LoginPage />
  if (here === '/desk') {
    if (!isAuthed()) return <LoginPage />
    return <App onSignOut={() => { signOut(); go('/') }} />
  }
  return <LandingPage />
}
