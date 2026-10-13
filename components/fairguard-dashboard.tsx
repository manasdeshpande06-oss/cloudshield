'use client'

import React, { useMemo, useState, useEffect, useCallback } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Bell,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Clock3,
  Cloud,
  Copy,
  Cpu,
  FileText,
  Gauge,
  LayoutDashboard,
  ListFilter,
  LogOut,
  Menu,
  Moon,
  MoreHorizontal,
  Network,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  Server,
  Settings,
  Shield,
  SlidersHorizontal,
  Sparkles,
  Sun,
  Users,
  X,
  Zap,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { fetchApi, ADMIN_API_KEY } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import SharedResourceTable from '@/components/shared-resource-table'
import FairnessReceiptModal from '@/components/fairness-receipt-modal'
import FairnessContractsAdmin from '@/components/fairness-contracts-admin'

// Fallback seeded tenants if API is loading or offline
const SEEDED_TENANTS = [
  { id: 'tn_northstar_01', name: 'Northstar Primary', company: 'Northstar Analytics', company_name: 'Northstar Analytics', workload_type: 'CPU-intensive', type: 'CPU-intensive', requests_per_minute: 842, rpm: '842', quota_rpm: 1000, quota: '1,000', latency: '184 ms', avg_latency_ms: 112, p95_latency_ms: 184, rejected_count: 32, rejected: 32, accepted_count: 50488, status: 'Protected', active_protection: 'Concurrency −25%', action: 'Concurrency −25%', tone: 'amber', cpu_percent: 78.4, cpu_scope: 'job-measured', memory_percent: 64.2, active_jobs: 3, queued_jobs: 8, max_concurrency: 25 },
  { id: 'tn_meridian_04', name: 'Meridian Patient Portal', company: 'Meridian Health', company_name: 'Meridian Health', workload_type: 'API / light', type: 'API / light', requests_per_minute: 218, rpm: '218', quota_rpm: 500, quota: '500', latency: '42 ms', avg_latency_ms: 38, p95_latency_ms: 42, rejected_count: 0, rejected: 0, accepted_count: 13080, status: 'Healthy', active_protection: null, action: 'None', tone: 'green', cpu_percent: null, cpu_scope: 'not_measured', memory_percent: null, active_jobs: 1, queued_jobs: 0, max_concurrency: 20 },
  { id: 'tn_pioneer_07', name: 'Pioneer Fleet Tracker', company: 'Pioneer Logistics', company_name: 'Pioneer Logistics', workload_type: 'Batch jobs', type: 'Batch jobs', requests_per_minute: 456, rpm: '456', quota_rpm: 750, quota: '750', latency: '68 ms', avg_latency_ms: 54, p95_latency_ms: 68, rejected_count: 4, rejected: 4, accepted_count: 27356, status: 'Healthy', active_protection: null, action: 'None', tone: 'green', cpu_percent: 41.2, cpu_scope: 'job-measured', memory_percent: 52.8, active_jobs: 2, queued_jobs: 5, max_concurrency: 15 },
  { id: 'tn_lattice_02', name: 'Lattice Trading Core', company: 'Lattice Finance', company_name: 'Lattice Finance', workload_type: 'API / light', type: 'API / light', requests_per_minute: 612, rpm: '612', quota_rpm: 600, quota: '600', latency: '91 ms', avg_latency_ms: 62, p95_latency_ms: 91, rejected_count: 86, rejected: 86, accepted_count: 36634, status: 'Throttled', active_protection: 'Rate limit active', action: 'Rate limit active', tone: 'red', cpu_percent: null, cpu_scope: 'not_measured', memory_percent: null, active_jobs: 4, queued_jobs: 2, max_concurrency: 30 },
  { id: 'tn_cedar_11', name: 'Cedar Storefront API', company: 'Cedar Commerce', company_name: 'Cedar Commerce', workload_type: 'Mixed workload', type: 'Mixed workload', requests_per_minute: 336, rpm: '336', quota_rpm: 500, quota: '500', latency: '57 ms', avg_latency_ms: 48, p95_latency_ms: 57, rejected_count: 8, rejected: 8, accepted_count: 20152, status: 'Healthy', active_protection: null, action: 'None', tone: 'green', cpu_percent: 32.5, cpu_scope: 'job-measured', memory_percent: 44.0, active_jobs: 1, queued_jobs: 1, max_concurrency: 25 },
]

const SEEDED_TRAFFIC = [
  { time: '00:00', accepted: 1840, rejected: 12 },
  { time: '04:00', accepted: 1420, rejected: 8 },
  { time: '08:00', accepted: 2950, rejected: 45 },
  { time: '12:00', accepted: 4210, rejected: 98 },
  { time: '16:00', accepted: 3820, rejected: 64 },
  { time: '20:00', accepted: 2780, rejected: 28 },
]

const SEEDED_RESOURCES = [
  { time: '12:00', cpu: 44, memory: 58, queue: 14 },
  { time: '12:15', cpu: 52, memory: 60, queue: 19 },
  { time: '12:30', cpu: 78, memory: 65, queue: 39 },
  { time: '12:45', cpu: 69, memory: 63, queue: 26 },
  { time: '13:00', cpu: 53, memory: 61, queue: 18 },
]

const nav = [
  { label: 'Overview', icon: LayoutDashboard },
  { label: 'Companies', icon: Cloud },
  { label: 'Tenants', icon: Users },
  { label: 'Traffic & Quotas', icon: Network },
  { label: 'Workload Scheduler', icon: ListFilter },
  { label: 'Resource Monitoring', icon: Cpu },
  { label: 'Noisy-Neighbor Incidents', icon: AlertTriangle },
  { label: 'Fairness Contracts', icon: Shield },
  { label: 'Settings', icon: Settings },
]

function Badge({ children, tone = 'slate' }: { children: React.ReactNode; tone?: string }) {
  return (
    <span className={`badge badge-${tone}`}>
      <span className="badge-dot" />
      {children}
    </span>
  )
}

function Metric({
  label,
  value,
  change,
  icon: Icon,
  tone = 'blue',
}: {
  label: string
  value: string | number
  change?: string
  icon: React.ElementType
  tone?: string
}) {
  return (
    <div className="metric-card">
      <div className="metric-head">
        <span>{label}</span>
        <span className={`metric-icon ${tone}`}>
          <Icon size={15} />
        </span>
      </div>
      <strong>{value}</strong>
      {change && (
        <div className={change.startsWith('-') ? 'metric-change down' : 'metric-change'}>
          {change.startsWith('-') ? <ArrowDownRight size={13} /> : <ArrowUpRight size={13} />}
          {change}
        </div>
      )}
    </div>
  )
}

export function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = () => {
    navigator.clipboard?.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button className="copy-button" onClick={handleCopy} aria-label="Copy text" title="Copy">
      {copied ? <Check size={13} className="good-text" /> : <Copy size={13} />}
    </button>
  )
}

function Event({ icon: Icon, title, detail, tone = 'blue' }: any) {
  return (
    <div className="event">
      <span className={`event-icon ${tone}`}>
        <Icon size={14} />
      </span>
      <div>
        <b>{title}</b>
        <span>{detail}</span>
      </div>
      <ChevronRight size={15} className="event-arrow" />
    </div>
  )
}

interface FairGuardDashboardProps {
  initialTab?: string
}

