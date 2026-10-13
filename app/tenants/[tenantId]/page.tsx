"use client"

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';

import {
  Activity,
  AlertTriangle,
  Check,
  Clock3,
  Cpu,
  Gauge,
  Shield,
  ChevronRight,
} from 'lucide-react';

function Badge({ children, tone = 'slate' }: { children: React.ReactNode; tone?: string }) {
  return <span className={`badge badge-${tone}`}><span className="badge-dot" />{children}</span>;
}

function Metric({ label, value, icon: Icon, tone = 'blue' }: any) {
  return (
    <div className="metric-card">
      <div className="metric-head">
        <span>{label}</span>
        <span className={`metric-icon ${tone}`}><Icon size={15} /></span>
      </div>
      <strong>{value}</strong>
    </div>
  );
}

export default function TenantDetailsPage() {
  const params = useParams();
  const tenantId = params?.tenantId as string;
  const router = useRouter();

  const [tenant, setTenant] = useState<any>(null);
  const [traffic, setTraffic] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [resources, setResources] = useState<any[]>([]);
  const [securityEvents, setSecurityEvents] = useState<any[]>([]);
  const [protectionActions, setProtectionActions] = useState<any[]>([]);
  const [incidents, setIncidents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    if (!tenantId) return;
    const fetchAll = async () => {
      try {
        const headers = { Authorization: 'Bearer fg_admin_platform_demo_key' };
        const [tRes, trRes, jRes, rRes, seRes, paRes, incRes] = await Promise.all([
          fetch(`/api/tenants/${tenantId}`, { headers }),
          fetch(`/api/tenants/${tenantId}/traffic`, { headers }),
          fetch(`/api/tenants/${tenantId}/jobs`, { headers }),
          fetch(`/api/tenants/${tenantId}/resources`, { headers }),
          fetch(`/api/tenants/${tenantId}/security-events`, { headers }),
          fetch(`/api/protection-actions?tenant_id=${tenantId}`, { headers }),
          fetch(`/api/incidents`, { headers }),
        ]);
        if (!tRes.ok) throw new Error('Failed to load tenant');
        const tenantData = await tRes.json();
        setTenant(tenantData);
        if (trRes.ok) setTraffic(await trRes.json());
        if (jRes.ok) setJobs(await jRes.json());
        if (rRes.ok) setResources(await rRes.json());
        if (seRes.ok) setSecurityEvents(await seRes.json());
        if (paRes.ok) setProtectionActions(await paRes.json());
        if (incRes.ok) {
          const allInc = await incRes.json();
          setIncidents(allInc.filter((i: any) => i.tenant_id === tenantId));
        }
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, [tenantId]);

  if (loading) return <div className="loader">Loading tenant details…</div>;
  if (error) return <div className="error">{error}</div>;
  if (!tenant) return null;

  const filteredResources = resources.filter(
    (r) => r.cpu_percent !== null || r.memory_percent !== null
  );

  return (
    <div className="page-view">
      <button className="panel-action back-action" onClick={() => router.back()}>
        <ChevronRight size={14} className="rotate-180" /> Back
      </button>

      {/* Tenant overview */}
      <section className="company-hero panel">
        <div>
          <div className="eyebrow">Tenant scoped · {tenant.is_simulated ? 'simulated' : 'live'}</div>
          <h2>{tenant.tenant?.name || tenant.name}</h2>
          <p>
            Tenant ID {tenant.tenant?.id || tenant.id} · Workload {tenant.tenant?.workload_type || tenant.workload_type} ·{' '}
            <Badge tone={(tenant.tenant?.status || tenant.status) === 'Protected' ? 'green' : (tenant.tenant?.status || tenant.status) === 'Throttled' ? 'amber' : 'slate'}>
              {tenant.tenant?.status || tenant.status}
            </Badge>
          </p>
        </div>
        <Badge tone="blue">Company {tenant.tenant?.company_name || tenant.company_name}</Badge>
      </section>

      {/* Metrics grid */}
      <div className="metric-grid">
        <Metric label="Requests per minute" value={`${tenant.requests_per_minute?.toLocaleString() || 0} rpm`} icon={Activity} />
        <Metric label="Accepted" value={tenant.accepted_count?.toLocaleString() || 0} tone="green" icon={Check} />
        <Metric label="Rejected" value={tenant.rejected_count?.toLocaleString() || 0} tone="amber" icon={AlertTriangle} />
        <Metric label="Avg latency" value={`${tenant.avg_latency_ms?.toFixed(1) || 0} ms`} icon={Clock3} />
        <Metric label="Quota" value={`${tenant.quota?.requests_per_minute ?? 500} rpm / ${tenant.quota?.max_concurrency ?? 25} conc`} tone="violet" icon={Gauge} />
        <Metric label="Utilisation" value={`${Math.round(((tenant.requests_per_minute || 0) / (tenant.quota?.requests_per_minute || 500)) * 100)}%`} tone="blue" icon={Gauge} />
      </div>

      {/* Traffic chart */}
      <section className="panel chart-panel">
        <div className="panel-header"><h2>Traffic (last {traffic.length} buckets)</h2></div>
        <ul>
          {traffic.map((b, idx) => (
            <li key={b.time || idx}>{b.time}: {b.accepted} accepted / {b.rejected} rejected</li>
          ))}
        </ul>
      </section>

      {/* Jobs table */}
      <section className="panel table-panel">
        <div className="panel-header"><h2>Job history</h2></div>
        <div className="table-scroll">
          <table className="dense-table">
            <thead><tr><th>ID</th><th>Status</th><th>Created</th><th>Duration ms</th></tr></thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td>{j.id}</td>
                  <td>{j.status}</td>
                  <td>{new Date(j.created_at).toLocaleString()}</td>
                  <td>{j.duration_ms?.toFixed(0) || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Resource measurements */}
      {filteredResources.length > 0 && (
        <section className="panel table-panel">
          <div className="panel-header"><h2>Resource measurements</h2></div>
          <div className="table-scroll">
            <table className="dense-table">
              <thead><tr><th>Time</th><th>CPU %</th><th>Memory %</th><th>Queue depth</th></tr></thead>
              <tbody>
                {filteredResources.map((r) => (
                  <tr key={r.id}>
                    <td>{new Date(r.timestamp).toLocaleTimeString()}</td>
                    <td>{r.cpu_percent ?? '-'}</td>
                    <td>{r.memory_percent ?? '-'}</td>
                    <td>{r.queue_depth ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Security events */}
      {securityEvents.length > 0 && (
        <section className="panel table-panel">
          <div className="panel-header"><h2>Security events</h2></div>
          <div className="table-scroll">
            <table className="dense-table">
              <thead><tr><th>Time</th><th>Type</th><th>Severity</th><th>Description</th></tr></thead>
              <tbody>
                {securityEvents.map((e) => (
                  <tr key={e.id}>
                    <td>{new Date(e.timestamp).toLocaleString()}</td>
                    <td>{e.event_type}</td>
                    <td>{e.severity}</td>
                    <td>{e.description ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Protection actions */}
      {protectionActions.length > 0 && (
        <section className="panel table-panel">
          <div className="panel-header"><h2>Protection actions</h2></div>
          <div className="table-scroll">
            <table className="dense-table">
              <thead><tr><th>ID</th><th>Type</th><th>Status</th><th>Applied at</th></tr></thead>
              <tbody>
                {protectionActions.map((a) => (
                  <tr key={a.id}>
                    <td>{a.id}</td>
                    <td>{a.action_type}</td>
                    <td>{a.status}</td>
                    <td>{new Date(a.applied_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Incidents */}
      {incidents.length > 0 && (
        <section className="panel table-panel">
          <div className="panel-header"><h2>Incidents affecting this tenant</h2></div>
          <div className="table-scroll">
            <table className="dense-table">
              <thead><tr><th>ID</th><th>Title</th><th>Severity</th><th>Status</th></tr></thead>
              <tbody>
                {incidents.map((i) => (
                  <tr key={i.id}>
                    <td>{i.id}</td>
                    <td>{i.title}</td>
                    <td>{i.severity}</td>
                    <td>{i.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
