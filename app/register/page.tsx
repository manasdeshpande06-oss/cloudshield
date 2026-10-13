'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Lock,
  Server,
  Shield,
  Sparkles,
  Zap,
} from 'lucide-react'
import { fetchApi } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'

export default function RegisterPage() {
  const router = useRouter()
  const { user } = useAuth()
  const [companyName, setCompanyName] = useState('')
  const [companySlug, setCompanySlug] = useState('')
  const [initialTenantName, setInitialTenantName] = useState('')
  const [workloadType, setWorkloadType] = useState('API / light')
  const [contactEmail, setContactEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  // Auto-generate slug from company name
  const handleCompanyNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setCompanyName(val)
    if (!companySlug || companySlug === companyName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')) {
      setCompanySlug(val.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''))
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!companyName.trim()) {
      setError('Please enter a company name.')
      return
    }

    setLoading(true)
    setError('')
    try {
      const res = await fetchApi<{
        access_token: string
        role: string
        company_id: string
        company_name: string
        company_slug: string
        expires_in: number
      }>('/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          company_name: companyName,
          company_slug: companySlug || undefined,
          initial_tenant_name: initialTenantName || undefined,
          workload_type: workloadType,
          contact_email: contactEmail || undefined,
        }),
      })

      // Store auth
      const authUser = {
        role: res.role as 'tenant',
        displayName: res.company_name,
        companyId: res.company_id,
        companyName: res.company_name,
        companySlug: res.company_slug,
        token: res.access_token,
        expiresIn: res.expires_in,
      }
      localStorage.setItem('fg_auth', JSON.stringify(authUser))
      setSuccess(true)
      setTimeout(() => {
        router.push('/tenant')
      }, 1000)
    } catch (err: any) {
      setError(err?.message?.replace(/^API Error \d+: /, '') || 'Registration failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="register-root">
      {/* Background */}
      <div className="register-bg">
        <div className="register-blob blob-1" />
        <div className="register-blob blob-2" />
        <div className="register-grid" />
      </div>

      <div className="register-container">
        {/* Left column — Platform value */}
        <div className="register-left">
          <div className="register-brand">
            <div className="register-logo">
              <Shield size={28} />
            </div>
            <div>
              <div className="register-brand-title">CloudShield</div>
              <div className="register-brand-sub">FairGuard Platform</div>
            </div>
          </div>

          <div className="register-hero">
            <h1 className="register-hero-title">
              Onboard Your Tenant to
              <br />
              <span className="register-accent">Guaranteed Fairness</span>
            </h1>
            <p className="register-hero-desc">
              Join the multi-tenant resource protection mesh. Receive SLA guarantees,
              transparent shared resource visibility, and active defense against noisy neighbors.
            </p>
          </div>

          <div className="register-guarantees">
            {[
              { icon: Zap, title: 'Dedicated Resource Contract', desc: 'Guaranteed minimum requests per minute with burst headroom' },
              { icon: Server, title: 'Independent Queue Isolation', desc: 'Batch workloads will never block your interactive API calls' },
              { icon: Shield, title: 'Evidence-Based Protection', desc: 'Automatic contention throttling when neighbors spike' },
            ].map(({ icon: Icon, title, desc }) => (
              <div key={title} className="register-guarantee">
                <div className="register-guarantee-icon">
                  <Icon size={16} />
                </div>
                <div>
                  <div className="register-guarantee-title">{title}</div>
                  <div className="register-guarantee-desc">{desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right column — Form */}
        <div className="register-right">
          <div className="register-card">
            <div className="register-card-header">
              <h2>Tenant Self-Registration</h2>
              <p>Register your company and launch your primary tenant account.</p>
            </div>

            {error && (
              <div className="register-error">
                <AlertTriangle size={15} />
                <span>{error}</span>
              </div>
            )}

            {success && (
              <div className="register-success">
                <CheckCircle2 size={16} />
                <span>Account provisioned! Redirecting to tenant dashboard…</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="register-form">
              <div className="register-field">
                <label htmlFor="company-name">Company Name *</label>
                <input
                  id="company-name"
                  type="text"
                  placeholder="e.g. Acme Cloud Corp"
                  value={companyName}
                  onChange={handleCompanyNameChange}
                  required
                  autoFocus
                />
              </div>

              <div className="register-field">
                <label htmlFor="company-slug">Company Slug (Identifier)</label>
                <input
                  id="company-slug"
                  type="text"
                  placeholder="e.g. acme-cloud"
                  value={companySlug}
                  onChange={(e) => setCompanySlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                />
              </div>

              <div className="register-field">
                <label htmlFor="tenant-name">Initial Tenant Name</label>
                <input
                  id="tenant-name"
                  type="text"
                  placeholder="e.g. Acme API Gateway"
                  value={initialTenantName}
                  onChange={(e) => setInitialTenantName(e.target.value)}
                />
              </div>

              <div className="register-field">
                <label htmlFor="workload-type">Workload Type</label>
                <select
                  id="workload-type"
                  value={workloadType}
                  onChange={(e) => setWorkloadType(e.target.value)}
                >
                  <option value="API / light">API / light (interactive, low latency)</option>
                  <option value="CPU-intensive">CPU-intensive (compute, data processing)</option>
                  <option value="Batch jobs">Batch jobs (ETL, asynchronous)</option>
                  <option value="Mixed workload">Mixed workload (API + background)</option>
                </select>
              </div>

              <div className="register-field">
                <label htmlFor="contact-email">Contact Email</label>
                <input
                  id="contact-email"
                  type="email"
                  placeholder="admin@acmecloud.com"
                  value={contactEmail}
                  onChange={(e) => setContactEmail(e.target.value)}
                />
              </div>

              <button
                type="submit"
                className="register-submit-btn"
                disabled={loading || success}
              >
                {loading ? (
                  <span className="register-spinner" />
                ) : (
                  <>
                    Provision Tenant Account <ArrowRight size={16} />
                  </>
                )}
              </button>
            </form>

            <div className="register-footer-links">
              <span>Already have an account or demo key?</span>
              <Link href="/login" className="register-login-link">
                Sign in to FairGuard
              </Link>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .register-root {
          min-height: 100vh;
          display: flex;
          position: relative;
          overflow: hidden;
          font-family: 'Inter', system-ui, sans-serif;
          color: #fff;
        }
        .register-bg {
          position: fixed;
          inset: 0;
          background: linear-gradient(135deg, #09071c 0%, #110e2b 40%, #171038 100%);
          z-index: 0;
        }
        .register-blob {
          position: absolute;
          border-radius: 50%;
          filter: blur(90px);
          opacity: 0.35;
        }
        .blob-1 {
          width: 550px; height: 550px;
          background: #6366f1;
          top: -150px; left: -100px;
        }
        .blob-2 {
          width: 450px; height: 450px;
          background: #8b5cf6;
          bottom: -100px; right: 200px;
        }
        .register-grid {
          position: absolute;
          inset: 0;
          background-image:
            linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
          background-size: 40px 40px;
        }
        .register-container {
          position: relative;
          z-index: 1;
          display: flex;
          width: 100%;
          max-width: 1200px;
          margin: 0 auto;
          min-height: 100vh;
        }
        .register-left {
          flex: 1;
          padding: 60px 48px;
          display: flex;
          flex-direction: column;
          gap: 40px;
          justify-content: center;
        }
        .register-brand {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .register-logo {
          width: 46px; height: 46px;
          background: linear-gradient(135deg, #6366f1, #8b5cf6);
          border-radius: 12px;
          display: grid; place-items: center;
          box-shadow: 0 8px 24px rgba(99,102,241,0.4);
        }
        .register-brand-title {
          font-size: 19px;
          font-weight: 700;
        }
        .register-brand-sub {
          font-size: 11px;
          opacity: 0.5;
        }
        .register-hero-title {
          font-family: 'DM Serif Display', Georgia, serif;
          font-size: 44px;
          line-height: 1.15;
          margin: 0 0 16px;
          font-weight: 400;
        }
        .register-accent {
          background: linear-gradient(90deg, #818cf8, #c084fc);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
        .register-hero-desc {
          font-size: 14px;
          line-height: 1.7;
          opacity: 0.65;
          max-width: 440px;
          margin: 0;
        }
        .register-guarantees {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .register-guarantee {
          display: flex;
          align-items: flex-start;
          gap: 12px;
        }
        .register-guarantee-icon {
          width: 32px; height: 32px;
          background: rgba(99,102,241,0.15);
          border: 1px solid rgba(99,102,241,0.3);
          border-radius: 8px;
          display: grid; place-items: center;
          color: #818cf8;
          flex-shrink: 0;
        }
        .register-guarantee-title {
          font-size: 13px;
          font-weight: 600;
        }
        .register-guarantee-desc {
          font-size: 11px;
          opacity: 0.5;
          margin-top: 2px;
        }
        .register-right {
          width: 480px;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 40px 32px;
          background: rgba(255,255,255,0.03);
          backdrop-filter: blur(20px);
          border-left: 1px solid rgba(255,255,255,0.08);
        }
        .register-card {
          width: 100%;
          max-width: 390px;
          display: flex;
          flex-direction: column;
          gap: 18px;
        }
        .register-card-header h2 {
          font-family: 'DM Serif Display', Georgia, serif;
          font-size: 24px;
          font-weight: 400;
          margin: 0 0 6px;
        }
        .register-card-header p {
          font-size: 13px;
          color: rgba(255,255,255,0.45);
          margin: 0;
        }
        .register-error {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 12px;
          background: rgba(239,68,68,0.12);
          border: 1px solid rgba(239,68,68,0.3);
          border-radius: 8px;
          color: #fca5a5;
          font-size: 12px;
        }
        .register-success {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 12px;
          background: rgba(16,185,129,0.12);
          border: 1px solid rgba(16,185,129,0.3);
          border-radius: 8px;
          color: #6ee7b7;
          font-size: 12px;
        }
        .register-form {
          display: flex;
          flex-direction: column;
          gap: 13px;
        }
        .register-field {
          display: flex;
          flex-direction: column;
          gap: 5px;
        }
        .register-field label {
          font-size: 11px;
          font-weight: 500;
          color: rgba(255,255,255,0.6);
        }
        .register-field input,
        .register-field select {
          padding: 10px 12px;
          background: rgba(255,255,255,0.06);
          border: 1px solid rgba(255,255,255,0.12);
          border-radius: 8px;
          color: #fff;
          font-size: 13px;
          outline: none;
        }
        .register-field select option {
          background: #110e2b;
          color: #fff;
        }
        .register-field input:focus,
        .register-field select:focus {
          border-color: #6366f1;
          background: rgba(99,102,241,0.08);
        }
        .register-submit-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 12px 18px;
          background: linear-gradient(135deg, #6366f1, #8b5cf6);
          border: none;
          border-radius: 9px;
          color: #fff;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          margin-top: 6px;
        }
        .register-submit-btn:hover:not(:disabled) {
          box-shadow: 0 6px 24px rgba(99,102,241,0.5);
        }
        .register-submit-btn:disabled {
          opacity: 0.7;
          cursor: not-allowed;
        }
        .register-spinner {
          width: 16px; height: 16px;
          border: 2px solid rgba(255,255,255,0.3);
          border-top-color: #fff;
          border-radius: 50%;
          animation: spin 0.7s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .register-footer-links {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          font-size: 12px;
          color: rgba(255,255,255,0.4);
          margin-top: 4px;
        }
        .register-login-link {
          color: #818cf8;
          text-decoration: none;
          font-weight: 500;
        }
        .register-login-link:hover { text-decoration: underline; }
        @media (max-width: 850px) {
          .register-container { flex-direction: column; }
          .register-left { padding: 36px 24px; }
          .register-right { width: 100%; border-left: none; border-top: 1px solid rgba(255,255,255,0.08); }
          .register-hero-title { font-size: 32px; }
        }
      `}</style>
    </div>
  )
}
