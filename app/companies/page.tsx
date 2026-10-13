"use client"

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
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

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const router = useRouter();

  useEffect(() => {
    const fetchCompanies = async () => {
      try {
        const res = await fetch('/api/companies', {
          headers: { Authorization: 'Bearer fg_admin_platform_demo_key' }
        });
        if (!res.ok) throw new Error('Failed to load companies');
        const data = await res.json();
        setCompanies(data);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchCompanies();
  }, []);

  if (loading) return <div className="loader">Loading companies…</div>;
  if (error) return <div className="error">{error}</div>;

  const totals = companies.reduce(
    (a, c) => ({
      rpm: a.rpm + Number(c.total_requests_per_minute || 0),
      rejected: a.rejected + Number(c.total_rejected || 0),
      accepted: a.accepted + Number(c.total_accepted || 0),
    }),
    { rpm: 0, rejected: 0, accepted: 0 }
  );

  return (
    <div className="page-view">
      <section className="company-hero panel">
        <div>
          <h2>All Companies</h2>
          <p>{companies.length} companies registered</p>
        </div>
      </section>
      <div className="metric-grid">
        <Metric label="Requests received" value={`${totals.rpm.toLocaleString()} / min`} icon={Activity} />
        <Metric label="Accepted requests" value={totals.accepted.toLocaleString()} tone="green" icon={Check} />
        <Metric label="Rejected requests" value={totals.rejected.toLocaleString()} tone="amber" icon={AlertTriangle} />
        <Metric label="Request quota" value="2,500 / min" tone="violet" icon={Gauge} />
      </div>
      <section className="panel table-panel">
        <div className="panel-header"><h2>Companies</h2></div>
        <div className="table-scroll">
          <table className="dense-table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Company ID</th>
                <th>Tenants</th>
                <th>Requests / min</th>
                <th>Quota</th>
                <th>Incidents</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {companies.map((c) => (
                <tr key={c.id} onClick={() => router.push(`/companies/${c.id}`)} className="row-pointer">
                  <td>{c.name}</td>
                  <td className="mono">{c.id}</td>
                  <td>{c.tenant_count}</td>
                  <td className="mono">{c.total_requests_per_minute ?? 0}</td>
                  <td className="mono">2,500</td>
                  <td>{c.active_incidents ?? 0}</td>
                  <td><Badge tone={c.status === 'active' ? 'green' : 'red'}>{c.status}</Badge></td>
                  <td><ChevronRight size={15} className="row-arrow" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
