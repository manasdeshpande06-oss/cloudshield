'use client'

import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Shield, Eye, EyeOff, Zap, Lock, ArrowRight, CheckCircle2, AlertTriangle, LogOut } from 'lucide-react'
import { useAuth } from '@/lib/auth-context'
import { fetchApi } from '@/lib/api'

interface DemoCredential {
  company: string
  username: string
  password: string
  role: string
}

export default function LoginPage() {
  const { user, login, logout } = useAuth()
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [credentials, setCredentials] = useState<DemoCredential[]>([])
  const [activeParticle, setActiveParticle] = useState(0)

  useEffect(() => {
    // Load demo credentials from backend
    fetchApi<{ demo_credentials: DemoCredential[] }>('/auth/credentials')
      .then((r) => setCredentials(r.demo_credentials.slice(0, 6))) // admin + tenants
      .catch(() => {
        // fallback
        setCredentials([
          { company: 'CloudShield Platform', username: 'admin', password: 'admin', role: 'admin' },
          { company: 'Shop A Commerce', username: 'shop_a', password: 'shop_a', role: 'tenant' },
          { company: 'Game B Interactive', username: 'game_b', password: 'game_b', role: 'tenant' },
          { company: 'Food C Delivery', username: 'food_c', password: 'food_c', role: 'tenant' },
          { company: 'Northstar Analytics', username: 'northstar', password: 'fg_demo_8246e5e55435a942', role: 'tenant' },
        ])
      })

    // Animate the particle counter
    const t = setInterval(() => setActiveParticle((n) => (n + 1) % 5), 800)
    return () => clearInterval(t)
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username || !password) {
      setError('Please enter your username and password.')
      return
    }
    setLoading(true)
    setError('')
    try {
      await login(username, password)
      const stored = typeof window !== 'undefined' ? localStorage.getItem('fg_auth') : null
      if (stored) {
        const parsed = JSON.parse(stored)
        if (parsed.role === 'admin') {
          router.push('/admin')
        } else {
          router.push('/tenant')
        }
      }
    } catch (err: any) {
      const msg = err?.message || ''
      if (msg.includes('401') || msg.includes('Invalid')) {
        setError('Invalid credentials. Try one of the demo accounts below.')
      } else {
        setError('Backend unreachable. Make sure the FastAPI server is running on port 8000.')
      }
    } finally {
      setLoading(false)
    }
  }

  const quickLogin = (cred: DemoCredential) => {
    setUsername(cred.username)
    setPassword(cred.password)
    setError('')
  }

  return (
    <div className="login-root">
      {/* Animated background */}
      <div className="login-bg">
        <div className="login-bg-blob blob-1" />
        <div className="login-bg-blob blob-2" />
        <div className="login-bg-blob blob-3" />
        <div className="login-grid" />
      </div>

      {/* Left panel — branding */}
      <div className="login-left">
        <div className="login-brand">
          <div className="login-logo">
            <Shield size={32} />
          </div>
          <div>
            <div className="login-product-name">CloudShield</div>
            <div className="login-product-sub">FairGuard Platform</div>
          </div>
        </div>

        <div className="login-hero">
          <h1 className="login-hero-title">
            Multi-Tenant
            <br />
            <span className="login-hero-accent">Resource Fairness</span>
          </h1>
          <p className="login-hero-desc">
            Protect your shared cloud infrastructure from noisy neighbors with adaptive 
            fair scheduling, explainable resource attribution, and real-time incident response.
          </p>
        </div>

        <div className="login-features">
          {[
            { icon: Zap, label: 'Round-Robin Fair Scheduler', desc: 'Guaranteed turn allocation across tenants' },
            { icon: Shield, label: 'Noisy-Neighbor Detection', desc: 'Automatic contention identification' },
            { icon: Lock, label: 'Fairness Contracts', desc: 'SLA-backed resource guarantees' },
          ].map(({ icon: Icon, label, desc }) => (
            <div key={label} className="login-feature">
              <div className="login-feature-icon">
                <Icon size={16} />
              </div>
              <div>
                <div className="login-feature-label">{label}</div>
                <div className="login-feature-desc">{desc}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Live activity indicator */}
        <div className="login-live">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className={`login-live-bar ${i <= activeParticle ? 'active' : ''}`}
              style={{ height: `${8 + i * 6}px` }}
            />
          ))}
          <span>Live system active · {credentials.length > 0 ? 'Backend Connected' : 'Connecting…'}</span>
        </div>
      </div>

      {/* Right panel — login form */}
      <div className="login-right">
        <div className="login-card">
          <div className="login-card-header">
            <h2>Sign in to FairGuard</h2>
            <p>Use your company slug + API key, or log in as Platform Admin.</p>
          </div>

          {error && (
            <div className="login-error">
              <AlertTriangle size={15} />
              <span>{error}</span>
            </div>
          )}

          {user && (
            <div style={{
              background: '#eff6ff',
              border: '1px solid #bfdbfe',
              borderRadius: 8,
              padding: '12px 14px',
              marginBottom: 16,
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}>
              <div style={{ fontSize: 12, color: '#1e40af' }}>
                Currently logged in as <strong>{user.displayName}</strong> ({user.role === 'admin' ? 'Platform Administrator' : 'Tenant'}).
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  onClick={() => router.push(user.role === 'admin' ? '/admin' : '/tenant')}
                  style={{
                    flex: 1,
                    background: '#2563eb',
                    color: '#fff',
                    border: 'none',
                    borderRadius: 6,
                    padding: '6px 10px',
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  Return to Dashboard
                </button>
                <button
                  type="button"
                  onClick={logout}
                  style={{
                    background: '#fff',
                    color: '#dc2626',
                    border: '1px solid #fecaca',
                    borderRadius: 6,
                    padding: '6px 10px',
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  Sign Out
                </button>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="login-form">
            <div className="login-field">
              <label htmlFor="fg-username">Username</label>
              <input
                id="fg-username"
                type="text"
                placeholder="admin  or  northstar  or  meridian"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
              />
            </div>

            <div className="login-field">
              <label htmlFor="fg-password">Password / API Key</label>
              <div className="login-password-wrap">
                <input
                  id="fg-password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="fg_admin_platform_demo_key"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="login-eye"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="login-submit"
              disabled={loading}
              id="login-submit-btn"
            >
              {loading ? (
                <span className="login-spinner" />
              ) : (
                <>
                  Sign In <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>

          {/* Quick-fill demo credentials */}
          {credentials.length > 0 && (
            <div className="login-demos">
              <div className="login-demos-label">
                <span>Demo accounts</span>
                <span className="login-demos-hint">Click to fill</span>
              </div>
              {credentials.map((cred) => (
                <button
                  key={cred.username}
                  className={`login-demo-card ${cred.role}`}
                  onClick={() => quickLogin(cred)}
                  type="button"
                  id={`demo-${cred.username}`}
                >
                  <div className="login-demo-badge">{cred.role}</div>
                  <div>
                    <div className="login-demo-company">{cred.company}</div>
                    <div className="login-demo-creds">
                      <code>{cred.username}</code>
                    </div>
                  </div>
                  <CheckCircle2 size={14} className="login-demo-check" />
                </button>
              ))}
            </div>
          )}

          <div className="login-note">
            <Lock size={12} />
            JWT tokens · 8-hour session · Demo environment
          </div>
        </div>
      </div>

      <style>{`
        .login-root {
          min-height: 100vh;
          display: flex;
          position: relative;
          overflow: hidden;
          font-family: 'Inter', system-ui, sans-serif;
        }

        /* ── Background ── */
        .login-bg {
          position: fixed;
          inset: 0;
          background: linear-gradient(135deg, #0a0720 0%, #14102f 40%, #1a1040 100%);
          z-index: 0;
        }
        .login-bg-blob {
          position: absolute;
          border-radius: 50%;
          filter: blur(80px);
          opacity: 0.35;
        }
        .blob-1 {
          width: 600px; height: 600px;
          background: #6366f1;
          top: -200px; left: -100px;
          animation: blobFloat 8s ease-in-out infinite alternate;
        }
        .blob-2 {
          width: 500px; height: 500px;
          background: #8b5cf6;
          bottom: -150px; right: 300px;
          animation: blobFloat 10s ease-in-out infinite alternate-reverse;
        }
        .blob-3 {
          width: 350px; height: 350px;
          background: #06b6d4;
          top: 40%; right: -100px;
          animation: blobFloat 12s ease-in-out infinite alternate;
        }
        @keyframes blobFloat {
          from { transform: translate(0, 0) scale(1); }
          to { transform: translate(30px, 20px) scale(1.08); }
        }
        .login-grid {
          position: absolute;
          inset: 0;
          background-image:
            linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
          background-size: 40px 40px;
        }

        /* ── Layout ── */
        .login-left {
          position: relative;
          z-index: 1;
          flex: 1;
          padding: 56px 64px;
          display: flex;
          flex-direction: column;
          gap: 40px;
          color: #fff;
        }
        .login-right {
          position: relative;
          z-index: 1;
          width: 440px;
          min-width: 380px;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 40px 32px;
          background: rgba(255,255,255,0.04);
          backdrop-filter: blur(24px);
          border-left: 1px solid rgba(255,255,255,0.08);
        }

        /* ── Left panel ── */
        .login-brand {
          display: flex;
          align-items: center;
          gap: 14px;
        }
        .login-logo {
          width: 52px; height: 52px;
          background: linear-gradient(135deg, #6366f1, #8b5cf6);
          border-radius: 14px;
          display: flex; align-items: center; justify-content: center;
          box-shadow: 0 8px 32px rgba(99,102,241,0.4);
        }
        .login-product-name {
          font-size: 20px;
          font-weight: 700;
          letter-spacing: -0.3px;
        }
        .login-product-sub {
          font-size: 12px;
          opacity: 0.5;
          letter-spacing: 0.5px;
        }

        .login-hero-title {
          font-family: 'DM Serif Display', serif;
          font-size: 52px;
          line-height: 1.1;
          margin: 0;
          font-weight: 400;
        }
        .login-hero-accent {
          background: linear-gradient(90deg, #818cf8, #c084fc);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
        .login-hero-desc {
          font-size: 15px;
          line-height: 1.7;
          opacity: 0.65;
          max-width: 460px;
          margin: 0;
        }

        .login-features {
          display: flex;
          flex-direction: column;
          gap: 18px;
        }
        .login-feature {
          display: flex;
          align-items: flex-start;
          gap: 14px;
        }
        .login-feature-icon {
          width: 34px; height: 34px;
          background: rgba(99,102,241,0.15);
          border: 1px solid rgba(99,102,241,0.3);
          border-radius: 8px;
          display: flex; align-items: center; justify-content: center;
          flex-shrink: 0;
          color: #818cf8;
        }
        .login-feature-label {
          font-size: 13px;
          font-weight: 600;
          margin-bottom: 2px;
        }
        .login-feature-desc {
          font-size: 12px;
          opacity: 0.5;
        }

        .login-live {
          display: flex;
          align-items: flex-end;
          gap: 4px;
          font-size: 11px;
          opacity: 0.5;
        }
        .login-live-bar {
          width: 4px;
          background: rgba(255,255,255,0.3);
          border-radius: 2px;
          transition: background 0.3s;
        }
        .login-live-bar.active {
          background: #34d399;
        }
        .login-live span {
          margin-left: 8px;
        }

        /* ── Login card ── */
        .login-card {
          width: 100%;
          max-width: 380px;
          display: flex;
          flex-direction: column;
          gap: 20px;
        }
        .login-card-header h2 {
          font-family: 'DM Serif Display', serif;
          font-size: 26px;
          font-weight: 400;
          color: #fff;
          margin: 0 0 6px;
        }
        .login-card-header p {
          font-size: 13px;
          color: rgba(255,255,255,0.45);
          margin: 0;
          line-height: 1.5;
        }

        .login-error {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 14px;
          background: rgba(239,68,68,0.12);
          border: 1px solid rgba(239,68,68,0.25);
          border-radius: 8px;
          color: #fca5a5;
          font-size: 13px;
        }

        .login-form {
          display: flex;
          flex-direction: column;
          gap: 14px;
        }
        .login-field {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .login-field label {
          font-size: 12px;
          font-weight: 500;
          color: rgba(255,255,255,0.55);
          letter-spacing: 0.3px;
        }
        .login-field input,
        .login-password-wrap input {
          width: 100%;
          padding: 11px 14px;
          background: rgba(255,255,255,0.06);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 10px;
          color: #fff;
          font-size: 14px;
          font-family: inherit;
          outline: none;
          transition: border-color 0.2s, background 0.2s;
          box-sizing: border-box;
        }
        .login-field input::placeholder,
        .login-password-wrap input::placeholder {
          color: rgba(255,255,255,0.2);
          font-size: 13px;
        }
        .login-field input:focus,
        .login-password-wrap input:focus {
          border-color: #6366f1;
          background: rgba(99,102,241,0.08);
        }
        .login-password-wrap {
          position: relative;
        }
        .login-password-wrap input {
          padding-right: 44px;
        }
        .login-eye {
          position: absolute;
          right: 12px;
          top: 50%;
          transform: translateY(-50%);
          background: none;
          border: none;
          color: rgba(255,255,255,0.4);
          cursor: pointer;
          padding: 4px;
          display: flex; align-items: center;
        }
        .login-eye:hover { color: #fff; }

        .login-submit {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 13px 20px;
          background: linear-gradient(135deg, #6366f1, #8b5cf6);
          border: none;
          border-radius: 10px;
          color: #fff;
          font-size: 14px;
          font-weight: 600;
          font-family: inherit;
          cursor: pointer;
          transition: all 0.2s;
          margin-top: 4px;
          box-shadow: 0 4px 24px rgba(99,102,241,0.35);
        }
        .login-submit:hover:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 8px 32px rgba(99,102,241,0.5);
        }
        .login-submit:disabled {
          opacity: 0.7;
          cursor: not-allowed;
        }
        .login-spinner {
          width: 18px; height: 18px;
          border: 2px solid rgba(255,255,255,0.3);
          border-top-color: #fff;
          border-radius: 50%;
          animation: spin 0.7s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* ── Demo credentials ── */
        .login-demos {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .login-demos-label {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 11px;
          font-weight: 600;
          color: rgba(255,255,255,0.35);
          text-transform: uppercase;
          letter-spacing: 0.7px;
        }
        .login-demos-hint {
          font-weight: 400;
          text-transform: none;
          letter-spacing: 0;
        }
        .login-demo-card {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 12px;
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 8px;
          cursor: pointer;
          text-align: left;
          transition: all 0.2s;
          font-family: inherit;
          color: #fff;
          width: 100%;
        }
        .login-demo-card:hover {
          background: rgba(99,102,241,0.1);
          border-color: rgba(99,102,241,0.3);
        }
        .login-demo-badge {
          font-size: 10px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          padding: 2px 7px;
          border-radius: 4px;
          flex-shrink: 0;
        }
        .login-demo-card.admin .login-demo-badge {
          background: rgba(239,68,68,0.15);
          color: #fca5a5;
          border: 1px solid rgba(239,68,68,0.2);
        }
        .login-demo-card.tenant .login-demo-badge {
          background: rgba(99,102,241,0.15);
          color: #a5b4fc;
          border: 1px solid rgba(99,102,241,0.2);
        }
        .login-demo-company {
          font-size: 13px;
          font-weight: 500;
          margin-bottom: 2px;
        }
        .login-demo-creds {
          font-size: 11px;
          opacity: 0.45;
        }
        .login-demo-creds code {
          font-family: 'SF Mono', 'Fira Code', monospace;
        }
        .login-demo-check {
          margin-left: auto;
          flex-shrink: 0;
          color: rgba(255,255,255,0.2);
        }
        .login-demo-card:hover .login-demo-check {
          color: #818cf8;
        }

        .login-note {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 11px;
          color: rgba(255,255,255,0.25);
          text-align: center;
          justify-content: center;
        }

        /* ── Responsive ── */
        @media (max-width: 768px) {
          .login-root { flex-direction: column; }
          .login-left { padding: 32px 24px; gap: 24px; }
          .login-right { width: 100%; min-width: 0; border-left: none; border-top: 1px solid rgba(255,255,255,0.08); }
          .login-hero-title { font-size: 36px; }
        }
      `}</style>
    </div>
  )
}
