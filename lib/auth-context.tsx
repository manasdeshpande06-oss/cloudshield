/**
 * CloudShield FairGuard — Authentication Context
 * 
 * Provides JWT-based auth state, login/logout actions, and role-based access.
 * Tokens are stored in localStorage (demo) — use httpOnly cookies in production.
 */
'use client'

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { fetchApi } from './api'

export type UserRole = 'admin' | 'tenant' | null

export interface AuthUser {
  role: UserRole
  displayName: string
  companyId?: string | null
  companyName?: string | null
  companySlug?: string | null
  token: string
  expiresIn: number
}

interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  isAdmin: boolean
  isTenant: boolean
  companyId: string | null
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
  isAdmin: false,
  isTenant: false,
  companyId: null,
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  // Restore session from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem('fg_auth')
      if (stored) {
        const parsed = JSON.parse(stored) as AuthUser
        setUser(parsed)
      }
    } catch {
      localStorage.removeItem('fg_auth')
    } finally {
      setLoading(false)
    }
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const response = await fetchApi<{
      access_token: string
      role: string
      company_id?: string | null
      company_name?: string | null
      company_slug?: string | null
      display_name: string
      expires_in: number
    }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })

    const authUser: AuthUser = {
      role: response.role as UserRole,
      displayName: response.display_name,
      companyId: response.company_id,
      companyName: response.company_name,
      companySlug: response.company_slug,
      token: response.access_token,
      expiresIn: response.expires_in,
    }

    localStorage.setItem('fg_auth', JSON.stringify(authUser))
    setUser(authUser)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('fg_auth')
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        logout,
        isAdmin: user?.role === 'admin',
        isTenant: user?.role === 'tenant',
        companyId: user?.companyId ?? null,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