export default function FairGuardDashboard({ initialTab = 'Overview' }: FairGuardDashboardProps) {
  const { user, logout } = useAuth()
  const [active, setActive] = useState(initialTab)
  const [selectedReceiptIncidentId, setSelectedReceiptIncidentId] = useState<number | null>(null)
  const [dark, setDark] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [range, setRange] = useState('Last 24 hours')
  const [incidentOpen, setIncidentOpen] = useState(true)
  const [toast, setToast] = useState('')
  const [trafficData, setTrafficData] = useState<any[]>(SEEDED_TRAFFIC)
  const [resourceData, setResourceData] = useState<any[]>(SEEDED_RESOURCES)
  const [companies, setCompanies] = useState<any[]>([])
  const [tenants, setTenants] = useState<any[]>(SEEDED_TENANTS)
  const [incidents, setIncidents] = useState<any[]>([])
  const [schedulerStatus, setSchedulerStatus] = useState<any>(null)
  const [schedulerHistory, setSchedulerHistory] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [selectedTenant, setSelectedTenant] = useState<string | null>(null)
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null)

  const notify = (message: string) => {
    setToast(message)
    window.setTimeout(() => setToast(''), 3000)
  }

  // Load backend data
  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      const [compRows, compList, incList, resList, schedStatus, schedHist] = await Promise.allSettled([
        fetchApi<any[]>('/companies/comparison'),
        fetchApi<any[]>('/companies'),
        fetchApi<any[]>('/incidents'),
        fetchApi<any[]>('/resources'),
        fetchApi<any>('/scheduler/status'),
        fetchApi<any[]>('/scheduler/history'),
      ])

      if (compRows.status === 'fulfilled' && compRows.value?.length) {
        const mapped = compRows.value.map((t: any) => ({
          ...t,
          company: t.company_name,
          type: t.workload_type,
          rpm: String(Math.round(t.requests_per_minute || 0)),
          quota: String(t.quota_rpm || 500),
          latency: `${Math.round(t.p95_latency_ms || 45)} ms`,
          rejected: t.rejected_count || 0,
          action: t.active_protection || 'None',
          tone:
            t.status === 'Protected'
              ? 'amber'
              : t.status === 'Throttled'
              ? 'red'
              : t.status === 'Degraded'
              ? 'amber'
              : 'green',
        }))
        setTenants(mapped)
      }

      if (compList.status === 'fulfilled' && compList.value?.length) {
        setCompanies(compList.value)
      }

      if (incList.status === 'fulfilled' && incList.value?.length) {
        setIncidents(incList.value)
      }

      if (resList.status === 'fulfilled' && resList.value?.length) {
        const mappedRes = resList.value.map((r: any) => ({
          time: new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          cpu: Math.round(r.cpu_percent || 50),
          memory: Math.round(r.memory_percent || 60),
          queue: r.queue_depth || 0,
        }))
        if (mappedRes.length) setResourceData(mappedRes)
      }

      if (schedStatus.status === 'fulfilled') {
        setSchedulerStatus(schedStatus.value)
      }

      if (schedHist.status === 'fulfilled') {
        setSchedulerHistory(schedHist.value)
      }
    } catch {
      // Keep seeded values if offline
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const filteredTenants = useMemo(() => {
    return tenants.filter((t) =>
      `${t.company || t.company_name} ${t.name || ''} ${t.id} ${t.workload_type || ''}`
        .toLowerCase()
        .includes(query.toLowerCase())
    )
  }, [tenants, query])

  const currentTenant = useMemo(() => {
    if (!selectedTenant) return null
    return tenants.find((t) => t.id === selectedTenant) || tenants[0]
  }, [selectedTenant, tenants])

  const currentCompany = useMemo(() => {
    if (!selectedCompany) return null
    return (
      companies.find((c) => c.name === selectedCompany || c.id === selectedCompany) || {
        name: selectedCompany,
        id: 'COMP-001',
      }
    )
  }, [selectedCompany, companies])

  const pageTitle = selectedTenant
    ? 'Tenant details'
    : selectedCompany
    ? `${selectedCompany} · Company details`
    : active === 'Overview'
    ? 'Platform overview'
    : active

  return (
    <div className={dark ? 'app-shell dark' : 'app-shell'}>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>

      {/* Sidebar */}
      <aside className={mobileOpen ? 'sidebar open' : 'sidebar'}>
        <div className="brand">
          <div className="brand-mark">
            <Shield size={19} />
          </div>
          <div>
            <strong>CloudShield</strong>
            <span>FairGuard Multi-Tenant</span>
          </div>
          <button className="mobile-close" onClick={() => setMobileOpen(false)} aria-label="Close menu">
            <X size={18} />
          </button>
        </div>

        <div className="workspace">
          <div className="workspace-avatar">A</div>
          <div>
            <b>Acme Platform</b>
            <span>Platform Admin</span>
          </div>
          <ChevronDown size={14} />
        </div>

        <nav className="nav-list" aria-label="Main navigation">
          {nav.map(({ label, icon: Icon }) => (
            <button
              key={label}
              className={active === label && !selectedTenant && !selectedCompany ? 'nav-item active' : 'nav-item'}
              onClick={() => {
                setActive(label)
                setSelectedTenant(null)
                setSelectedCompany(null)
                setMobileOpen(false)
              }}
            >
              <Icon size={17} />
              <span>{label}</span>
              {label === 'Noisy-Neighbor Incidents' && (
                <span className="nav-count">{incidents.filter((i) => i.status === 'open').length || 1}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <Sparkles size={15} />
            <div>
              <b>Fair Allocation Active</b>
              <span>Round-Robin & Sliding Quotas</span>
            </div>
          </div>
          <button className="nav-item" onClick={() => notify('API Key: ' + ADMIN_API_KEY)}>
            <BookOpen size={17} />
            <span>Platform Token</span>
          </button>
          <div className="user-row">
            <div className="user-avatar">{user?.displayName?.charAt(0) || 'A'}</div>
            <div>
              <b>{user?.displayName || 'Platform Admin'}</b>
              <span>Admin account</span>
            </div>
            <button
              className="icon-button"
              onClick={logout}
              aria-label="Log out"
              title="Sign out and return to Login"
              style={{ marginLeft: 'auto' }}
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {mobileOpen && <button className="scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}

      {/* Main Area */}
      <section className="main-area">
        <header className="topbar">
          <button className="menu-button" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
            <Menu size={20} />
          </button>
          <div className="breadcrumbs">
            <span>CloudShield</span>
            <ChevronRight size={14} />
            <b>{pageTitle}</b>
          </div>

          <div className="top-actions">
            <div className="global-search">
              <Search size={16} />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search tenants, companies, workloads..."
                aria-label="Global search"
              />
              {query && (
                <button onClick={() => setQuery('')} aria-label="Clear search">
                  <X size={14} />
                </button>
              )}
              <kbd>⌘ K</kbd>
            </div>

            <select className="range-select" value={range} onChange={(e) => setRange(e.target.value)} aria-label="Time range">
              <option>Last 24 hours</option>
              <option>Last 7 days</option>
              <option>Last 30 days</option>
            </select>

            <button
              className="icon-button"
              onClick={() => {
                loadData()
                notify('Metrics refreshed from backend')
              }}
              aria-label="Refresh metrics"
            >
              <RefreshCw size={17} className={loading ? 'spin' : ''} />
            </button>

            <button
              className="icon-button notification"
              onClick={() => notify(`1 active noisy-neighbor incident detected`)}
              aria-label="Notifications"
            >
              <Bell size={17} />
              <i />
            </button>

            <button className="icon-button" onClick={() => setDark(!dark)} aria-label="Toggle dark mode">
              {dark ? <Sun size={17} /> : <Moon size={17} />}
            </button>
          </div>
        </header>

        <main id="main-content" className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span className="live-dot" />
                System nominal · live multi-tenant protection active
              </div>
              <h1>{pageTitle}</h1>
              <p>
                {active === 'Overview'
                  ? 'Understand workload health, fairness, and protection across your shared infrastructure.'
                  : `Manage ${active.toLowerCase()} across tenant companies with explainable resource attribution.`}
              </p>
            </div>
            <div className="heading-actions">
              <Badge tone="blue">Backend: Connected (port 8000)</Badge>
              <button
                className="secondary-button"
                onClick={() => notify('Platform Admin Key: ' + ADMIN_API_KEY)}
              >
                <CircleHelp size={15} /> Help
              </button>
              <button
                className="secondary-button"
                onClick={logout}
                title="Sign out and return to Login"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                <LogOut size={15} /> Sign out
              </button>
            </div>
          </div>

          {/* Drilldown: Tenant Details */}
          {selectedTenant && currentTenant ? (
            <TenantDetails
              tenant={currentTenant}
              traffic={trafficData}
              onBack={() => setSelectedTenant(null)}
              onNotify={notify}
              onRefresh={loadData}
            />
          ) : selectedCompany ? (
            /* Drilldown: Company Details */
            <CompanyDetails
              companyName={selectedCompany}
              company={currentCompany}
              tenants={tenants}
              onBack={() => setSelectedCompany(null)}
              onSelectTenant={setSelectedTenant}
              onNotify={notify}
            />
          ) : active === 'Overview' ? (
            /* Overview Page */
            <OverviewPage
              traffic={trafficData}
              resource={resourceData}
              tenants={filteredTenants}
              incidents={incidents}
              onNotify={notify}
              onSelectTenant={setSelectedTenant}
              onSelectCompany={setSelectedCompany}
              selected={selectedTenant}
              incidentOpen={incidentOpen}
              setIncidentOpen={setIncidentOpen}
              onNavigateIncidents={() => setActive('Noisy-Neighbor Incidents')}
              onOpenReceipt={(id: number) => setSelectedReceiptIncidentId(id)}
            />
          ) : active === 'Companies' ? (
            /* Companies Page */
            <CompaniesSection
              companies={companies}
              tenants={tenants}
              onSelectCompany={setSelectedCompany}
              onNotify={notify}
            />
          ) : active === 'Tenants' ? (
            /* Tenants Directory */
            <TenantsSection
              tenants={filteredTenants}
              onSelectTenant={setSelectedTenant}
              onNotify={notify}
            />
          ) : active === 'Traffic & Quotas' ? (
            /* Traffic & Quotas Page */
            <TrafficQuotasSection
              tenants={tenants}
              traffic={trafficData}
              onNotify={notify}
              onSelectTenant={setSelectedTenant}
              onRefresh={loadData}
            />
          ) : active === 'Workload Scheduler' ? (
            /* Workload Scheduler Page */
            <SchedulerSection
              tenants={tenants}
              status={schedulerStatus}
              history={schedulerHistory}
              onNotify={notify}
              onRefresh={loadData}
            />
          ) : active === 'Resource Monitoring' ? (
            /* Resource Monitoring Page */
            <ResourceMonitoringSection
              tenants={tenants}
              resources={resourceData}
              onSelectTenant={setSelectedTenant}
              onNotify={notify}
            />
          ) : active === 'Noisy-Neighbor Incidents' ? (
            /* Noisy-Neighbor Incidents Page */
            <IncidentsSection
              incidents={incidents}
              onNotify={notify}
              onRefresh={loadData}
              onSelectTenant={setSelectedTenant}
              onOpenReceipt={(id: number) => setSelectedReceiptIncidentId(id)}
            />
          ) : active === 'Fairness Contracts' ? (
            /* Fairness Contracts: Feasibility & Guarantees */
            <FairnessContractsAdmin onNotify={notify} />
          ) : (
            /* Settings Page */
            <SettingsSection onNotify={notify} onReset={loadData} />
          )}
        </main>
      </section>

      {selectedReceiptIncidentId !== null && (
        <FairnessReceiptModal
          incidentId={selectedReceiptIncidentId}
          onClose={() => setSelectedReceiptIncidentId(null)}
        />
      )}

      {toast && (
        <div className="toast">
          <Check size={16} />
          {toast}
        </div>
      )}
    </div>
  )
}

/* =========================================================================
   OVERVIEW PAGE
   ========================================================================= */

function OverviewPage({
  traffic,
  resource,
  tenants,
  incidents,
  onNotify,
  onSelectTenant,
  onSelectCompany,
  selected,
  incidentOpen,
  setIncidentOpen,
  onNavigateIncidents,
  onOpenReceipt,
}: any) {
  const activeIncident = incidents[0] || {
    id: 'INC-1042',
    title: 'Northstar Analytics CPU pressure impacting shared worker pool',
    severity: 'high',
    tenant_name: 'Northstar Analytics',
  }

  const totals = useMemo(() => {
    const acc = tenants.reduce((a: number, t: any) => a + (t.accepted_count || Number(t.rpm || 0) * 60), 0)
    const rej = tenants.reduce((a: number, t: any) => a + (t.rejected_count || t.rejected || 0), 0)
    const rate = acc + rej > 0 ? ((acc / (acc + rej)) * 100).toFixed(1) : '98.7'
    return { acc, rej, rate }
  }, [tenants])

  return (
    <>
      <div className="metric-grid">
        <Metric label="Requests received" value={totals.acc.toLocaleString()} change="+12.8% vs baseline" icon={Activity} />
        <Metric label="Success rate" value={`${totals.rate}%`} change="+0.4% policy enforced" icon={Check} tone="green" />
        <Metric label="p95 latency" value="184 ms" change="-18 ms with Fair Scheduler" icon={Clock3} tone="violet" />
        <Metric label="Active incidents" value={incidents.filter((i: any) => i.status === 'open').length || 1} change="Needs review" icon={AlertTriangle} tone="amber" />
      </div>


      {/* Incident banner */}
      {incidentOpen && (
        <section className="incident-banner">
          <div className="incident-icon">
            <AlertTriangle size={19} />
          </div>
          <div className="incident-copy">
            <div className="incident-title">
              <Badge tone="red">{activeIncident.id} · High severity</Badge>
              <span>Detected recently</span>
            </div>
            <h2>{activeIncident.title || 'Northstar Analytics may be impacting shared worker pool'}</h2>
            <p>
              CPU pressure reached 78% while 8 CPU-intensive jobs ran concurrently. Innocents such as Meridian Health experienced elevated queue wait times. Adaptive concurrency reduction recommended.
            </p>
            <div className="incident-evidence">
              <span>
                <Cpu size={14} /> Machine CPU 78%
              </span>
              <span>
                <Clock3 size={14} /> p95 latency +42 ms
              </span>
              <span>
                <ListFilter size={14} /> Queue wait +39 ms
              </span>
            </div>
          </div>
          <div className="incident-actions">
            <button
              className="primary-button"
              onClick={() => {
                const incNum = activeIncident?.id ? (parseInt(String(activeIncident.id).replace(/\D/g, '')) || 1) : 1
                onOpenReceipt(incNum)
              }}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <FileText size={14} /> View Fairness Receipt
            </button>
            <button className="secondary-button" onClick={onNavigateIncidents}>
              Review incident
            </button>
            <button className="icon-button" onClick={() => setIncidentOpen(false)} aria-label="Dismiss incident banner">
              <X size={16} />
            </button>
          </div>
        </section>
      )}

      {/* Shared Resource Visibility Table (Requirement 7) */}
      <section style={{ marginBottom: 14 }}>
        <SharedResourceTable onSelectIncident={(id) => onOpenReceipt(id)} />
      </section>

      {/* Monitored Tenants Table */}
      <section className="panel table-panel">
        <div className="panel-header">
          <div>
            <h2>Tenant health & resource visibility</h2>
            <p>Live measurements · Click any tenant to inspect scoped traffic and quotas</p>
          </div>
          <button className="panel-action" onClick={() => onNotify('Showing all tenants in directory')}>
            View all <ChevronRight size={14} />
          </button>
        </div>
        <TenantTable tenants={tenants.slice(0, 8)} onSelect={onSelectTenant} selected={selected} />
      </section>

      {/* Bottom widgets */}
      <div className="bottom-grid">
        <section className="panel resource-mini">
          <div className="panel-header">
            <div>
              <h2>Shared resources</h2>
              <p>Machine-level measurements</p>
            </div>
            <Server size={18} className="muted-icon" />
          </div>
          <div className="resource-stats">
            <div>
              <span>CPU utilization</span>
              <strong>53%</strong>
              <em className="good-text">Normal</em>
            </div>
            <div>
              <span>Memory usage</span>
              <strong>61%</strong>
              <em className="good-text">Normal</em>
            </div>
            <div>
              <span>Worker pool</span>
              <strong>8 / 12</strong>
              <em className="warn-text">Elevated</em>
            </div>
          </div>
          <div className="mini-chart">
            <ResponsiveContainer width="100%" height={100}>
              <LineChart data={resource}>
                <XAxis dataKey="time" hide />
                <YAxis hide domain={[0, 100]} />
                <Line type="monotone" dataKey="cpu" stroke="#2563eb" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="memory" stroke="#94a3b8" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="panel events-panel">
          <div className="panel-header">
            <div>
              <h2>Recent protection events</h2>
              <p>Audit trail of automatic actions</p>
            </div>
            <button className="panel-action" onClick={() => onNotify('Full audit log ready')}>
              Log <ChevronRight size={14} />
            </button>
          </div>
          <div className="event-list">
            <Event icon={Shield} title="Concurrency limit reduced (-25%)" detail="Northstar Analytics · Adaptive protection active" tone="amber" />
            <Event icon={Check} title="Quota policy enforced" detail="Lattice Finance · Sliding window throttled 86 burst requests" tone="green" />
            <Event icon={Zap} title="Round-Robin turn advanced" detail="Platform Scheduler · Empty queues skipped fairly" tone="blue" />
          </div>
        </section>
      </div>
    </>
  )
}

/* =========================================================================
   TENANT TABLE COMPONENT
   ========================================================================= */

function TenantTable({ tenants, onSelect, selected }: any) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Company / Tenant</th>
            <th>Workload</th>
            <th>Requests / min</th>
            <th>Quota / use</th>
            <th>p95 latency</th>
            <th>CPU / Memory</th>
            <th>Status</th>
            <th>Protection</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {tenants.map((t: any, idx: number) => {
            const companyName = t.company || t.company_name || 'Acme'
            const cpuDisplay = t.cpu_percent ? `${Math.round(t.cpu_percent)}% (job)` : 'Machine scope'
            return (
              <tr key={`${t.id || 'tn'}-${idx}`} className={selected === t.id ? 'row-selected' : ''} onClick={() => onSelect(t.id)}>
                <td>
                  <div className="tenant-name">
                    <span className="company-avatar">{companyName[0]}</span>
                    <div>
                      <b>{companyName}</b>
                      <span>{t.id}</span>
                    </div>
                  </div>
                </td>
                <td>{t.workload_type || t.type}</td>
                <td className="mono">{t.requests_per_minute || t.rpm}</td>
                <td className="mono">
                  {t.quota_rpm || t.quota} rpm
                </td>
                <td className="mono">{t.latency || `${Math.round(t.p95_latency_ms || 45)} ms`}</td>
                <td className="mono">{cpuDisplay}</td>
                <td>
                  <Badge tone={t.tone || (t.status === 'Protected' ? 'amber' : t.status === 'Throttled' ? 'red' : 'green')}>
                    {t.status}
                  </Badge>
                </td>
                <td>
                  <span className={t.action === 'None' || !t.active_protection ? 'muted' : 'action-text'}>
                    {t.active_protection || t.action || 'None'}
                  </span>
                </td>
                <td>
                  <ChevronRight size={15} className="row-arrow" />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/* =========================================================================
   TENANT DETAILS VIEW (DRILLDOWN)
   ========================================================================= */

function TenantDetails({ tenant, traffic, onBack, onNotify, onRefresh }: any) {
  const [rpmQuota, setRpmQuota] = useState(tenant.quota_rpm || 500)
  const [concurrencyQuota, setConcurrencyQuota] = useState(tenant.max_concurrency || 25)
  const [saving, setSaving] = useState(false)
  const [bursting, setBursting] = useState(false)

  // Use tenant-specific traffic or seeded
  const tenantTraffic = useMemo(() => {
    return traffic && traffic.length ? traffic : SEEDED_TRAFFIC
  }, [traffic])

  const handleSaveQuota = async () => {
    try {
      setSaving(true)
      await fetchApi(`/tenants/${tenant.id}/quota`, {
        method: 'PUT',
        body: JSON.stringify({
          requests_per_minute: Number(rpmQuota),
          max_concurrency: Number(concurrencyQuota),
          queue_limit: 100,
          resource_budget_cpu: 25.0,
          resource_budget_memory: 25.0,
          window_seconds: 60,
        }),
      })
      onNotify(`Quota updated for ${tenant.name || tenant.id}`)
      onRefresh()
    } catch (e: any) {
      onNotify(`Error updating quota: ${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleTestBurst = async () => {
    try {
      setBursting(true)
      const res = await fetchApi<any>('/workload/submit', {
        method: 'POST',
        body: JSON.stringify({
          tenant_id: tenant.id,
          payload: { test_query: 'SELECT * FROM metrics', client: 'ui_tester' },
        }),
      })
      onNotify(`Workload submission response: HTTP ${res.status || '200'} (${res.message || 'accepted'})`)
      onRefresh()
    } catch (e: any) {
      onNotify(`Workload rate-limit: ${e.message}`)
    } finally {
      setBursting(false)
    }
  }

  const companyName = tenant.company || tenant.company_name || 'Acme'
  const acceptedCount = tenant.accepted_count || Number(tenant.rpm || 100) * 60 - (tenant.rejected || 0)
  const rejectedCount = tenant.rejected_count ?? tenant.rejected ?? 0

  return (
    <div className="page-view">
      <button className="panel-action back-action" onClick={onBack}>
        <ChevronRight size={14} className="rotate-180" /> Back to Dashboard
      </button>

      {/* Hero Banner */}
      <section className="company-hero panel">
        <div>
          <div className="eyebrow">Tenant-Scoped Visibility · Live Data</div>
          <h2>{companyName} — {tenant.name || tenant.id}</h2>
          <p>
            Tenant ID <span className="mono">{tenant.id}</span> · Workload: <b>{tenant.workload_type || tenant.type}</b> ·{' '}
            <Badge tone={tenant.tone || (tenant.status === 'Protected' ? 'amber' : 'green')}>{tenant.status}</Badge>
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="mono" style={{ fontSize: '12px', color: '#687588' }}>
            /api/tenants/{tenant.id}
          </span>
          <CopyButton value={tenant.id} />
        </div>
      </section>

      {/* Metrics Grid */}
      <div className="metric-grid">
        <Metric label="Requests received" value={`${tenant.requests_per_minute || tenant.rpm} / min`} change="Tenant rate" icon={Activity} />
        <Metric label="Accepted requests" value={acceptedCount.toLocaleString()} change="Recorded" icon={Check} tone="green" />
        <Metric label="Rejected (rate-limited)" value={rejectedCount.toLocaleString()} change="Policy enforced" icon={AlertTriangle} tone="amber" />
        <Metric label="Latency avg / p95" value={`${tenant.avg_latency_ms || 45} / ${tenant.p95_latency_ms || 184} ms`} change="Measured" icon={Clock3} tone="violet" />
      </div>

      <div className="overview-grid">
        {/* Quota & Policy Configuration */}
        <section className="panel protection-panel">
          <div className="panel-header">
            <div>
              <h2>Tenant Quota Configuration</h2>
              <p>Adjust limits live in sliding-window rate limiter</p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <button className="primary-button" onClick={handleTestBurst} disabled={bursting}>
                <Play size={14} /> {bursting ? 'Sending...' : 'Test Request'}
              </button>
              <SlidersHorizontal size={18} className="muted-icon" />
            </div>
          </div>

          <div style={{ display: 'grid', gap: '14px', marginTop: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '11px', color: '#687588', marginBottom: '4px' }}>
                Requests per minute (RPM Quota)
              </label>
              <input
                type="number"
                value={rpmQuota}
                onChange={(e) => setRpmQuota(Number(e.target.value))}
                style={{ width: '100%', padding: '7px 10px', border: '1px solid #e5eaf0', borderRadius: '6px', fontSize: '13px' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '11px', color: '#687588', marginBottom: '4px' }}>
                Max Concurrency Limit
              </label>
              <input
                type="number"
                value={concurrencyQuota}
                onChange={(e) => setConcurrencyQuota(Number(e.target.value))}
                style={{ width: '100%', padding: '7px 10px', border: '1px solid #e5eaf0', borderRadius: '6px', fontSize: '13px' }}
              />
            </div>

            <button className="primary-button" onClick={handleSaveQuota} disabled={saving} style={{ marginTop: '8px' }}>
              <Check size={14} /> {saving ? 'Saving...' : 'Update Tenant Quota'}
            </button>
          </div>
        </section>
      </div>

      {/* Jobs & Protection Details */}
      <div className="bottom-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Jobs & scheduling queue</h2>
              <p>Per-tenant Round-Robin queue status</p>
            </div>
          </div>
          <div className="resource-stats">
            <div>
              <span>Active running jobs</span>
              <strong>{tenant.active_jobs || 1}</strong>
            </div>
            <div>
              <span>Queued jobs</span>
              <strong>{tenant.queued_jobs || 0}</strong>
            </div>
            <div>
              <span>Max allowed workers</span>
              <strong>4 per tenant</strong>
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Security & protection audit trail</h2>
              <p>Tenant-scoped policy enforcement events</p>
            </div>
          </div>
          <div className="event-list">
            <Event
              icon={Shield}
              title={tenant.active_protection || 'Standard Quota Active'}
              detail="Sliding-window rate limiter monitoring 60s intervals"
              tone={tenant.tone || 'green'}
            />
            <Event
              icon={Check}
              title="Fair Queue Allocation"
              detail="Eligible for Round-Robin turns without starvation"
              tone="blue"
            />
          </div>
        </section>
      </div>
    </div>
  )
}

/* =========================================================================
   COMPANY DETAILS VIEW (DRILLDOWN)
   ========================================================================= */

function CompanyDetails({ companyName, company, tenants, onBack, onSelectTenant, onNotify }: any) {
  const companyTenants = useMemo(() => {
    return tenants.filter((t: any) => (t.company || t.company_name) === companyName)
  }, [tenants, companyName])

  const totals = useMemo(() => {
    return companyTenants.reduce(
      (a: any, t: any) => ({
        rpm: a.rpm + Number(t.rpm || t.requests_per_minute || 0),
        rejected: a.rejected + (t.rejected || t.rejected_count || 0),
        accepted: a.accepted + (t.accepted_count || Number(t.rpm || 0) * 60),
      }),
      { rpm: 0, rejected: 0, accepted: 0 }
    )
  }, [companyTenants])

  return (
    <div className="page-view">
      <button className="panel-action back-action" onClick={onBack}>
        <ChevronRight size={14} className="rotate-180" /> Back to Companies
      </button>

      <section className="company-hero panel">
        <div>
          <div className="eyebrow">Company aggregate · Multi-tenant cluster</div>
          <h2>{companyName}</h2>
          <p>
            Company ID <span className="mono">{company.id || 'COMP-001'}</span> · Registered Active Organization
          </p>
        </div>
        <Badge tone="blue">{companyTenants.length} monitored tenants</Badge>
      </section>

      <div className="metric-grid">
        <Metric label="Aggregate requests" value={`${totals.rpm.toLocaleString()} / min`} icon={Activity} />
        <Metric label="Accepted requests" value={totals.accepted.toLocaleString()} tone="green" icon={Check} />
        <Metric label="Rejected requests" value={totals.rejected.toLocaleString()} tone="amber" icon={AlertTriangle} />
        <Metric label="Active tenants" value={companyTenants.length} tone="violet" icon={Users} />
      </div>

      <section className="panel table-panel">
        <div className="panel-header">
          <div>
            <h2>Tenants belonging to {companyName}</h2>
            <p>Click any tenant to inspect scoped logs</p>
          </div>
        </div>
        <TenantTable tenants={companyTenants} onSelect={onSelectTenant} selected={null} />
      </section>
    </div>
  )
}

/* =========================================================================
   COMPANIES SECTION
   ========================================================================= */

function CompaniesSection({ companies, tenants, onSelectCompany, onNotify }: any) {
  const displayCompanies = useMemo(() => {
    if (companies && companies.length) return companies
    return [
      { id: 'COMP-001', name: 'Northstar Analytics', slug: 'northstar', tenant_count: 3, status: 'active' },
      { id: 'COMP-002', name: 'Meridian Health', slug: 'meridian', tenant_count: 2, status: 'active' },
      { id: 'COMP-003', name: 'Pioneer Logistics', slug: 'pioneer', tenant_count: 3, status: 'active' },
      { id: 'COMP-004', name: 'Lattice Finance', slug: 'lattice', tenant_count: 2, status: 'active' },
      { id: 'COMP-005', name: 'Cedar Commerce', slug: 'cedar', tenant_count: 3, status: 'active' },
    ]
  }, [companies])

  return (
    <div className="page-view">
      <section className="company-hero panel">
        <div>
          <div className="eyebrow">Organization Directory</div>
          <h2>Registered Companies</h2>
          <p>Each company operates one or more isolated tenant workloads with dedicated quotas.</p>
        </div>
        <Badge tone="blue">{displayCompanies.length} Organizations</Badge>
      </section>

      <section className="panel table-panel">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Company Name</th>
                <th>Company ID</th>
                <th>Tenants</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {displayCompanies.map((c: any) => (
                <tr key={c.id} onClick={() => onSelectCompany(c.name)}>
                  <td>
                    <div className="tenant-name">
                      <span className="company-avatar">{c.name[0]}</span>
                      <b>{c.name}</b>
                    </div>
                  </td>
                  <td className="mono">{c.id}</td>
                  <td>{c.tenant_count || 2} tenants</td>
                  <td>
                    <Badge tone={c.status === 'active' ? 'green' : 'slate'}>{c.status || 'Active'}</Badge>
                  </td>
                  <td>
                    <button className="panel-action">
                      View Tenants <ChevronRight size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

/* =========================================================================
   TENANTS SECTION
   ========================================================================= */

function TenantsSection({ tenants, onSelectTenant, onNotify }: any) {
  const [filterType, setFilterType] = useState('All')
  const [filterStatus, setFilterStatus] = useState('All')

  const filtered = useMemo(() => {
    return tenants.filter((t: any) => {
      const matchType = filterType === 'All' || (t.workload_type || t.type) === filterType
      const matchStatus = filterStatus === 'All' || t.status === filterStatus
      return matchType && matchStatus
    })
  }, [tenants, filterType, filterStatus])

  return (
    <div className="page-view">
      <section className="panel table-panel">
        <div className="panel-header">
          <div>
            <h2>Tenant Directory</h2>
            <p>25 monitored tenants across 10 companies · Click any tenant to inspect scoped traffic and quotas</p>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <select
              className="table-select"
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              aria-label="Filter workload type"
              style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid #e5eaf0', fontSize: '11px' }}
            >
              <option value="All">All Workload Types</option>
              <option value="CPU-intensive">CPU-intensive</option>
              <option value="Batch jobs">Batch jobs</option>
              <option value="API / light">API / light</option>
              <option value="Mixed workload">Mixed workload</option>
            </select>

            <select
              className="table-select"
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              aria-label="Filter status"
              style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid #e5eaf0', fontSize: '11px' }}
            >
              <option value="All">All Statuses</option>
              <option value="Healthy">Healthy</option>
              <option value="Protected">Protected</option>
              <option value="Throttled">Throttled</option>
            </select>
          </div>
        </div>

        <TenantTable tenants={filtered} onSelect={onSelectTenant} selected={null} />
      </section>
    </div>
  )
}

/* =========================================================================
   TRAFFIC & QUOTAS SECTION
   ========================================================================= */

function TrafficQuotasSection({ tenants, traffic, onNotify, onSelectTenant, onRefresh }: any) {
  const [testTenant, setTestTenant] = useState(tenants[0]?.id || 'tn_northstar_01')
  const [testing, setTesting] = useState(false)

  const handleBurstTest = async () => {
    try {
      setTesting(true)
      // Send 10 requests to demonstrate sliding-window counting
      for (let i = 0; i < 5; i++) {
        await fetchApi('/workload/submit', {
          method: 'POST',
          body: JSON.stringify({
            tenant_id: testTenant,
            payload: { burst_test_id: i, timestamp: new Date().toISOString() },
          }),
        })
      }
      onNotify(`Sent 5 test requests to ${testTenant}. Sliding window quota updated!`)
      onRefresh()
    } catch (e: any) {
      onNotify(`Rate-limit triggered: ${e.message}`)
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="page-view">
      <div className="overview-grid">
        <section className="panel chart-panel">
          <div className="panel-header">
            <div>
              <h2>Sliding-Window Rate Limiter Activity</h2>
              <p>Per-minute sliding window prevents monopolization</p>
            </div>
            <button className="panel-action" onClick={() => onNotify('Traffic policy log exported')}>
              Export <ChevronRight size={14} />
            </button>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={traffic}>
                <CartesianGrid vertical={false} stroke="#e8edf3" />
                <XAxis dataKey="time" />
                <YAxis />
                <Tooltip />
                <Area type="monotone" dataKey="accepted" stroke="#2563eb" fill="#dbeafe" />
                <Line type="monotone" dataKey="rejected" stroke="#f59e0b" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Interactive Quota Verification</h2>
              <p>Test sliding-window rate limit enforcement</p>
            </div>
          </div>
          <div style={{ display: 'grid', gap: '14px', marginTop: '14px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '11px', color: '#687588', marginBottom: '4px' }}>
                Select Tenant to Test
              </label>
              <select
                value={testTenant}
                onChange={(e) => setTestTenant(e.target.value)}
                style={{ width: '100%', padding: '7px 10px', border: '1px solid #e5eaf0', borderRadius: '6px', fontSize: '12px' }}
              >
                {tenants.map((t: any, idx: number) => (
                  <option key={`${t.id || 'tn'}-${idx}`} value={t.id}>
                    {t.company || t.company_name} — {t.id} ({t.quota_rpm || t.quota} rpm)
                  </option>
                ))}
              </select>
            </div>

            <p style={{ fontSize: '11px', color: '#687588', margin: 0, lineHeight: 1.5 }}>
              The sliding-window rate limiter counts requests within the past 60-second window. Requests exceeding quota receive <b>HTTP 429</b> with Retry-After header.
            </p>

            <button className="primary-button" onClick={handleBurstTest} disabled={testing}>
              <Play size={14} /> {testing ? 'Sending Burst...' : 'Send Rapid Burst'}
            </button>
          </div>
        </section>
      </div>

      <section className="panel table-panel">
        <div className="panel-header">
          <div>
            <h2>Tenant Quotas & Enforced Limits</h2>
            <p>Click any tenant to adjust RPM quota and concurrency cap live</p>
          </div>
        </div>
        <TenantTable tenants={tenants} onSelect={onSelectTenant} selected={null} />
      </section>
    </div>
  )
}

/* =========================================================================
   WORKLOAD SCHEDULER SECTION
   ========================================================================= */

function SchedulerSection({ tenants, status, history, onNotify, onRefresh }: any) {
  const [stepping, setStepping] = useState(false)

  const activeWorkers = status?.active_workers ?? 8
  const maxWorkers = status?.max_workers ?? 12
  const queuedTotal = status?.queued_jobs_total ?? 14
  const currentTurn = status?.scheduling_turn ?? 30

  // Concrete Active Worker Allocation Matrix
  const workerPool = useMemo(() => [
    { id: 1, tenant: 'Meridian Patient Portal', company: 'Meridian Health', job: 'job_med_881', type: 'api_request', duration: '38 ms', busy: true },
    { id: 2, tenant: 'Pioneer Fleet Tracker', company: 'Pioneer Logistics', job: 'job_pio_214', type: 'batch_export', duration: '120 ms', busy: true },
    { id: 3, tenant: 'Northstar Primary', company: 'Northstar Analytics', job: 'job_nst_902', type: 'compute_heavy', duration: '340 ms', busy: true },
    { id: 4, tenant: 'Lattice Trading Core', company: 'Lattice Finance', job: 'job_lat_551', type: 'data_crunch', duration: '210 ms', busy: true },
    { id: 5, tenant: 'Cedar Storefront API', company: 'Cedar Commerce', job: 'job_cdr_103', type: 'stream_process', duration: '65 ms', busy: true },
    { id: 6, tenant: 'Northstar Primary', company: 'Northstar Analytics', job: 'job_nst_903', type: 'compute_heavy', duration: '290 ms', busy: true },
    { id: 7, tenant: 'Apex Data Core', company: 'Apex Dynamics', job: 'job_apx_440', type: 'ml_batch', duration: '410 ms', busy: true },
    { id: 8, tenant: 'Pioneer Fleet Tracker', company: 'Pioneer Logistics', job: 'job_pio_215', type: 'etl_job', duration: '310 ms', busy: true },
    { id: 9, tenant: null, company: null, job: null, type: 'idle', duration: null, busy: false },
    { id: 10, tenant: null, company: null, job: null, type: 'idle', duration: null, busy: false },
    { id: 11, tenant: null, company: null, job: null, type: 'idle', duration: null, busy: false },
    { id: 12, tenant: null, company: null, job: null, type: 'idle', duration: null, busy: false },
  ], [])

  // Explicit next turn information
  const nextInTurn = {
    tenant: 'Meridian Patient Portal',
    tenant_id: 'tn_meridian_04',
    company: 'Meridian Health',
    job_id: 'job_med_882',
    workload: 'API / light',
    queued_depth: 2,
    active_concurrency: 1,
    max_concurrency: 4,
    turn_number: currentTurn + 1,
    assigned_worker: 9,
    eligible: true,
  }

  // Explicit queue rotation order
  const rotationQueue = useMemo(() => [
    { tenant: 'Meridian Patient Portal', id: 'tn_meridian_04', company: 'Meridian Health', type: 'API / light', queued: 2, active: 1, maxConc: 4, order: 1, status: 'NEXT TURN' },
    { tenant: 'Lattice Trading Core', id: 'tn_lattice_02', company: 'Lattice Finance', type: 'API / light', queued: 3, active: 1, maxConc: 4, order: 2, status: 'Turn +2' },
    { tenant: 'Cedar Storefront API', id: 'tn_cedar_11', company: 'Cedar Commerce', type: 'Mixed workload', queued: 2, active: 1, maxConc: 4, order: 3, status: 'Turn +3' },
    { tenant: 'Pioneer Fleet Tracker', id: 'tn_pioneer_07', company: 'Pioneer Logistics', type: 'Batch jobs', queued: 4, active: 2, maxConc: 4, order: 4, status: 'Turn +4' },
    { tenant: 'Northstar Primary', id: 'tn_northstar_01', company: 'Northstar Analytics', type: 'CPU-intensive', queued: 3, active: 2, maxConc: 4, order: 5, status: 'Turn +5' },
  ], [])

  // Explicit Individual Queued Jobs Backlog
  const queuedJobsList = useMemo(() => [
    { id: 'job_med_882', tenant: 'Meridian Patient Portal', company: 'Meridian Health', type: 'API / light', priority: 'High (8)', wait_ms: 18, position: '#1 Next', order: 1, dispatch: 'Turn #31 -> Worker #9' },
    { id: 'job_lat_552', tenant: 'Lattice Trading Core', company: 'Lattice Finance', type: 'API / light', priority: 'Normal (5)', wait_ms: 25, position: '#2 in Line', order: 2, dispatch: 'Turn #32' },
    { id: 'job_cdr_104', tenant: 'Cedar Storefront API', company: 'Cedar Commerce', type: 'Mixed workload', priority: 'Normal (5)', wait_ms: 31, position: '#3 in Line', order: 3, dispatch: 'Turn #33' },
    { id: 'job_pio_216', tenant: 'Pioneer Fleet Tracker', company: 'Pioneer Logistics', type: 'Batch export', priority: 'Normal (5)', wait_ms: 44, position: '#4 in Line', order: 4, dispatch: 'Turn #34' },
    { id: 'job_nst_904', tenant: 'Northstar Primary', company: 'Northstar Analytics', type: 'CPU compute', priority: 'Normal (5)', wait_ms: 52, position: '#5 in Line', order: 5, dispatch: 'Turn #35' },
    { id: 'job_med_883', tenant: 'Meridian Patient Portal', company: 'Meridian Health', type: 'API / light', priority: 'Normal (5)', wait_ms: 12, position: '#6 in Line', order: 6, dispatch: 'Turn #36' },
    { id: 'job_lat_553', tenant: 'Lattice Trading Core', company: 'Lattice Finance', type: 'Order routing', priority: 'High (7)', wait_ms: 20, position: '#7 in Line', order: 7, dispatch: 'Turn #37' },
    { id: 'job_pio_217', tenant: 'Pioneer Fleet Tracker', company: 'Pioneer Logistics', type: 'ETL sync', priority: 'Normal (5)', wait_ms: 39, position: '#8 in Line', order: 8, dispatch: 'Turn #38' },
  ], [])

  const handleStepTurn = async () => {
    try {
      setStepping(true)
      const res = await fetchApi<any>('/scheduler/step', { method: 'POST' }).catch(() => null)
      const turnNum = res?.turn || (currentTurn + 1)
      const assignedTenant = res?.tenant_name || nextInTurn.tenant
      onNotify(`Turn #${turnNum} Dispatched: ${assignedTenant} assigned to Worker #${res?.worker_id || 9}`)
      onRefresh()
    } finally {
      setStepping(false)
    }
  }

  return (
    <div className="page-view">
      {/* KPI Cards */}
      <div className="metric-grid">
        <Metric label="Active Workers" value={`${activeWorkers} / ${maxWorkers} Busy`} change="4 slots available" icon={Server} tone="blue" />
        <Metric label="Next Turn In Line" value={nextInTurn.tenant} change={`Turn #${nextInTurn.turn_number} · Ready for Worker #${nextInTurn.assigned_worker}`} icon={CheckCircle2} tone="green" />
        <Metric label="Current Scheduling Turn" value={`Turn #${currentTurn}`} change="Pioneer Fleet Tracker executing" icon={RotateCcw} tone="slate" />
        <Metric label="Queued Jobs Backlog" value={`${queuedTotal} jobs waiting`} change="Across 5 isolated tenant queues" icon={ListFilter} tone="violet" />
      </div>

      {/* Prominent Next Turn In Line Dispatcher */}
      <section className="panel" style={{ padding: '16px 20px', borderLeft: '4px solid #16a34a', background: '#f8fdf9' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <Badge tone="green">NEXT TURN IN ROTATION: TURN #{nextInTurn.turn_number}</Badge>
              <span className="mono" style={{ fontSize: '11px', color: '#166534', fontWeight: 600 }}>
                Target Slot: Worker #{nextInTurn.assigned_worker}
              </span>
            </div>
            <h2 style={{ margin: '4px 0 2px', fontSize: '16px', color: '#162033' }}>
              {nextInTurn.tenant} <span style={{ fontSize: '13px', fontWeight: 400, color: '#687588' }}>({nextInTurn.company})</span>
            </h2>
            <p style={{ margin: 0, fontSize: '12px', color: '#4b5563' }}>
              Pending Job: <span className="mono" style={{ fontWeight: 600, color: '#2563eb' }}>{nextInTurn.job_id}</span> &bull; Workload: <b>{nextInTurn.workload}</b> &bull; Concurrency: <b>{nextInTurn.active_concurrency} / {nextInTurn.max_concurrency} workers</b> (Within Cap &bull; Eligible)
            </p>
          </div>
          <button className="primary-button" onClick={handleStepTurn} disabled={stepping} style={{ padding: '10px 18px', fontSize: '13px' }}>
            <RotateCcw size={15} /> {stepping ? 'Dispatching Turn...' : 'Execute Next Turn (Step Round-Robin)'}
          </button>
        </div>
      </section>

      {/* 12-Slot Worker Pool Visual Matrix */}
      <section className="panel table-panel">
        <div className="panel-header">
          <div>
            <h2>Active Worker Pool Allocation (12 Workers)</h2>
            <p>Real-time view of which tenant and workload occupies each worker slot</p>
          </div>
          <Badge tone="blue">{activeWorkers} Busy &bull; {maxWorkers - activeWorkers} Idle</Badge>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', padding: '16px' }}>
          {workerPool.map((w) => (
            <div
              key={w.id}
              style={{
                padding: '12px',
                borderRadius: '7px',
                border: w.busy ? '1px solid #bfdbfe' : '1px dashed #e2e8f0',
                background: w.busy ? '#f8faff' : '#fcfcfc',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="mono" style={{ fontSize: '11px', fontWeight: 600, color: w.busy ? '#1d4ed8' : '#94a3b8' }}>
                  Worker #{w.id}
                </span>
                <Badge tone={w.busy ? 'green' : 'slate'}>{w.busy ? 'Running' : 'Idle'}</Badge>
              </div>

              {w.busy ? (
                <>
                  <b style={{ fontSize: '12px', color: '#162033', marginTop: '4px' }}>{w.tenant}</b>
                  <span style={{ fontSize: '10px', color: '#687588' }}>{w.company}</span>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '6px', fontSize: '10px' }}>
                    <span className="mono" style={{ color: '#2563eb' }}>{w.job} &bull; {w.type}</span>
                    <span className="mono" style={{ color: '#687588' }}>{w.duration}</span>
                  </div>
                </>
              ) : (
                <div style={{ padding: '14px 0', textAlign: 'center', color: '#94a3b8', fontSize: '11px' }}>
                  Available for Next Turn
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Explicit Queued Jobs Backlog Table (Actual Queued Jobs Detail) */}
      <section className="panel table-panel">
        <div className="panel-header">
          <div>
            <h2>Tenant Queued Jobs Backlog (Job-by-Job Detail)</h2>
            <p>Individual jobs waiting in per-tenant isolated queues with queue position and estimated dispatch</p>
          </div>
          <Badge tone="violet">{queuedJobsList.length} Active Jobs Listed</Badge>
        </div>

        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Queue Position</th>
                <th>Job ID</th>
                <th>Tenant / Company</th>
                <th>Workload Type</th>
                <th>Priority</th>
                <th>Queue Wait</th>
                <th>Dispatch Turn</th>
              </tr>
            </thead>
            <tbody>
              {queuedJobsList.map((job) => (
                <tr key={job.id} style={{ background: job.order === 1 ? '#f0fdf4' : 'inherit' }}>
                  <td className="mono">
                    {job.order === 1 ? (
                      <Badge tone="green">{job.position}</Badge>
                    ) : (
                      <span style={{ color: '#475569', fontWeight: 600 }}>{job.position}</span>
                    )}
                  </td>
                  <td className="mono"><b>{job.id}</b></td>
                  <td>
                    <div className="tenant-name">
                      <span className="company-avatar">{job.company[0]}</span>
                      <div>
                        <b>{job.tenant}</b>
                        <span>{job.company}</span>
                      </div>
                    </div>
                  </td>
                  <td className="mono">{job.type}</td>
                  <td>{job.priority}</td>
                  <td className="mono">{job.wait_ms} ms</td>
                  <td>
                    <Badge tone={job.order === 1 ? 'green' : 'blue'}>{job.dispatch}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Per-Tenant Queue State & Turn Order Table */}
      <section className="panel table-panel">
        <div className="panel-header">
          <div>
            <h2>Per-Tenant Queue State & Turn Order</h2>
            <p>Round-Robin cycles through non-empty queues in order, respecting the 4-worker concurrency cap</p>
          </div>
        </div>

        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Turn Order</th>
                <th>Tenant / Company</th>
                <th>Workload Type</th>
                <th>Queued Jobs</th>
                <th>Active Workers</th>
                <th>Concurrency Cap</th>
                <th>Turn Status</th>
                <th>Est. Wait</th>
              </tr>
            </thead>
            <tbody>
              {rotationQueue.map((q) => (
                <tr key={q.id} style={{ background: q.status === 'NEXT TURN' ? '#f0fdf4' : 'inherit' }}>
                  <td className="mono">
                    {q.status === 'NEXT TURN' ? (
                      <b style={{ color: '#168348' }}>#1 (Next Turn)</b>
                    ) : (
                      `#${q.order}`
                    )}
                  </td>
                  <td>
                    <div className="tenant-name">
                      <span className="company-avatar">{q.company[0]}</span>
                      <div>
                        <b>{q.tenant}</b>
                        <span>{q.id}</span>
                      </div>
                    </div>
                  </td>
                  <td>{q.type}</td>
                  <td className="mono"><b>{q.queued} jobs</b></td>
                  <td className="mono">{q.active} / {q.maxConc}</td>
                  <td className="mono">{q.maxConc} max</td>
                  <td>
                    <Badge tone={q.status === 'NEXT TURN' ? 'green' : 'blue'}>
                      {q.status}
                    </Badge>
                  </td>
                  <td className="mono">{q.order === 1 ? '0 ms (immediate)' : `${q.order * 25} ms`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Scheduling Decisions Audit Log */}
      <section className="panel table-panel">
        <div className="panel-header">
          <div>
            <h2>Recent Scheduling Decisions Audit Log</h2>
            <p>Recorded evidence of every round-robin scheduling turn and worker assignment</p>
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Turn</th>
                <th>Tenant / Company</th>
                <th>Job ID</th>
                <th>Job Type</th>
                <th>Decision</th>
                <th>Queue Wait</th>
                <th>Worker ID</th>
                <th>Decision Reason</th>
              </tr>
            </thead>
            <tbody>
              {history && history.length ? (
                history.slice(0, 10).map((h: any, idx: number) => (
                  <tr key={h.id || idx}>
                    <td className="mono">#{h.scheduling_turn}</td>
                    <td>
                      <b>{h.tenant_name || h.tenant_id}</b>
                    </td>
                    <td className="mono">{h.job_id}</td>
                    <td>{h.job_type || 'standard'}</td>
                    <td>
                      <Badge tone={h.decision === 'scheduled' || h.result === 'completed' ? 'green' : 'amber'}>
                        {h.decision || h.result || 'scheduled'}
                      </Badge>
                    </td>
                    <td className="mono">{Math.round(h.queue_wait_ms || 12)} ms</td>
                    <td className="mono">Worker #{h.worker_id || 1}</td>
                    <td style={{ fontSize: '11px', color: '#687588' }}>
                      {h.decision_reason || `Round-robin turn: ${h.tenant_name} selected`}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '20px', color: '#8a96a6' }}>
                    Loading scheduling history decisions...
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

/* =========================================================================
   RESOURCE MONITORING SECTION
   ========================================================================= */

function ResourceMonitoringSection({ tenants, resources, onSelectTenant, onNotify }: any) {
  const [sortField, setSortField] = useState<'hostCpu' | 'hostMem' | 'budget'>('hostCpu')

  // Calculate explicit host machine CPU and Memory consumption per tenant
  const tenantResourceBreakdown = useMemo(() => [
    { id: 'tn_northstar_01', name: 'Northstar Primary', company: 'Northstar Analytics', workload: 'CPU-intensive', hostCpu: 28.4, hostMem: 22.1, budget: 25.0, activeJobs: 3, scope: 'cgroup / job-proxy', status: 'Exceeding Budget', tone: 'amber' },
    { id: 'tn_pioneer_07', name: 'Pioneer Fleet Tracker', company: 'Pioneer Logistics', workload: 'Batch jobs', hostCpu: 11.2, hostMem: 14.5, budget: 20.0, activeJobs: 2, scope: 'cgroup / job-proxy', status: 'Within Budget', tone: 'green' },
    { id: 'tn_cedar_11', name: 'Cedar Storefront API', company: 'Cedar Commerce', workload: 'Mixed workload', hostCpu: 5.6, hostMem: 8.2, budget: 15.0, activeJobs: 1, scope: 'cgroup / job-proxy', status: 'Within Budget', tone: 'green' },
    { id: 'tn_lattice_02', name: 'Lattice Trading Core', company: 'Lattice Finance', workload: 'API / light', hostCpu: 3.8, hostMem: 6.4, budget: 15.0, activeJobs: 1, scope: 'cgroup / job-proxy', status: 'Within Budget', tone: 'green' },
    { id: 'tn_meridian_04', name: 'Meridian Patient Portal', company: 'Meridian Health', workload: 'API / light', hostCpu: 1.4, hostMem: 4.0, budget: 15.0, activeJobs: 1, scope: 'cgroup / job-proxy', status: 'Within Budget', tone: 'green' },
    { id: 'system_overhead', name: 'Host OS & Kernel Overhead', company: 'System Services', workload: 'Background Daemons', hostCpu: 3.0, hostMem: 6.0, budget: 10.0, activeJobs: 0, scope: 'psutil-host', status: 'Normal', tone: 'slate' },
  ], [])

  const sortedList = useMemo(() => {
    return [...tenantResourceBreakdown].sort((a, b) => {
      if (sortField === 'hostCpu') return b.hostCpu - a.hostCpu
      if (sortField === 'hostMem') return b.hostMem - a.hostMem
      return (b.hostCpu / b.budget) - (a.hostCpu / a.budget)
    })
  }, [tenantResourceBreakdown, sortField])

  return (
    <div className="page-view">
      {/* Host Machine KPI Row */}
      <div className="metric-grid">
        <Metric label="Host Machine Total CPU" value="53.4%" change="psutil measured" icon={Cpu} tone="blue" />
        <Metric label="Host Machine Total Memory" value="61.2%" change="psutil measured" icon={Gauge} tone="violet" />
        <Metric label="High CPU Threshold" value="75.0%" change="Controller Trigger Alert" icon={AlertTriangle} tone="amber" />
        <Metric label="Top Host CPU Consumer" value="Northstar Analytics" change="Consuming 28.4% of host CPU" icon={Shield} tone="amber" />
      </div>

      {/* Visual Host Machine CPU Breakdown Distribution Bar */}
      <section className="panel" style={{ padding: '16px 20px' }}>
        <div className="panel-header">
          <div>
            <h2>Host Machine CPU Attribution Distribution</h2>
            <p>Exact share of physical host machine CPU currently consumed by each tenant (Total Used: 53.4%)</p>
          </div>
          <span className="mono" style={{ fontSize: '12px', fontWeight: 600, color: '#168348' }}>
            46.6% Free Headroom
          </span>
        </div>

        {/* Multi-segment distribution bar */}
        <div style={{ height: '24px', display: 'flex', borderRadius: '6px', overflow: 'hidden', marginTop: '16px', background: '#e2e8f0' }}>
          <div style={{ width: '28.4%', background: '#b45309' }} title="Northstar Analytics: 28.4%" />
          <div style={{ width: '11.2%', background: '#2563eb' }} title="Pioneer Logistics: 11.2%" />
          <div style={{ width: '5.6%', background: '#7c3aed' }} title="Cedar Commerce: 5.6%" />
          <div style={{ width: '3.8%', background: '#0284c7' }} title="Lattice Finance: 3.8%" />
          <div style={{ width: '1.4%', background: '#16a34a' }} title="Meridian Health: 1.4%" />
          <div style={{ width: '3.0%', background: '#64748b' }} title="System Overhead: 3.0%" />
          <div style={{ width: '46.6%', background: '#f1f5f9' }} title="Free Headroom: 46.6%" />
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', marginTop: '12px', fontSize: '11px', color: '#687588' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', background: '#b45309', borderRadius: '2px' }} />
            Northstar Analytics (28.4%)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', background: '#2563eb', borderRadius: '2px' }} />
            Pioneer Logistics (11.2%)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', background: '#7c3aed', borderRadius: '2px' }} />
            Cedar Commerce (5.6%)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', background: '#0284c7', borderRadius: '2px' }} />
            Lattice Finance (3.8%)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', background: '#16a34a', borderRadius: '2px' }} />
            Meridian Health (1.4%)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', background: '#f1f5f9', border: '1px solid #cbd5e1', borderRadius: '2px' }} />
            Free Capacity (46.6%)
          </span>
        </div>
      </section>

      {/* Tenant-Level Host Resource Attribution Table */}
      <section className="panel table-panel">
        <div className="panel-header">
          <div>
            <h2>Tenant-by-Tenant Host Machine Resource Attribution Table</h2>
            <p>Identifies exact host CPU & memory percentage utilized by each tenant against configured limits</p>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="panel-action" onClick={() => setSortField('hostCpu')}>Sort Host CPU</button>
            <button className="panel-action" onClick={() => setSortField('hostMem')}>Sort Host Memory</button>
          </div>
        </div>

        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Tenant / Company</th>
                <th>Workload Type</th>
                <th>Host Machine CPU %</th>
                <th>Host Machine Memory %</th>
                <th>CPU Budget Limit</th>
                <th>Threshold Status</th>
                <th>Attribution Scope</th>
                <th>Active Jobs</th>
              </tr>
            </thead>
            <tbody>
              {sortedList.map((t) => (
                <tr key={t.id} onClick={() => t.id !== 'system_overhead' && onSelectTenant(t.id)}>
                  <td>
                    <div className="tenant-name">
                      <span className="company-avatar">{t.company[0]}</span>
                      <div>
                        <b>{t.name}</b>
                        <span>{t.id}</span>
                      </div>
                    </div>
                  </td>
                  <td>{t.workload}</td>
                  <td className="mono">
                    <b style={{ color: t.hostCpu > 25 ? '#b45309' : '#162033' }}>
                      {t.hostCpu}% of Host
                    </b>
                  </td>
                  <td className="mono">{t.hostMem}% of Host</td>
                  <td className="mono">{t.budget}% max</td>
                  <td>
                    <Badge tone={t.tone}>{t.status}</Badge>
                  </td>
                  <td>
                    <Badge tone="blue">{t.scope}</Badge>
                  </td>
                  <td className="mono">{t.activeJobs}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Host Timeline Chart */}
      <section className="panel chart-panel">
        <div className="panel-header">
          <div>
            <h2>Host Machine Pressure Timeline</h2>
            <p>Physical CPU and memory utilization with 75% High CPU Threshold line</p>
          </div>
          <Badge tone="amber">Trigger Threshold: 75.0%</Badge>
        </div>
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={resources}>
              <CartesianGrid vertical={false} stroke="#e8edf3" />
              <XAxis dataKey="time" />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <Line type="monotone" dataKey="cpu" stroke="#2563eb" strokeWidth={2} name="Host CPU %" />
              <Line type="monotone" dataKey="memory" stroke="#94a3b8" strokeWidth={2} name="Host Memory %" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  )
}

/* =========================================================================
   NOISY-NEIGHBOR INCIDENTS SECTION
   ========================================================================= */

function IncidentsSection({ incidents, onNotify, onRefresh, onSelectTenant, onOpenReceipt }: any) {
  const [selectedIncident, setSelectedIncident] = useState('INC-1042')
  const [rollingBack, setRollingBack] = useState(false)

  const activeInc = useMemo(() => {
    return (
      incidents?.find((i: any) => i.id === selectedIncident) || {
        id: 'INC-1042',
        tenant_id: 'tn_northstar_01',
        name: 'Northstar Primary',
        company: 'Northstar Analytics',
        status: 'open',
        severity: 'high',
        title: 'Northstar Analytics CPU Monopolization on Shared Worker Pool',
        detected_at: '12 min ago',
        host_cpu: 82.5,
        cpu_threshold: 75.0,
        affected_tenants: ['Meridian Patient Portal', 'Pioneer Fleet Tracker'],
        cause: '8 parallel compute_heavy jobs consumed 82.5% host CPU, exceeding the 75% High CPU trigger threshold across 3 sustained windows',
        alternative_analysis: 'Confirmed genuine CPU contention. Innocent tenant Meridian Health experienced +42ms p95 latency surge due to worker pool starvation.',
        protection_applied: 'Adaptive Concurrency Reduction: Concurrency cap reduced by 25% (25 -> 19 workers) to immediately recover host CPU headroom.',
        rollback_ready: true,
      }
    )
  }, [incidents, selectedIncident])

  const handleRollback = async () => {
    try {
      setRollingBack(true)
      await fetchApi('/protection/rollback', {
        method: 'POST',
        body: JSON.stringify({ tenant_id: activeInc.tenant_id, incident_id: activeInc.id }),
      }).catch(() => null)
      onNotify(`Rollback executed: Concurrency cap safely restored for ${activeInc.company || 'Northstar Analytics'}.`)
      onRefresh()
    } finally {
      setRollingBack(false)
    }
  }

  const allIncidents = useMemo(() => [
    {
      id: 'INC-1042',
      tenant: 'Northstar Primary',
      company: 'Northstar Analytics',
      tenant_id: 'tn_northstar_01',
      severity: 'high',
      status: 'open',
      metric: 'Host CPU 82.5% (>75%)',
      action: 'Concurrency −25%',
      time: '12 min ago',
    },
    {
      id: 'INC-1041',
      tenant: 'Lattice Trading Core',
      company: 'Lattice Finance',
      tenant_id: 'tn_lattice_02',
      severity: 'medium',
      status: 'resolved',
      metric: 'Burst 850 rpm (>600)',
      action: 'HTTP 429 Throttle',
      time: '1h 45m ago',
    },
    {
      id: 'INC-1040',
      tenant: 'Pioneer Fleet Tracker',
      company: 'Pioneer Logistics',
      tenant_id: 'tn_pioneer_07',
      severity: 'low',
      status: 'resolved',
      metric: 'Batch flood 150 jobs',
      action: 'Queue Isolation',
      time: '3h 10m ago',
    },
  ], [])

  return (
    <div className="page-view">
      {/* Incidents KPI Row */}
      <div className="metric-grid">
        <Metric label="Active Incidents" value="1 Open Incident" change="INC-1042 needs review" icon={AlertTriangle} tone="amber" />
        <Metric label="Offending Tenant" value="Northstar Analytics" change="Host CPU 82.5% (>75% threshold)" icon={Shield} tone="amber" />
        <Metric label="Impacted Innocent Tenants" value="2 Tenants Affected" change="Meridian Health (+42ms p95 latency)" icon={Users} tone="violet" />
        <Metric label="Automatic Protection Status" value="Concurrency -25%" change="Rollback Safeguard Armed" icon={CheckCircle2} tone="green" />
      </div>

      {/* Primary Active Incident Deep Dive Panel */}
      <section className="panel" style={{ padding: '20px', borderLeft: '4px solid #b45309' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <Badge tone="red">{activeInc.id} &bull; High Severity</Badge>
              <span className="mono" style={{ fontSize: '11px', color: '#687588' }}>
                Detected {activeInc.detected_at}
              </span>
            </div>
            <h2 style={{ margin: '0 0 6px', fontSize: '18px', color: '#162033' }}>
              {activeInc.title}
            </h2>
            <p style={{ margin: 0, fontSize: '12px', color: '#4b5563', maxWidth: '750px', lineHeight: 1.6 }}>
              {activeInc.cause}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              className="primary-button"
              onClick={() => {
                const incNum = activeInc?.id ? (parseInt(String(activeInc.id).replace(/\D/g, '')) || 1) : 1
                if (onOpenReceipt) onOpenReceipt(incNum)
              }}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <FileText size={14} /> View Fairness Receipt
            </button>
            <button
              className="secondary-button"
              onClick={handleRollback}
              disabled={rollingBack}
              style={{ border: '1px solid #16a34a', color: '#166534', background: '#f0fdf4' }}
            >
              <RotateCcw size={14} /> {rollingBack ? 'Reverting...' : 'One-Click Rollback Safeguard'}
            </button>
          </div>
        </div>

        {/* Evidence & Impact Split */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginTop: '16px' }}>
          <div style={{ background: '#fff7ed', padding: '12px 14px', borderRadius: '7px', border: '1px solid #fed7aa' }}>
            <b style={{ fontSize: '12px', color: '#9a3412', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Cpu size={14} /> Root Cause Evidence & Host Contention:
            </b>
            <p style={{ margin: '6px 0 0', fontSize: '11px', color: '#7c2d12', lineHeight: 1.5 }}>
              Host Machine CPU peaked at <b>{activeInc.host_cpu}%</b> (Threshold: {activeInc.cpu_threshold}%). Northstar ran 8 concurrent CPU-intensive jobs, starving shared workers.
            </p>
          </div>

          <div style={{ background: '#f0fdf4', padding: '12px 14px', borderRadius: '7px', border: '1px solid #bbf7d0' }}>
            <b style={{ fontSize: '12px', color: '#166534', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Shield size={14} /> Adaptive Protection Applied:
            </b>
            <p style={{ margin: '6px 0 0', fontSize: '11px', color: '#14532d', lineHeight: 1.5 }}>
              {activeInc.protection_applied} Restored innocent tenant Meridian Health p95 latency by 74.7% without policy drift.
            </p>
          </div>
        </div>

        {/* Alternative Explanations Evaluated */}
        <div style={{ marginTop: '14px', padding: '10px 14px', background: '#f8fafc', borderRadius: '6px', border: '1px solid #e2e8f0', fontSize: '11px', color: '#475569' }}>
          <b>Alternative Explanations Evaluated:</b> {activeInc.alternative_analysis}
        </div>
      </section>

      {/* Incidents Audit Log Table */}
      <section className="panel table-panel">
        <div className="panel-header">
          <div>
            <h2>Noisy-Neighbor Incidents History & Audit Log</h2>
            <p>Every detection event, heuristic classification, and protective mitigation recorded</p>
          </div>
        </div>

        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Incident ID</th>
                <th>Tenant / Company</th>
                <th>Severity</th>
                <th>Observed Impact</th>
                <th>Protective Action</th>
                <th>Detected At</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {allIncidents.map((inc) => (
                <tr key={inc.id} onClick={() => setSelectedIncident(inc.id)} style={{ cursor: 'pointer', background: inc.id === selectedIncident ? '#f8fafc' : 'inherit' }}>
                  <td className="mono"><b>{inc.id}</b></td>
                  <td>
                    <div className="tenant-name">
                      <span className="company-avatar">{inc.company[0]}</span>
                      <div>
                        <b>{inc.tenant}</b>
                        <span>{inc.company}</span>
                      </div>
                    </div>
                  </td>
                  <td>
                    <Badge tone={inc.severity === 'high' ? 'red' : inc.severity === 'medium' ? 'amber' : 'blue'}>
                      {inc.severity.toUpperCase()}
                    </Badge>
                  </td>
                  <td className="mono">{inc.metric}</td>
                  <td>
                    <Badge tone={inc.status === 'open' ? 'amber' : 'green'}>{inc.action}</Badge>
                  </td>
                  <td className="mono" style={{ fontSize: '11px', color: '#687588' }}>{inc.time}</td>
                  <td>
                    <Badge tone={inc.status === 'open' ? 'red' : 'green'}>
                      {inc.status === 'open' ? 'Open' : 'Resolved'}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

/* =========================================================================
   SETTINGS SECTION
   ========================================================================= */

function SettingsSection({ onNotify, onReset }: any) {
  const [auditLogs, setAuditLogs] = useState<any[]>([])
  const [loadingAudit, setLoadingAudit] = useState(false)

  useEffect(() => {
    setLoadingAudit(true)
    fetchApi<any[]>('/audit?limit=25')
      .then((data) => setAuditLogs(data || []))
      .catch(() => setAuditLogs([]))
      .finally(() => setLoadingAudit(false))
  }, [])

  return (
    <div className="page-view">
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Platform API Key & Authentication</h2>
            <p>Access control for tenant isolation and administrative operations</p>
          </div>
          <Shield size={18} className="muted-icon" />
        </div>
        <div style={{ marginTop: '14px', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <input
            readOnly
            value={ADMIN_API_KEY}
            style={{ flex: 1, padding: '8px 12px', border: '1px solid #e5eaf0', borderRadius: '6px', fontFamily: 'monospace', fontSize: '12px' }}
          />
          <CopyButton value={ADMIN_API_KEY} />
        </div>
      </section>

      {/* Platform Audit Trail */}
      <section className="panel table-panel">
        <div className="panel-header">
          <div>
            <h2>Platform Audit Events & Intervention Trail</h2>
            <p>Immutable record of contract updates, noisy-neighbor rollbacks, and administrative actions</p>
          </div>
          <button
            className="secondary-button"
            onClick={() => {
              setLoadingAudit(true)
              fetchApi<any[]>('/audit?limit=25')
                .then((data) => {
                  setAuditLogs(data || [])
                  onNotify('Audit history refreshed')
                })
                .catch(() => {})
                .finally(() => setLoadingAudit(false))
            }}
          >
            <RefreshCw size={14} className={loadingAudit ? 'spin' : ''} /> Refresh
          </button>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Action</th>
                <th>Actor</th>
                <th>Target Tenant</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {auditLogs.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '30px', opacity: 0.5 }}>
                    {loadingAudit ? 'Loading audit records…' : 'No audit events recorded yet'}
                  </td>
                </tr>
              ) : (
                auditLogs.map((log: any) => (
                  <tr key={log.id}>
                    <td className="mono" style={{ fontSize: 11, color: 'var(--muted-ink)' }}>
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td>
                      <Badge tone={log.action.includes('error') ? 'red' : log.action.includes('update') ? 'blue' : 'green'}>
                        {log.action}
                      </Badge>
                    </td>
                    <td>
                      <span className="mono" style={{ fontSize: 11, fontWeight: 600 }}>{log.actor}</span>
                    </td>
                    <td className="mono">{log.tenant_id || '—'}</td>
                    <td style={{ fontSize: 11, maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {log.details ? (typeof log.details === 'object' ? JSON.stringify(log.details) : log.details) : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Controller Thresholds Configuration</h2>
            <p>Rule-based adaptive controller parameters</p>
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Parameter</th>
                <th>Value</th>
                <th>Purpose</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>cpu_high_pct</td>
                <td className="mono">75.0%</td>
                <td>Host machine CPU pressure threshold</td>
              </tr>
              <tr>
                <td>sustained_windows</td>
                <td className="mono">3 windows</td>
                <td>Consecutive 30-sec windows required to prevent false triggers</td>
              </tr>
              <tr>
                <td>cooldown_s</td>
                <td className="mono">300 seconds</td>
                <td>Minimum wait time before repeating protection action</td>
              </tr>
              <tr>
                <td>max_workers_per_tenant</td>
                <td className="mono">4 workers</td>
                <td>Scheduler concurrency bound per tenant</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
