import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import apiClient from '../api/client'
import type { UserAccount } from '../types/environmentPackage'

const AUTH_KEY = 'opspaw-auth-session'

interface AuthSession {
  access_token: string
  user: UserAccount
}

interface AuthContextValue {
  token: string
  user: UserAccount | null
  isAuthenticated: boolean
  isAdmin: boolean
  isChecking: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function loadSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(AUTH_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function saveSession(session: AuthSession | null) {
  if (session) localStorage.setItem(AUTH_KEY, JSON.stringify(session))
  else localStorage.removeItem(AUTH_KEY)
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(loadSession)
  const [isChecking, setIsChecking] = useState(Boolean(session?.access_token))

  const clearSession = () => {
    setSession(null)
    saveSession(null)
  }

  useEffect(() => {
    let cancelled = false
    const token = session?.access_token
    if (!token) {
      setIsChecking(false)
      return
    }
    setIsChecking(true)
    apiClient.get<{ user: UserAccount }>('/auth/me', { headers: { Authorization: `Bearer ${token}` } })
      .then(({ data }) => {
        if (cancelled) return
        const refreshed = { access_token: token, user: data.user }
        setSession(refreshed)
        saveSession(refreshed)
      })
      .catch(() => {
        if (!cancelled) clearSession()
      })
      .finally(() => {
        if (!cancelled) setIsChecking(false)
      })
    return () => { cancelled = true }
  }, [session?.access_token])

  const value = useMemo<AuthContextValue>(() => ({
    token: session?.access_token || '',
    user: session?.user || null,
    isAuthenticated: Boolean(session?.access_token && session.user),
    isAdmin: session?.user?.role === 'admin' || session?.user?.username === 'admin',
    isChecking,
    login: async (username: string, password: string) => {
      const { data } = await apiClient.post<AuthSession>('/auth/login', { username, password })
      setSession(data)
      saveSession(data)
    },
    logout: clearSession,
  }), [isChecking, session])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
