'use client'

import React, { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { ShieldAlert, ArrowLeft } from 'lucide-react'
import { useAuth } from '@/lib/auth-context'
import FairGuardDashboard from '@/components/fairguard-dashboard'

interface AdminRouteWrapperProps {
  initialTab?: string
}

export default function AdminRouteWrapper({ initialTab = 'Overview' }: AdminRouteWrapperProps) {
  const { user, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login')
    }
  }, [user, loading, router])

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f8fafc',
        fontFamily: 'Inter, sans-serif'
      }}>
        <div style={{ textAlign: 'center', color: '#64748b' }}>
          <div style={{
            width: 36,
            height: 36,
            border: '3px solid #e2e8f0',
            borderTopColor: '#2563eb',
            borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
            margin: '0 auto 12px'
          }} />
          <p style={{ fontSize: 13 }}>Verifying platform administrator credentials…</p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </div>
    )
  }

  if (!user) {
    return null
  }

  // Tenant trying to access admin dashboard
  if (user.role !== 'admin') {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f8fafc',
        fontFamily: 'Inter, sans-serif',
        padding: 20
      }}>
        <div style={{
          maxWidth: 480,
          background: '#fff',
          borderRadius: 12,
          border: '1px solid #fee2e2',
          padding: '32px 28px',
          textAlign: 'center',
          boxShadow: '0 10px 25px -5px rgba(0,0,0,0.05)'
        }}>
          <div style={{
            width: 52,
            height: 52,
            background: '#fef2f2',
            color: '#dc2626',
            borderRadius: 12,
            display: 'grid',
            placeItems: 'center',
            margin: '0 auto 16px'
          }}>
            <ShieldAlert size={28} />
          </div>
          <h2 style={{
            fontFamily: 'DM Serif Display, Georgia, serif',
            fontSize: 22,
            margin: '0 0 8px',
            color: '#111827'
          }}>
            403 — Administrator Access Required
          </h2>
          <p style={{ fontSize: 13, color: '#4b5563', lineHeight: 1.6, margin: '0 0 24px' }}>
            Your account is authenticated as <strong>{user.displayName}</strong> (Tenant).
            Administrative views are restricted to platform operators.
          </p>
          <button
            onClick={() => router.push('/tenant')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '10px 18px',
              background: '#2563eb',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            <ArrowLeft size={15} /> Return to Tenant Dashboard
          </button>
        </div>
      </div>
    )
  }

  return <FairGuardDashboard initialTab={initialTab} />
}
