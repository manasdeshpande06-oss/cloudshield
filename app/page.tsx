'use client'

import { useAuth } from '@/lib/auth-context'
import FairGuardDashboard from '@/components/fairguard-dashboard'
import LoginPage from '@/components/login-page'
import TenantDashboard from '@/components/tenant-dashboard'

export default function Page() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)',
          fontFamily: 'Inter, system-ui, sans-serif',
        }}
      >
        <div style={{ textAlign: 'center', color: '#fff' }}>
          <div
            style={{
              width: 48,
              height: 48,
              border: '3px solid rgba(255,255,255,0.2)',
              borderTopColor: '#6366f1',
              borderRadius: '50%',
              animation: 'spin 0.8s linear infinite',
              margin: '0 auto 16px',
            }}
          />
          <p style={{ opacity: 0.7, fontSize: 14 }}>Loading CloudShield…</p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </div>
    )
  }

  if (!user) {
    return <LoginPage />
  }

  // Admin → full platform dashboard
  if (user.role === 'admin') {
    return <FairGuardDashboard />
  }

  // Tenant → scoped tenant dashboard
  return <TenantDashboard />
}
