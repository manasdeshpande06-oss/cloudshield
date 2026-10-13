"use client"

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Activity, Check, AlertTriangle, Gauge, ChevronRight } from 'lucide-react';

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

export default function CompanyDetailsPage() {
  const params = useParams();
  const companyId = params?.companyId as string;
  const [company, setCompany] = useState<any>(null);
  const [tenants, setTenants] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const router = useRouter();

  useEffect(() => {
    if (!companyId) return;
    const fetchData = async () => {
      try {
        const headers = { Authorization: 'Bearer fg_admin_platform_demo_key' };
        const [cRes, tRes] = await Promise.all([
          fetch(`/api/companies/${companyId}`, { headers }),
          fetch(`/api/companies/${companyId}/tenants`, { headers }),
        ]);
        if (!cRes.ok) throw new Error('Failed to load company');
        if (!tRes.ok) throw new Error('Failed to load tenants');
        const cData = await cRes.json();
        const tData = await tRes.json();
        setCompany(cData);
        setTenants(tData);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [companyId]);

  if (loading) return <div className="loader">Loading company...</div>;
  if (error) return <div className="error">{error}</div>;
  if (!company) return null;

  const totals = tenants.reduce(
    (a: any, t) => ({
      rpm: a.rpm + Number(t.requests_per_minute || 0),
      rejected: a.rejected + (t.rejected_count || 0),
      accepted: a.accepted + (t.accepted_count || 0),
    }),
    { rpm: 0, rejected: 0, accepted: 0 }
  );

  return (
    <div className="page-view">
      <button className="panel-action back-action" onClick={() => router.back()}>
        <ChevronRight size={14} className="rotate-180" /> Companies
      </button>
      <section className="company-hero panel">
        <div>
          <div className="eyebrow">Company aggregate · {company.is_simulated ? 'simulated' : 'live'}</div>
          <h2>{company.name}</h2>
          <p>
            Company ID {company.id} · Registered {new Date(company.registered_at).toLocaleDateString()} ·{' '}
            <Badge tone={company.status === 'active' ? 'green' : 'red'}>{company.status}</Badge>
          </p>
        </div>
        <Badge tone="blue">{company.tenant_count || tenants.length} tenants</Badge>
      </section>
      <div className="metric-grid">
        <Metric label="Requests received" value={`${company.total_requests_per_minute?.toLocaleString() || totals.rpm} / min`} icon={Activity} />
        <Metric label="Accepted requests" value={(company.total_accepted ?? totals.accepted).toLocaleString()} tone="green" icon={Check} />
        <Metric label="Rejected requests" value={(company.total_rejected ?? totals.rejected).toLocaleString()} tone="amber" icon={AlertTriangle} />
        <Metric label="Request quota" value="2,500 / min" tone="violet" icon={Gauge} />
      </div>
      <section className="panel table-panel">
        <div className="panel-header"><div><h2>Tenants</h2><p>Tenant‑scoped metrics</p></div></div>
        <div className="table-scroll">
          <table className="dense-table">
            <thead><tr>
              <th>Tenant</th>
              <th>Workload</th>
              <th>Status</th>
              <th>Req/min</th>
              <th>Quota / use</th>
            </tr></thead>
            <tbody>
              {tenants.map((t) => (
                <tr key={t.id} onClick={() => router.push(`/tenants/${t.id}`)} className="row-pointer">
                  <td>{t.name}</td>
                  <td>{t.workload_type}</td>
                  <td><Badge tone={t.status === 'Protected' ? 'green' : t.status === 'Throttled' ? 'amber' : 'slate'}>{t.status}</Badge></td>
                  <td className="mono">{t.requests_per_minute ?? 0}</td>
                  <td className="mono">{t.quota?.requests_per_minute ?? 500}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
