'use client'

import React, { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowUpDown,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Filter,
  Info,
  RefreshCw,
  Search,
  Shield,
  Zap,
} from 'lucide-react'
import { fetchApi } from '@/lib/api'

export interface SharedTenantItem {
  tenant_id: string
  tenant_name: string
  company_name: string
  company_id: string
  tenant_status: string
  time_window: string
  requests_received: number
  requests_accepted: number
  requests_processed?: number
  requests_rejected: number
  requests_throttled?: number
  configured_rate_limit_rpm: number
  current_request_rate_rpm: number
  current_allocation_pct: number
  min_service_guarantee_rpm: number
  max_allocation_limit_rpm: number
  priority: number
  borrow_allowed: boolean
  avg_latency_ms: number
  p95_latency_ms: number
  has_sufficient_latency_samples: boolean
  cpu_percent?: number | null
  memory_percent?: number | null
  infrastructure_status: string
  policy_adherence_status: string
  policy_adherence_color: string
  associated_incident_id?: number | null
  associated_incident_title?: string | null
  is_impacted_by_incident: boolean
  data_source_label: string

  // Extended Fairness Transparency Fields
  current_resource_usage?: string
  resource_unit?: string
  configured_max_allocation?: string
  min_service_guarantee?: string
  min_cpu_pct?: number
  current_assigned_allocation?: string
  borrowed_capacity?: string
  borrowed_units?: number
  remaining_pool_capacity?: string
  request_rate_display?: string
  rate_limit_exceeded?: boolean
  allocation_exceeded?: boolean
  avg_latency_display?: string
  p95_latency_display?: string
  fairness_status?: string
  fairness_status_details?: string
  fairness_status_color?: string
  protection_applied?: boolean
  protection_action_display?: string
  affected_tenants_summary?: string
}

interface SharedResourceTableProps {
  onSelectIncident?: (incidentId: number) => void
  readOnly?: boolean
}

