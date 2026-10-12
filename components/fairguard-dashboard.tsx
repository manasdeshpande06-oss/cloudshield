'use client'

import { useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Bell,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Clock3,
  Cloud,
  Copy,
  Cpu,
  Gauge,
  LayoutDashboard,
  ListFilter,
  Menu,
  Moon,
  MoreHorizontal,
  Network,
  Play,
  RefreshCw,
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
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const traffic = [
  { time: '08:00', accepted: 4100, rejected: 180 }, { time: '09:00', accepted: 5200, rejected: 240 },
  { time: '10:00', accepted: 4800, rejected: 210 }, { time: '11:00', accepted: 6800, rejected: 390 },
  { time: '12:00', accepted: 6100, rejected: 280 }, { time: '13:00', accepted: 7600, rejected: 460 },
  { time: '14:00', accepted: 7200, rejected: 340 }, { time: '15:00', accepted: 8400, rejected: 510 },
]
const resource = [
  { time: '08:00', cpu: 42, memory: 54, queue: 18 }, { time: '09:00', cpu: 48, memory: 58, queue: 24 },
  { time: '10:00', cpu: 51, memory: 61, queue: 29 }, { time: '11:00', cpu: 78, memory: 69, queue: 63 },
  { time: '12:00', cpu: 72, memory: 68, queue: 55 }, { time: '13:00', cpu: 66, memory: 65, queue: 41 },
  { time: '14:00', cpu: 59, memory: 62, queue: 34 }, { time: '15:00', cpu: 53, memory: 60, queue: 26 },
]
const tenants = [
  { company: 'Northstar Analytics', id: 'tn_northstar_01', type: 'CPU-intensive', rpm: '842', quota: '1,000', latency: '184 ms', rejected: 32, status: 'Protected', action: 'Concurrency −25%', tone: 'amber' },
  { company: 'Meridian Health', id: 'tn_meridian_04', type: 'API / light', rpm: '218', quota: '500', latency: '42 ms', rejected: 0, status: 'Healthy', action: 'None', tone: 'green' },
  { company: 'Pioneer Logistics', id: 'tn_pioneer_07', type: 'Batch jobs', rpm: '456', quota: '750', latency: '68 ms', rejected: 4, status: 'Healthy', action: 'None', tone: 'green' },
  { company: 'Lattice Finance', id: 'tn_lattice_02', type: 'API / light', rpm: '612', quota: '600', latency: '91 ms', rejected: 86, status: 'Throttled', action: 'Rate limit active', tone: 'red' },
  { company: 'Cedar Commerce', id: 'tn_cedar_11', type: 'Mixed workload', rpm: '336', quota: '500', latency: '57 ms', rejected: 8, status: 'Healthy', action: 'None', tone: 'green' },
]
const nav = [
  { label: 'Overview', icon: LayoutDashboard }, { label: 'Tenants', icon: Users }, { label: 'Traffic & Quotas', icon: Network },
  { label: 'Workload Scheduler', icon: ListFilter }, { label: 'Resource Monitoring', icon: Cpu }, { label: 'Noisy-Neighbor Incidents', icon: AlertTriangle },
  { label: 'Experiments & Reports', icon: BarChart3 }, { label: 'Settings', icon: Settings },
]

function Badge({ children, tone = 'slate' }: { children: React.ReactNode; tone?: string }) {
  return <span className={`badge badge-${tone}`}><span className="badge-dot" />{children}</span>
}
function Metric({ label, value, change, icon: Icon, tone = 'blue' }: { label: string; value: string; change: string; icon: React.ElementType; tone?: string }) {
  return <div className="metric-card"><div className="metric-head"><span>{label}</span><span className={`metric-icon ${tone}`}><Icon size={15} /></span></div><strong>{value}</strong><div className={change.startsWith('-') ? 'metric-change down' : 'metric-change'}>{change.startsWith('-') ? <ArrowDownRight size={13} /> : <ArrowUpRight size={13} />}{change}</div></div>
}

export default function FairGuardDashboard() {
  const [active, setActive] = useState('Overview')
  const [dark, setDark] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [range, setRange] = useState('Last 24 hours')
  const [incidentOpen, setIncidentOpen] = useState(true)
  const [toast, setToast] = useState('')
  const [running, setRunning] = useState(false)
  const [selectedTenant, setSelectedTenant] = useState<string | null>(null)
  const filteredTenants = useMemo(() => tenants.filter(t => `${t.company} ${t.id}`.toLowerCase().includes(query.toLowerCase())), [query])
  const notify = (message: string) => { setToast(message); window.setTimeout(() => setToast(''), 2800) }
  const pageTitle = active === 'Overview' ? 'Platform overview' : active

  return <div className={dark ? 'app-shell dark' : 'app-shell'}>
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className={mobileOpen ? 'sidebar open' : 'sidebar'}>
      <div className="brand"><div className="brand-mark"><Shield size={19} /></div><div><strong>CloudShield</strong><span>FairGuard</span></div><button className="mobile-close" onClick={() => setMobileOpen(false)} aria-label="Close menu"><X size={18} /></button></div>
      <div className="workspace"><div className="workspace-avatar">A</div><div><b>Acme Platform</b><span>Platform Admin</span></div><ChevronDown size={14} /></div>
      <nav className="nav-list" aria-label="Main navigation">{nav.map(({ label, icon: Icon }) => <button key={label} className={active === label ? 'nav-item active' : 'nav-item'} onClick={() => { setActive(label); setMobileOpen(false) }}><Icon size={17} /><span>{label}</span>{label === 'Noisy-Neighbor Incidents' && <span className="nav-count">1</span>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="sidebar-note"><Sparkles size={15} /><div><b>Demo simulation</b><span>Seeded data · local mode</span></div></div><button className="nav-item" onClick={() => notify('Documentation panel opened')}><BookOpen size={17} /><span>Documentation</span></button><div className="user-row"><div className="user-avatar">JD</div><div><b>Jordan Davis</b><span>Admin account</span></div><MoreHorizontal size={17} /></div></div>
    </aside>
    {mobileOpen && <button className="scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
    <section className="main-area">
      <header className="topbar"><button className="menu-button" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={20} /></button><div className="breadcrumbs"><span>CloudShield</span><ChevronRight size={14} /><b>{pageTitle}</b></div><div className="top-actions"><div className="global-search"><Search size={16} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search tenants, incidents, jobs" aria-label="Global search" />{query && <button onClick={() => setQuery('')} aria-label="Clear search"><X size={14} /></button>}<kbd>⌘ K</kbd></div><select className="range-select" value={range} onChange={e => setRange(e.target.value)} aria-label="Time range"><option>Last 24 hours</option><option>Last 7 days</option><option>Last 30 days</option></select><button className="icon-button" onClick={() => notify('Metrics refreshed just now')} aria-label="Refresh metrics"><RefreshCw size={17} /></button><button className="icon-button notification" onClick={() => notify('You have 3 unread notifications')} aria-label="Notifications"><Bell size={17} /><i /></button><button className="icon-button" onClick={() => setDark(!dark)} aria-label="Toggle dark mode">{dark ? <Sun size={17} /> : <Moon size={17} />}</button></div></header>
      <main id="main-content" className="content">
        <div className="page-heading"><div><div className="eyebrow"><span className="live-dot" />System nominal · updated 32 sec ago</div><h1>{pageTitle}</h1><p>{active === 'Overview' ? 'Understand workload health, fairness, and protection across your shared infrastructure.' : `Manage ${active.toLowerCase()} across the Acme Platform environment.`}</p></div><div className="heading-actions"><Badge tone="blue">Demo simulation</Badge><button className="secondary-button" onClick={() => notify('Help center opened')}><CircleHelp size={15} /> Help</button></div></div>
        {active !== 'Overview' ? <PageView active={active} tenants={filteredTenants} onNotify={notify} onRun={() => { setRunning(true); notify('Simulation started · collecting measurements'); window.setTimeout(() => setRunning(false), 2600) }} running={running} onSelect={setSelectedTenant} selected={selectedTenant} /> : <Overview traffic={traffic} resource={resource} tenants={filteredTenants} onNotify={notify} onSelect={setSelectedTenant} selected={selectedTenant} incidentOpen={incidentOpen} setIncidentOpen={setIncidentOpen} />}
      </main>
    </section>
    {toast && <div className="toast"><Check size={16} />{toast}</div>}
  </div>
}

function Overview({ traffic, resource, tenants, onNotify, onSelect, selected, incidentOpen, setIncidentOpen }: any) {
  return <>
    <div className="metric-grid"><Metric label="Requests received" value="48,294" change="+12.8% vs previous" icon={Activity} /><Metric label="Success rate" value="98.7%" change="+0.4% vs previous" icon={Check} tone="green" /><Metric label="p95 latency" value="184 ms" change="-18 ms vs previous" icon={Clock3} tone="violet" /><Metric label="Active incidents" value="1" change="Needs review" icon={AlertTriangle} tone="amber" /></div>
    <div className="overview-grid"><section className="panel chart-panel"><div className="panel-header"><div><h2>Request traffic</h2><p>Accepted and rejected requests · {"simulated"}</p></div><button className="panel-action" onClick={() => onNotify('Traffic view opened')}>View details <ChevronRight size={14} /></button></div><div className="chart-legend"><span><i className="legend-blue" />Accepted</span><span><i className="legend-gray" />Rejected</span></div><div className="chart-wrap"><ResponsiveContainer width="100%" height={250}><AreaChart data={traffic}><defs><linearGradient id="accepted" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#2563eb" stopOpacity={0.18} /><stop offset="100%" stopColor="#2563eb" stopOpacity={0} /></linearGradient></defs><CartesianGrid vertical={false} stroke="#e8edf3" /><XAxis dataKey="time" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#8a96a6' }} /><YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#8a96a6' }} tickFormatter={v => `${v / 1000}k`} /><Tooltip /><Area type="monotone" dataKey="accepted" stroke="#2563eb" strokeWidth={2} fill="url(#accepted)" /><Line type="monotone" dataKey="rejected" stroke="#f59e0b" strokeWidth={2} dot={false} /></AreaChart></ResponsiveContainer></div></section>
      <section className="panel protection-panel"><div className="panel-header"><div><h2>Protection posture</h2><p>Impact-aware controls</p></div><Gauge size={19} className="muted-icon" /></div><div className="posture-score"><div className="score-ring"><strong>82</strong><span>/ 100</span></div><div><b>Good coverage</b><p>One active action needs review.</p></div></div><div className="posture-list"><div><span><span className="status-dot green" />Fair scheduling</span><b>Enabled</b></div><div><span><span className="status-dot green" />Tenant quotas</span><b>10 / 10</b></div><div><span><span className="status-dot amber" />Noisy-neighbor rules</span><b>Monitoring</b></div><div><span><span className="status-dot green" />Rollback readiness</span><b>Ready</b></div></div><button className="wide-secondary" onClick={() => onNotify('Protection settings opened')}><SlidersHorizontal size={15} /> Review controls</button></section></div>
    {incidentOpen && <section className="incident-banner"><div className="incident-icon"><AlertTriangle size={19} /></div><div className="incident-copy"><div className="incident-title"><Badge tone="red">INC-1042 · High impact</Badge><span>Detected 14 min ago</span></div><h2>Northstar Analytics may be impacting shared workers</h2><p>CPU pressure and queue wait increased while 8 CPU-intensive jobs were active. Evidence strength: <b>strong signal</b>, not confirmed causation.</p><div className="incident-evidence"><span><Cpu size={14} /> CPU 78%</span><span><Clock3 size={14} /> p95 +42 ms</span><span><ListFilter size={14} /> Queue +39</span></div></div><div className="incident-actions"><button className="primary-button" onClick={() => onNotify('Protection action preview opened')}>Review incident</button><button className="icon-button" onClick={() => setIncidentOpen(false)} aria-label="Dismiss incident"><X size={16} /></button></div></section>}
    <section className="panel table-panel"><div className="panel-header"><div><h2>Tenant health</h2><p>Current window · 10 tenants monitored</p></div><button className="panel-action" onClick={() => onNotify('Tenant directory opened')}>View all tenants <ChevronRight size={14} /></button></div><TenantTable tenants={tenants} onSelect={onSelect} selected={selected} /></section>
    <div className="bottom-grid"><section className="panel resource-mini"><div className="panel-header"><div><h2>Shared resources</h2><p>Machine-level measurements · simulated</p></div><Server size={18} className="muted-icon" /></div><div className="resource-stats"><div><span>CPU utilization</span><strong>53%</strong><em className="good-text">Normal</em></div><div><span>Memory usage</span><strong>61%</strong><em className="good-text">Normal</em></div><div><span>Worker saturation</span><strong>68%</strong><em className="warn-text">Elevated</em></div></div><div className="mini-chart"><ResponsiveContainer width="100%" height={100}><LineChart data={resource}><XAxis dataKey="time" hide /><YAxis hide domain={[0, 100]} /><Line type="monotone" dataKey="cpu" stroke="#2563eb" strokeWidth={2} dot={false} /><Line type="monotone" dataKey="memory" stroke="#94a3b8" strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer></div></section><section className="panel events-panel"><div className="panel-header"><div><h2>Recent protection events</h2><p>Audit trail · simulated</p></div><button className="panel-action" onClick={() => onNotify('Event log opened')}>Event log <ChevronRight size={14} /></button></div><div className="event-list"><Event icon={Shield} title="Concurrency limit reduced" detail="Northstar Analytics · 2 min ago" tone="amber" /><Event icon={Check} title="Quota policy updated" detail="Meridian Health · 18 min ago" tone="green" /><Event icon={Zap} title="Fair scheduler enabled" detail="Platform setting · 42 min ago" tone="blue" /></div></section></div>
  </>
}
function Event({ icon: Icon, title, detail, tone }: any) { return <div className="event"><span className={`event-icon ${tone}`}><Icon size={14} /></span><div><b>{title}</b><span>{detail}</span></div><ChevronRight size={15} className="event-arrow" /></div> }
function TenantTable({ tenants, onSelect, selected }: any) { return <div className="table-scroll"><table><thead><tr><th>Company / tenant</th><th>Workload</th><th>Req / min</th><th>Quota</th><th>p95 latency</th><th>Status</th><th>Protection</th><th /></tr></thead><tbody>{tenants.map((t: any) => <tr key={t.id} className={selected === t.id ? 'row-selected' : ''} onClick={() => onSelect(t.id)}><td><div className="tenant-name"><span className="company-avatar">{t.company[0]}</span><div><b>{t.company}</b><span>{t.id}</span></div></div></td><td>{t.type}</td><td className="mono">{t.rpm}</td><td className="mono">{t.quota}</td><td>{t.latency}</td><td><Badge tone={t.tone}>{t.status}</Badge></td><td><span className={t.action === 'None' ? 'muted' : 'action-text'}>{t.action}</span></td><td><ChevronRight size={15} className="row-arrow" /></td></tr>)}</tbody></table></div> }

function PageView({ active, tenants, onNotify, onRun, running, onSelect, selected }: any) {
  const isIncidents = active.includes('Incidents'), isReports = active.includes('Reports'), isResource = active.includes('Resource'), isScheduler = active.includes('Scheduler'), isTraffic = active.includes('Traffic'), isSettings = active === 'Settings'
  if (active === 'Tenants') return <section className="panel table-panel"><div className="panel-header"><div><h2>Tenant directory</h2><p>10 companies · 24 tenants · simulated environment</p></div><button className="primary-button" onClick={() => onNotify('Create tenant flow opened')}><Users size={15} /> Add tenant</button></div><TenantTable tenants={tenants} onSelect={onSelect} selected={selected} /></section>
  return <div className="page-view"><div className="metric-grid"><Metric label={isResource ? 'CPU utilization' : isScheduler ? 'Active workers' : isTraffic ? 'Traffic received' : isIncidents ? 'Open incidents' : isReports ? 'Experiments run' : 'API endpoint' } value={isResource ? '53%' : isScheduler ? '8 / 12' : isTraffic ? '48,294' : isIncidents ? '1' : isReports ? '14' : 'Healthy'} change="Live in demo mode" icon={isResource ? Cpu : isScheduler ? Server : isTraffic ? Network : isIncidents ? AlertTriangle : isReports ? BarChart3 : Settings} /><Metric label={isResource ? 'Memory utilization' : isScheduler ? 'Queue depth' : isTraffic ? 'Rejected requests' : isIncidents ? 'Affected tenants' : isReports ? 'Avg. improvement' : 'API base URL'} value={isResource ? '61%' : isScheduler ? '26 jobs' : isTraffic ? '510' : isIncidents ? '3' : isReports ? '18.4%' : 'localhost:8000'} change="Within expected range" icon={Gauge} tone="violet" /></div><section className="panel feature-panel"><div className="feature-icon"><Sparkles size={20} /></div><div><h2>{isIncidents ? 'Impact-aware incident analysis' : isReports ? 'Controlled experiments' : isScheduler ? 'Fair workload scheduling' : isResource ? 'Resource pressure timeline' : isTraffic ? 'Tenant traffic & quota policies' : isSettings ? 'Platform configuration' : `${active} workspace`}</h2><p>{isIncidents ? 'Review evidence, alternative explanations, and bounded actions before changing tenant policy. Rule-based scores are heuristics, not calibrated probabilities.' : isReports ? 'Run repeatable scenarios and compare measured outcomes. Seeded reports are clearly marked simulated; live runs record actual observations.' : isScheduler ? 'Round Robin selects eligible jobs from separate per-tenant queues, skipping empty or ineligible queues to prevent monopolization.' : isResource ? 'Measurements are machine-level in this prototype. Tenant attribution only appears when a job was separately measured.' : isTraffic ? 'Sliding-window quotas are enforced before expensive work. Rejected requests return HTTP 429 with a retry hint.' : 'This workspace is connected to the local demo service. Changes are reversible and clearly recorded.'}</p><div className="feature-actions"><button className="primary-button" onClick={onRun} disabled={running}>{running ? <><RefreshCw size={15} className="spin" /> Running...</> : <><Play size={15} /> {isReports ? 'Run scenario' : 'Start simulation'}</>}</button><button className="secondary-button" onClick={() => onNotify('Configuration saved successfully')}><Settings size={15} /> Configure</button></div></div></section><section className="panel chart-panel"><div className="panel-header"><div><h2>{isScheduler ? 'Scheduling decisions' : isResource ? 'Resource trend' : isTraffic ? 'Traffic trend' : isReports ? 'Before / after comparison' : 'Activity timeline'}</h2><p>Simulated measurements · {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</p></div><button className="panel-action" onClick={() => onNotify('Export prepared')}>Export <ChevronRight size={14} /></button></div><div className="chart-wrap large"><ResponsiveContainer width="100%" height={280}><AreaChart data={resource}><CartesianGrid vertical={false} stroke="#e8edf3" /><XAxis dataKey="time" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#8a96a6' }} /><YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#8a96a6' }} /><Tooltip /><Area type="monotone" dataKey="cpu" stroke="#2563eb" fill="#2563eb" fillOpacity={0.1} strokeWidth={2} /><Area type="monotone" dataKey="queue" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.08} strokeWidth={2} /></AreaChart></ResponsiveContainer></div></section></div>
}

export function CopyButton({ value }: { value: string }) { return <button className="copy-button" onClick={() => navigator.clipboard?.writeText(value)} aria-label="Copy ID"><Copy size={13} /></button> }
