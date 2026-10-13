'use client'

import React, { useState, useEffect, useCallback } from 'react'
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock,
  Edit2,
  FileText,
  HelpCircle,
  Plus,
  RefreshCw,
  Save,
  Shield,
  ShieldAlert,
  Sliders,
  X,
  Zap,
} from 'lucide-react'
import { fetchApi } from '@/lib/api'
import FairnessReceiptModal from '@/components/fairness-receipt-modal'

interface Contract {
  id: number
  tenant_id: string
  tenant_name: string
  company_name: string
  min_cpu_pct: number
  max_cpu_pct: number
  priority: number
  min_rpm: number
  max_rpm: number
  borrow_cap_pct: number
  status: string
  guarantee_status?: string
}

export default function FairnessContractsAdmin({
  onNotify,
}: {
  onNotify?: (msg: string) => void
}) {
  const [contracts, setContracts] = useState<Contract[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<Partial<Contract>>({})
  const [saving, setSaving] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [selectedReceiptTenantId, setSelectedReceiptTenantId] = useState<string | null>(null)

  const loadContracts = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchApi<Contract[]>('/contracts')
      setContracts(data)
    } catch (err: any) {
      if (onNotify) onNotify('Failed to load contracts: ' + err.message)
    } finally {
      setLoading(false)
    }
  }, [onNotify])

  useEffect(() => {
    loadContracts()
  }, [loadContracts])

  const totalMinGuarantees = contracts.reduce((acc, c) => acc + (c.min_cpu_pct || 0), 0)
  const isOvercommitted = totalMinGuarantees > 100.0

  const handleEdit = (contract: Contract) => {
    setEditingId(contract.tenant_id)
    setForm({ ...contract })
    setValidationError(null)
  }

  const handleCancel = () => {
    setEditingId(null)
    setForm({})
    setValidationError(null)
  }

  const handleSave = async (tenantId: string) => {
    setSaving(true)
    setValidationError(null)

    // Client-side pre-validation of feasibility
    const otherMin = contracts
      .filter((c) => c.tenant_id !== tenantId)
      .reduce((sum, c) => sum + (c.min_cpu_pct || 0), 0)
    const proposedTotal = otherMin + (form.min_cpu_pct || 0)

    if (proposedTotal > 100.0) {
      setValidationError(
        `Infeasible Guarantee: Sum of minimum guarantees (${proposedTotal.toFixed(1)}%) would exceed available host capacity (100.0%). Please lower the minimum guarantee.`
      )
      setSaving(false)
      return
    }

    try {
      await fetchApi(`/contracts/${tenantId}`, {
        method: 'PUT',
        body: JSON.stringify({
          min_cpu_pct: form.min_cpu_pct,
          max_cpu_pct: form.max_cpu_pct,
          priority: form.priority,
          min_rpm: form.min_rpm,
          max_rpm: form.max_rpm,
          borrow_cap_pct: form.borrow_cap_pct,
        }),
      })
      if (onNotify) onNotify(`Fairness contract updated for tenant ${tenantId}!`)
      setEditingId(null)
      loadContracts()
    } catch (err: any) {
      setValidationError(err?.message || 'Failed to update contract')
    } finally {
      setSaving(false)
    }
  }

  const getStatusBadge = (status?: string) => {
    switch (status) {
      case 'Satisfied':
        return { color: '#15803d', bg: '#dcfce7', icon: CheckCircle2 }
      case 'At risk':
        return { color: '#b45309', bg: '#fef3c7', icon: AlertTriangle }
      case 'Not satisfied':
        return { color: '#b91c1c', bg: '#fee2e2', icon: ShieldAlert }
      default:
        return { color: '#475569', bg: '#f1f5f9', icon: Clock }
    }
  }

  return (
    <div className="page-view" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Capacity & Feasibility Overview */}
      <section className="panel" style={{ padding: '18px 22px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: 18, margin: '0 0 4px' }}>
              Multi-Tenant Fairness Contracts & Service Guarantees
            </h2>
            <p style={{ margin: 0, fontSize: 12, color: 'var(--muted-ink)' }}>
              Configure enforceable minimum guarantees, priority weights, and borrowing caps.
            </p>
          </div>
          <button
            onClick={loadContracts}
            className="secondary-button"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
          </button>
        </div>

        {/* Feasibility Alert */}
        <div style={{
          marginTop: 16,
          padding: '12px 16px',
          borderRadius: 8,
          border: `1px solid ${isOvercommitted ? '#fca5a5' : '#bbf7d0'}`,
          background: isOvercommitted ? '#fef2f2' : '#f0fdf4',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          flexWrap: 'wrap'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {isOvercommitted ? (
              <ShieldAlert size={20} style={{ color: '#dc2626' }} />
            ) : (
              <CheckCircle2 size={20} style={{ color: '#16a34a' }} />
            )}
            <div>
              <strong style={{ fontSize: 13, color: isOvercommitted ? '#991b1b' : '#166534' }}>
                {isOvercommitted ? 'Capacity Infeasibility Warning' : 'Simultaneous Guarantees Feasible'}
              </strong>
              <div style={{ fontSize: 11, color: isOvercommitted ? '#b91c1c' : '#15803d' }}>
                Total Allocated Minimum Guarantees: <strong>{totalMinGuarantees.toFixed(1)}%</strong> / 100.0% available capacity.
                {isOvercommitted ? ' Contract minimums exceed total system processing capacity.' : ' All tenant guarantees are mathematically satisfiable simultaneously.'}
              </div>
            </div>
          </div>
          <div style={{
            fontSize: 12,
            fontWeight: 700,
            color: isOvercommitted ? '#dc2626' : '#16a34a',
            padding: '4px 10px',
            background: 'rgba(255,255,255,0.7)',
            borderRadius: 6
          }}>
            {totalMinGuarantees.toFixed(1)}% / 100%
          </div>
        </div>
      </section>

      {validationError && (
        <div style={{
          padding: '12px 16px',
          borderRadius: 8,
          background: '#fef2f2',
          border: '1px solid #fecaca',
          color: '#b91c1c',
          fontSize: 12,
          display: 'flex',
          alignItems: 'center',
          gap: 8
        }}>
          <AlertTriangle size={16} />
          {validationError}
        </div>
      )}

      {/* Contracts Table */}
      <section className="panel table-panel">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Tenant & Company</th>
                <th>Guarantee Status</th>
                <th>Min Guarantee (CPU %)</th>
                <th>Max Cap (CPU %)</th>
                <th>Priority (1–10)</th>
                <th>RPM Bounds (Min / Max)</th>
                <th>Borrow Cap %</th>
                <th>Contract Status</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {contracts.map((c) => {
                const isEditing = editingId === c.tenant_id
                const statusInfo = getStatusBadge(c.guarantee_status)
                const StatusIcon = statusInfo.icon

                if (isEditing) {
                  return (
                    <tr key={c.tenant_id} style={{ background: '#f8fafc' }}>
                      <td>
                        <strong>{c.tenant_name}</strong>
                        <div style={{ fontSize: 10, color: 'var(--muted-ink)' }}>{c.company_name}</div>
                      </td>
                      <td>
                        <span style={{ fontSize: 11, color: 'var(--muted-ink)' }}>Editing…</span>
                      </td>
                      <td>
                        <input
                          type="number"
                          min="0"
                          max="80"
                          step="1"
                          value={form.min_cpu_pct ?? 0}
                          onChange={(e) => setForm({ ...form, min_cpu_pct: parseFloat(e.target.value) || 0 })}
                          style={{ width: 70, padding: '4px 6px', fontSize: 12, borderRadius: 4, border: '1px solid var(--border)' }}
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          min="5"
                          max="80"
                          step="1"
                          value={form.max_cpu_pct ?? 50}
                          onChange={(e) => setForm({ ...form, max_cpu_pct: parseFloat(e.target.value) || 50 })}
                          style={{ width: 70, padding: '4px 6px', fontSize: 12, borderRadius: 4, border: '1px solid var(--border)' }}
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          min="1"
                          max="10"
                          value={form.priority ?? 5}
                          onChange={(e) => setForm({ ...form, priority: parseInt(e.target.value) || 5 })}
                          style={{ width: 55, padding: '4px 6px', fontSize: 12, borderRadius: 4, border: '1px solid var(--border)' }}
                        />
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 4 }}>
                          <input
                            type="number"
                            value={form.min_rpm ?? 0}
                            placeholder="Min"
                            onChange={(e) => setForm({ ...form, min_rpm: parseInt(e.target.value) || 0 })}
                            style={{ width: 60, padding: '4px 4px', fontSize: 11, borderRadius: 4, border: '1px solid var(--border)' }}
                          />
                          <input
                            type="number"
                            value={form.max_rpm ?? 1000}
                            placeholder="Max"
                            onChange={(e) => setForm({ ...form, max_rpm: parseInt(e.target.value) || 1000 })}
                            style={{ width: 60, padding: '4px 4px', fontSize: 11, borderRadius: 4, border: '1px solid var(--border)' }}
                          />
                        </div>
                      </td>
                      <td>
                        <input
                          type="number"
                          min="0"
                          max="50"
                          value={form.borrow_cap_pct ?? 20}
                          onChange={(e) => setForm({ ...form, borrow_cap_pct: parseFloat(e.target.value) || 0 })}
                          style={{ width: 60, padding: '4px 6px', fontSize: 12, borderRadius: 4, border: '1px solid var(--border)' }}
                        />
                      </td>
                      <td>
                        <span className="badge badge-blue">Saving</span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', gap: 6 }}>
                          <button
                            onClick={() => handleSave(c.tenant_id)}
                            disabled={saving}
                            className="primary-button"
                            style={{ padding: '4px 8px', fontSize: 11, height: 26 }}
                          >
                            <Save size={12} /> Save
                          </button>
                          <button
                            onClick={handleCancel}
                            className="secondary-button"
                            style={{ padding: '4px 8px', fontSize: 11, height: 26 }}
                          >
                            <X size={12} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                }

                return (
                  <tr key={c.tenant_id}>
                    <td>
                      <div style={{ fontWeight: 600 }}>{c.tenant_name}</div>
                      <div style={{ fontSize: 10, color: 'var(--muted-ink)' }}>{c.company_name} · {c.tenant_id}</div>
                    </td>
                    <td>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        padding: '3px 8px',
                        borderRadius: 5,
                        fontSize: 11,
                        fontWeight: 650,
                        background: statusInfo.bg,
                        color: statusInfo.color
                      }}>
                        <StatusIcon size={12} />
                        {c.guarantee_status || 'Satisfied'}
                      </span>
                    </td>
                    <td className="mono">
                      <strong>{c.min_cpu_pct}%</strong>
                    </td>
                    <td className="mono">{c.max_cpu_pct}%</td>
                    <td className="mono">
                      <span style={{
                        background: c.priority >= 8 ? '#fef3c7' : '#f1f5f9',
                        color: c.priority >= 8 ? '#b45309' : '#475569',
                        padding: '2px 6px',
                        borderRadius: 4,
                        fontWeight: 700,
                        fontSize: 11
                      }}>
                        {c.priority} / 10
                      </span>
                    </td>
                    <td className="mono" style={{ fontSize: 11 }}>
                      {c.min_rpm} – {c.max_rpm} RPM
                    </td>
                    <td className="mono">+{c.borrow_cap_pct}%</td>
                    <td>
                      <span className="badge badge-green">
                        <span className="badge-dot" /> {c.status}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: 6, justifyContent: 'flex-end' }}>
                        <button
                          onClick={() => setSelectedReceiptTenantId(c.tenant_id)}
                          className="secondary-button"
                          style={{
                            padding: '4px 8px',
                            fontSize: 11,
                            height: 26,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            color: '#4338ca',
                            borderColor: '#c7d2fe',
                            background: '#eef2ff',
                          }}
                          title="View Verifiable Fairness Receipt"
                        >
                          <FileText size={12} /> Receipt
                        </button>
                        <button
                          onClick={() => handleEdit(c)}
                          className="secondary-button"
                          style={{ padding: '4px 8px', fontSize: 11, height: 26 }}
                        >
                          <Edit2 size={12} /> Edit
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Verifiable Fairness Receipt Modal */}
      {selectedReceiptTenantId && (
        <FairnessReceiptModal
          tenantId={selectedReceiptTenantId}
          onClose={() => setSelectedReceiptTenantId(null)}
        />
      )}
    </div>
  )
}