export default function SharedResourceTable({
  onSelectIncident,
  readOnly = false,
}: SharedResourceTableProps) {
  const [data, setData] = useState<SharedTenantItem[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [policyFilter, setPolicyFilter] = useState('all')
  const [sortField, setSortField] = useState<keyof SharedTenantItem>('company_name')
  const [sortAsc, setSortAsc] = useState(true)
  const [selectedTenant, setSelectedTenant] = useState<SharedTenantItem | null>(null)
  const [dataSource, setDataSource] = useState('SIMULATION MODE')
  const [privacyNotice, setPrivacyNotice] = useState('')

  const loadData = () => {
    setLoading(true)
    fetchApi<{
      tenants: SharedTenantItem[]
      data_source_label: string
      privacy_notice: string
    }>('/shared-resource-overview')
      .then((res) => {
        setData(res.tenants || [])
        setDataSource(res.data_source_label || 'SIMULATION MODE')
        setPrivacyNotice(res.privacy_notice || '')
      })
      .catch(() => {
        setDataSource('SIMULATION MODE')
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadData()
  }, [])

  const filteredData = useMemo(() => {
    return data
      .filter((item) => {
        const matchesSearch =
          item.tenant_name.toLowerCase().includes(search.toLowerCase()) ||
          item.company_name.toLowerCase().includes(search.toLowerCase()) ||
          item.tenant_id.toLowerCase().includes(search.toLowerCase())
        const itemStatus = item.fairness_status || item.policy_adherence_status || ''
        const matchesStatus =
          statusFilter === 'all' ||
          item.tenant_status.toLowerCase() === statusFilter.toLowerCase() ||
          itemStatus.toLowerCase().includes(statusFilter.toLowerCase())
        const matchesPolicy =
          policyFilter === 'all' ||
          itemStatus.toLowerCase().includes(policyFilter.toLowerCase())
        return matchesSearch && matchesStatus && matchesPolicy
      })
      .sort((a, b) => {
        const valA = a[sortField] ?? ''
        const valB = b[sortField] ?? ''
        if (typeof valA === 'number' && typeof valB === 'number') {
          return sortAsc ? valA - valB : valB - valA
        }
        return sortAsc
          ? String(valA).localeCompare(String(valB))
          : String(valB).localeCompare(String(valA))
      })
  }, [data, search, statusFilter, policyFilter, sortField, sortAsc])

  const handleSort = (field: keyof SharedTenantItem) => {
    if (sortField === field) {
      setSortAsc(!sortAsc)
    } else {
      setSortField(field)
      setSortAsc(true)
    }
  }

  const getStatusBadge = (item: SharedTenantItem) => {
    const statusText = item.fairness_status || item.policy_adherence_status || 'Within Allocation'
    const color = item.fairness_status_color || item.policy_adherence_color || 'green'

    let badgeClass = 'badge-green'
    if (color === 'red') badgeClass = 'badge-red'
    else if (color === 'amber') badgeClass = 'badge-amber'
    else if (color === 'blue') badgeClass = 'badge-blue'
    else if (color === 'slate') badgeClass = 'badge-slate'

    return (
      <span className={`badge ${badgeClass}`} title={item.fairness_status_details || statusText}>
        <span className="badge-dot" />
        {statusText}
      </span>
    )
  }

  return (
    <div className="shared-table-container">
      {/* Table Toolbar */}
      <div className="shared-table-header">
        <div>
          <div className="shared-eyebrow">
            <span>SHARED PLATFORM RESOURCE TRANSPARENCY</span>
            <span className="shared-dot" />
            <span className={`badge ${dataSource === 'LIVE APPLICATION DATA' ? 'badge-green' : 'badge-amber'}`}>
              <span className="badge-dot" />
              {dataSource}
            </span>
          </div>
          <h2 className="shared-title">Tenant-Level Operational Overview</h2>
          <p className="shared-subtitle">
            Cross-tenant transparency for shared capacity, rate limits, latency, SLA guarantees, and fairness enforcement.
          </p>
        </div>

        <button className="secondary-button" onClick={loadData} disabled={loading}>
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {privacyNotice && (
        <div className="shared-privacy-notice">
          <Info size={15} className="shared-info-icon" />
          <span>{privacyNotice}</span>
        </div>
      )}

      {/* Filter bar */}
      <div className="shared-controls">
        <div className="shared-search-wrap">
          <Search size={14} className="shared-search-icon" />
          <input
            type="text"
            placeholder="Filter by company, tenant name, or ID…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="shared-search-input"
          />
        </div>

        <div className="shared-filter-group">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="shared-select"
          >
            <option value="all">All Fairness Statuses</option>
            <option value="within">Within Allocation</option>
            <option value="borrowing">Borrowing Permitted Capacity</option>
            <option value="exceeds">Exceeds Configured Allocation</option>
            <option value="risk">Another Tenant Guarantee at Risk</option>
            <option value="protection">Protection Applied</option>
            <option value="insufficient">Insufficient Data</option>
          </select>
        </div>
      </div>

      {/* Main Table */}
      <div className="shared-table-wrap">
        <table className="shared-table">
          <thead>
            <tr>
              <th onClick={() => handleSort('company_name')} className="cursor-pointer">
                Tenant / Company <ArrowUpDown size={11} className="inline ml-1 opacity-50" />
              </th>
              <th>Fairness Status</th>
              <th onClick={() => handleSort('requests_received')} className="cursor-pointer text-right">
                Received <ArrowUpDown size={11} className="inline ml-1 opacity-50" />
              </th>
              <th className="text-right">Accepted</th>
              <th className="text-right">Throttled</th>
              <th className="text-right">Current Rate</th>
              <th onClick={() => handleSort('configured_rate_limit_rpm')} className="cursor-pointer text-right">
                Configured Quota <ArrowUpDown size={11} className="inline ml-1 opacity-50" />
              </th>
              <th className="text-right">Min SLA Guarantee</th>
              <th className="text-right">Borrowed</th>
              <th className="text-right">Avg Latency</th>
              <th className="text-right">p95 Latency</th>
              <th>CPU / Memory</th>
              <th>Impact / Incident</th>
              <th className="text-center">Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredData.length === 0 ? (
              <tr>
                <td colSpan={14} className="shared-empty-cell">
                  {loading ? 'Loading operational usage records…' : 'No requests recorded in this time window.'}
                </td>
              </tr>
            ) : (
              filteredData.map((item) => {
                const isSelected = selectedTenant?.tenant_id === item.tenant_id
                return (
                  <tr
                    key={item.tenant_id}
                    className={isSelected ? 'shared-row-selected' : ''}
                    onClick={() => setSelectedTenant(item)}
                  >
                    <td>
                      <strong>{item.tenant_name}</strong>
                      <div className="shared-sub-text">{item.company_name}</div>
                    </td>
                    <td>{getStatusBadge(item)}</td>
                    <td className="mono text-right">{item.requests_received.toLocaleString()}</td>
                    <td className="mono text-right" style={{ color: '#16a34a' }}>
                      {item.requests_accepted.toLocaleString()}
                    </td>
                    <td
                      className="mono text-right"
                      style={{ color: item.requests_rejected > 0 ? '#dc2626' : 'inherit' }}
                    >
                      {item.requests_rejected.toLocaleString()}
                    </td>
                    <td className="mono text-right font-medium">
                      {item.requests_received > 0 ? `${item.current_request_rate_rpm} rpm` : '—'}
                    </td>
                    <td className="mono text-right">{item.configured_rate_limit_rpm} rpm</td>
                    <td className="mono text-right" title="Contracted Minimum SLA Guarantee">
                      {item.min_service_guarantee_rpm} rpm
                    </td>
                    <td className="mono text-right">
                      {item.borrowed_units && item.borrowed_units > 0 ? (
                        <span style={{ color: '#d97706', fontWeight: 600 }}>+{item.borrowed_units} rpm</span>
                      ) : (
                        <span className="text-slate-400">0</span>
                      )}
                    </td>
                    <td className="mono text-right">
                      {item.has_sufficient_latency_samples && item.avg_latency_ms > 0 ? `${item.avg_latency_ms} ms` : '—'}
                    </td>
                    <td className="mono text-right">
                      {item.has_sufficient_latency_samples && item.p95_latency_ms > 0 ? `${item.p95_latency_ms} ms` : '—'}
                    </td>
                    <td>
                      {item.cpu_percent !== null && item.cpu_percent !== undefined ? (
                        <span className="mono text-xs">{item.cpu_percent}% / {item.memory_percent}%</span>
                      ) : (
                        <span className="text-xs text-slate-400">Not connected</span>
                      )}
                    </td>
                    <td>
                      {item.associated_incident_id ? (
                        <button
                          className="incident-link-btn"
                          onClick={(e) => {
                            e.stopPropagation()
                            if (onSelectIncident) onSelectIncident(item.associated_incident_id!)
                          }}
                        >
                          <AlertTriangle size={12} />
                          <span>Receipt #{item.associated_incident_id}</span>
                        </button>
                      ) : (
                        <span className="text-xs text-slate-400">None</span>
                      )}
                    </td>
                    <td className="text-center">
                      <button
                        className="shared-inspect-btn"
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedTenant(item)
                        }}
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Tenant Detail Drawer / Modal — Required Three-Way Comparison (Section 3) */}
      {selectedTenant && (
        <div className="tenant-detail-card">
          <div className="tenant-detail-header">
            <div>
              <div className="flex items-center gap-2">
                <h3>{selectedTenant.tenant_name} — Resource Fairness Breakdown</h3>
                {getStatusBadge(selectedTenant)}
              </div>
              <p>{selectedTenant.company_name} · Tenant ID: <code>{selectedTenant.tenant_id}</code></p>
            </div>
            <button
              className="tenant-detail-close"
              onClick={() => setSelectedTenant(null)}
            >
              ×
            </button>
          </div>

          {/* Three-Way Comparison: Actual Usage vs Configured Allocation vs Minimum Guarantee */}
          <div className="tenant-comparison-section">
            <h4 className="tenant-section-heading">Fairness Envelope Comparison</h4>
            <div className="tenant-detail-grid">
              <div className="tenant-detail-col">
                <span>1. Actual Measured Usage</span>
                <strong>{selectedTenant.requests_received > 0 ? `${selectedTenant.current_request_rate_rpm} rpm` : '— (No traffic)'}</strong>
                <em>{selectedTenant.requests_accepted} accepted · {selectedTenant.requests_rejected} throttled</em>
              </div>
              <div className="tenant-detail-col">
                <span>2. Configured Allocation Cap</span>
                <strong>{selectedTenant.configured_rate_limit_rpm} rpm</strong>
                <em>Hard cap · Priority {selectedTenant.priority}/10</em>
              </div>
              <div className="tenant-detail-col">
                <span>3. Minimum Service Guarantee</span>
                <strong>{selectedTenant.min_service_guarantee_rpm} rpm</strong>
                <em>Guaranteed SLA baseline floor</em>
              </div>
            </div>

            {/* Delta & Policy Enforcement Interpretation */}
            <div className="tenant-delta-banner">
              <strong>Evaluation:</strong>{' '}
              {selectedTenant.requests_received === 0 ? (
                <span>No requests observed in this measurement window. Awaiting live traffic.</span>
              ) : selectedTenant.current_request_rate_rpm > selectedTenant.configured_rate_limit_rpm ? (
                selectedTenant.borrow_allowed ? (
                  <span>
                    Exceeds base allocation by{' '}
                    <b style={{ color: '#d97706' }}>
                      {(selectedTenant.current_request_rate_rpm - selectedTenant.configured_rate_limit_rpm).toFixed(1)} rpm
                    </b>
                    . Borrowing is <b>permitted</b> from idle shared pool.
                  </span>
                ) : (
                  <span>
                    Exceeds base allocation by{' '}
                    <b style={{ color: '#dc2626' }}>
                      {(selectedTenant.current_request_rate_rpm - selectedTenant.configured_rate_limit_rpm).toFixed(1)} rpm
                    </b>
                    . Borrowing is <b>disabled</b> for this tenant. Rate limiting / throttling enforced.
                  </span>
                )
              ) : selectedTenant.current_request_rate_rpm >= selectedTenant.min_service_guarantee_rpm ? (
                <span>
                  Within permitted allocation envelope ({selectedTenant.current_request_rate_rpm} rpm / {selectedTenant.configured_rate_limit_rpm} rpm). Minimum guarantee satisfied.
                </span>
              ) : (
                <span>
                  Operating below minimum guarantee ceiling ({selectedTenant.current_request_rate_rpm} rpm &lt; {selectedTenant.min_service_guarantee_rpm} rpm SLA floor). Spare capacity available for borrowing.
                </span>
              )}
            </div>
          </div>

          {/* Underlying Conditions & Borrowing Rules */}
          <div className="tenant-detail-subgrid">
            <div className="tenant-subcol">
              <span className="subcol-label">Borrowing Rules</span>
              <div>
                <strong>{selectedTenant.borrow_allowed ? 'Eligible to Borrow' : 'Strict Quota Cap'}</strong>
                <p className="text-xs text-slate-500">
                  {selectedTenant.borrow_allowed
                    ? 'Permitted to borrow spare capacity from idle tenants up to dynamic safety cap.'
                    : 'Hard ceiling strictly enforced. Excess requests dropped immediately.'}
                </p>
              </div>
            </div>
            <div className="tenant-subcol">
              <span className="subcol-label">Protection Action</span>
              <div>
                <strong>{selectedTenant.protection_action_display || 'None active'}</strong>
                <p className="text-xs text-slate-500">
                  {selectedTenant.protection_applied
                    ? 'Automated rate limit / concurrency bounding applied by policy engine.'
                    : 'No protective restriction applied.'}
                </p>
              </div>
            </div>
            <div className="tenant-subcol">
              <span className="subcol-label">Condition Reason</span>
              <div>
                <p className="text-xs text-slate-700 font-medium">
                  {selectedTenant.fairness_status_details || 'Operating within defined policy rules.'}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .shared-table-container {
          background: #ffffff;
          border: 1px solid #e2e8f0;
          border-radius: 12px;
          padding: 20px;
          margin-bottom: 24px;
          font-family: 'Inter', system-ui, sans-serif;
        }
        .shared-table-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          margin-bottom: 16px;
        }
        .shared-eyebrow {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 11px;
          font-weight: 700;
          color: #64748b;
          letter-spacing: 0.5px;
        }
        .shared-dot {
          width: 4px;
          height: 4px;
          border-radius: 50%;
          background: #cbd5e1;
        }
        .shared-title {
          font-family: 'DM Serif Display', Georgia, serif;
          font-size: 22px;
          font-weight: 400;
          margin: 4px 0 2px;
          color: #0f172a;
        }
        .shared-subtitle {
          margin: 0;
          font-size: 12px;
          color: #64748b;
        }
        .shared-privacy-notice {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 14px;
          background: #f8fafc;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          font-size: 11px;
          color: #475569;
          margin-bottom: 16px;
          line-height: 1.5;
        }
        .shared-info-icon {
          color: #2563eb;
          flex-shrink: 0;
        }
        .shared-controls {
          display: flex;
          gap: 12px;
          margin-bottom: 14px;
          flex-wrap: wrap;
        }
        .shared-search-wrap {
          flex: 1;
          min-width: 240px;
          position: relative;
        }
        .shared-search-icon {
          position: absolute;
          left: 10px;
          top: 50%;
          transform: translateY(-50%);
          color: #94a3b8;
        }
        .shared-search-input {
          width: 100%;
          padding: 9px 12px 9px 34px;
          border: 1px solid #cbd5e1;
          border-radius: 7px;
          font-size: 13px;
          outline: none;
          color: #0f172a;
        }
        .shared-search-input:focus {
          border-color: #2563eb;
        }
        .shared-filter-group {
          display: flex;
          gap: 8px;
        }
        .shared-select {
          padding: 9px 12px;
          border: 1px solid #cbd5e1;
          border-radius: 7px;
          font-size: 13px;
          background: #fff;
          color: #1e293b;
          font-weight: 500;
          outline: none;
        }
        .shared-table-wrap {
          overflow-x: auto;
          border: 1px solid var(--line);
          border-radius: 8px;
        }
        .shared-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
          min-width: 1240px;
        }
        .shared-table th {
          background: #f8fafc;
          padding: 11px 12px;
          color: #334155;
          font-weight: 600;
          font-size: 13px;
          border-bottom: 2px solid var(--line);
          white-space: nowrap;
          text-align: left;
        }
        .shared-table td {
          padding: 12px 12px;
          border-bottom: 1px solid #f1f5f9;
          white-space: nowrap;
          color: #1e293b;
          font-size: 13px;
        }
        .shared-table tr:hover {
          background: #f8fafc;
        }
        .shared-row-selected {
          background: #eff6ff !important;
        }
        .shared-sub-text {
          font-size: 12px;
          color: #475569;
          margin-top: 2px;
        }
        .priority-pill {
          background: #ede9fe;
          color: #5b21b6;
          padding: 2px 7px;
          border-radius: 4px;
          font-weight: 700;
          font-size: 12px;
        }
        .incident-link-btn {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          background: #fef3c7;
          color: #92400e;
          border: 1px solid #fde68a;
          padding: 4px 8px;
          border-radius: 5px;
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
        }
        .incident-link-btn:hover {
          background: #fde68a;
        }
        .shared-inspect-btn {
          background: #f1f5f9;
          border: 1px solid #cbd5e1;
          padding: 5px 10px;
          border-radius: 6px;
          font-size: 12px;
          font-weight: 600;
          color: #1e293b;
          cursor: pointer;
        }
        .shared-inspect-btn:hover {
          background: #e2e8f0;
          color: #0f172a;
        }
        .shared-empty-cell {
          text-align: center;
          padding: 40px;
          color: #64748b;
          font-size: 14px;
        }
        .tenant-detail-card {
          margin-top: 16px;
          padding: 18px 22px;
          background: #f8fafc;
          border: 1px solid #cbd5e1;
          border-radius: 10px;
        }
        .tenant-detail-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 16px;
        }
        .tenant-detail-header h3 {
          font-family: 'DM Serif Display', Georgia, serif;
          margin: 0;
          font-size: 19px;
          color: #0f172a;
        }
        .tenant-detail-header p {
          margin: 3px 0 0;
          font-size: 13px;
          color: #475569;
        }
        .tenant-detail-close {
          background: transparent;
          border: none;
          font-size: 22px;
          color: #64748b;
          cursor: pointer;
        }
        .tenant-comparison-section {
          background: #ffffff;
          padding: 16px;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          margin-bottom: 14px;
        }
        .tenant-section-heading {
          margin: 0 0 12px;
          font-size: 13px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          color: #334155;
        }
        .tenant-detail-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 14px;
        }
        .tenant-detail-col {
          background: #f8fafc;
          padding: 14px;
          border-radius: 7px;
          border: 1px solid #e2e8f0;
        }
        .tenant-detail-col span {
          display: block;
          font-size: 12px;
          color: #475569;
          text-transform: uppercase;
          font-weight: 600;
        }
        .tenant-detail-col strong {
          display: block;
          font-size: 16px;
          margin: 5px 0 2px;
          color: #0f172a;
        }
        .tenant-detail-col em {
          font-style: normal;
          font-size: 12px;
          color: #475569;
        }
        .tenant-delta-banner {
          margin-top: 14px;
          padding: 12px 14px;
          background: #eff6ff;
          border: 1px solid #bfdbfe;
          border-radius: 7px;
          font-size: 13px;
          color: #1e3a8a;
          line-height: 1.5;
        }
        .tenant-detail-subgrid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 14px;
        }
        .tenant-subcol {
          background: #ffffff;
          padding: 14px;
          border-radius: 7px;
          border: 1px solid #e2e8f0;
        }
        .subcol-label {
          display: block;
          font-size: 12px;
          color: #475569;
          text-transform: uppercase;
          margin-bottom: 4px;
          font-weight: 600;
        }
        .badge-slate {
          background: #f1f5f9;
          color: #334155;
          border: 1px solid #cbd5e1;
        }
        .badge-blue {
          background: #eff6ff;
          color: #1d4ed8;
          border: 1px solid #bfdbfe;
        }
        .mono {
          font-variant-numeric: tabular-nums;
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        }
      `}</style>
    </div>
  )
}
