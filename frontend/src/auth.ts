const KEY = 'casework-session'

export function isAuthed(): boolean {
  return localStorage.getItem(KEY) === 'analyst'
}

export function signIn(name: string, password: string): boolean {
  if (name.trim().toLowerCase() === 'analyst' && password === 'demo') {
    localStorage.setItem(KEY, 'analyst')
    return true
  }
  return false
}

export function signOut(): void {
  localStorage.removeItem(KEY)
}

export function go(path: string): void {
  window.location.assign(path)
}
