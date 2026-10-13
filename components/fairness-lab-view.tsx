'use client'

import React, { useState, useEffect, useCallback } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Cpu,
  FlaskConical,
  Layers,
  Play,
  RefreshCw,
  RotateCcw,
  Shield,
  ShieldAlert,
  Sliders,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Zap,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { fetchApi } from '@/lib/api'

export default function FairnessLabView({ onNotify }: { onNotify?: (msg: string) => void }) {
  const [burstFactor, setBurstFactor] = useState(4.5)
  const [totalWorkers, setTotalWorkers] = useState(12)
  const [quotaPerTenant, setQuotaPerTenant] = useState(40)
  const [seed, setSeed] = useState(42)
  const [shopPriority, setShopPriority] = useState(8)
  const [gamePriority, setGamePriority] = useState(5)
  const [foodPriority, setFoodPriority] = useState(4)

  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'comparison' | 'chart' | 'tenants'>('comparison')

  const runSimulation = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchApi<any>('/fairness-lab/custom-comparison', {
        method: 'POST',
        body: JSON.stringify({
          game_b_burst_factor: burstFactor,
          total_workers: totalWorkers,
          quota_per_tenant: quotaPerTenant,
          duration_seconds: 60,
          seed: seed,
          shop_a_priority: shopPriority,
          game_b_priority: gamePriority,
          food_c_priority: foodPriority,
        }),
      })
      setResult(res)
      if (onNotify) {
        onNotify(`3-Policy simulation executed with Game B burst ${burstFactor}x!`)
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to run policy simulation')
    } finally {
      setLoading(false)
    }
  }, [burstFactor, totalWorkers, quotaPerTenant, seed, shopPriority, gamePriority, foodPriority, onNotify])

  useEffect(() => {
    runSimulation()
  }, []) // run initial comparison on mount

  const [policyFilter, setPolicyFilter] = useState<'all' | 'unprotected' | 'fixed_quota' | 'adaptive'>('all')

  const resetDefaults = () => {
    setBurstFactor(4.5)
    setTotalWorkers(12)
    setQuotaPerTenant(40)
    setSeed(42)
    setShopPriority(8)
    setGamePriority(5)
    setFoodPriority(4)
  }

  const triggerGameBSpike = async () => {
    setBurstFactor(5.0)
    setLoading(true)
    try {
      await fetchApi<any>('/simulation/trigger-spike?burst_multiplier=5.0&policy=adaptive', { method: 'POST' }).catch(() => null)
      const res = await fetchApi<any>('/fairness-lab/custom-comparison', {
        method: 'POST',
        body: JSON.stringify({
          game_b_burst_factor: 5.0,
          total_workers: totalWorkers,
          quota_per_tenant: quotaPerTenant,
          duration_seconds: 60,
          seed: seed,
          shop_a_priority: shopPriority,
          game_b_priority: gamePriority,
          food_c_priority: foodPriority,
        }),
      })
      setResult(res)
      if (onNotify) onNotify('Game B 5x traffic spike triggered! Evidence-backed incident generated.')
    } catch (err: any) {
      setError(err?.message || 'Failed to trigger spike')
    } finally {
      setLoading(false)
    }
  }

  const handlePauseSimulator = async () => {
    try {
      await fetchApi<any>('/simulation/pause', { method: 'POST' })
      if (onNotify) onNotify('Simulation paused.')
    } catch {}
  }

  const handleResetSimulator = async () => {
    resetDefaults()
    try {
      await fetchApi<any>('/simulation/reset', { method: 'POST' })
      if (onNotify) onNotify('Simulator reset to baseline state.')
      runSimulation()
    } catch {}
  }

  const applyPresetScenario = (key: string) => {
    if (key === 'a') {
      setBurstFactor(1.0); setTotalWorkers(12); setQuotaPerTenant(40); setShopPriority(5); setGamePriority(5); setFoodPriority(5)
    } else if (key === 'b') {
      setBurstFactor(5.0); setTotalWorkers(12); setQuotaPerTenant(40); setShopPriority(5); setGamePriority(5); setFoodPriority(5)
    } else if (key === 'c') {
      setBurstFactor(4.0); setTotalWorkers(12); setQuotaPerTenant(40); setShopPriority(8); setGamePriority(5); setFoodPriority(5)
    } else if (key === 'd') {
      setBurstFactor(2.5); setTotalWorkers(12); setQuotaPerTenant(40); setShopPriority(5); setGamePriority(5); setFoodPriority(5)
    } else if (key === 'e') {
      setBurstFactor(3.0); setTotalWorkers(12); setQuotaPerTenant(40); setShopPriority(9); setGamePriority(5); setFoodPriority(3)
    }
    if (onNotify) onNotify(`Applied preset scenario ${key.toUpperCase()}`)
  }

  // Transform data for charts
  const latencyChartData = result?.policies?.map((p: any) => {
    const shop = p.tenants.find((t: any) => t.tenant_id === 'shop_a')
    const game = p.tenants.find((t: any) => t.tenant_id === 'game_b')
    const food = p.tenants.find((t: any) => t.tenant_id === 'food_c')
    return {
      policy: p.policy_label,
      'Shop A (Innocent)': Math.round(shop?.p95_latency_ms || 0),
      'Game B (Bursting)': Math.round(game?.p95_latency_ms || 0),
      'Food C (Innocent)': Math.round(food?.p95_latency_ms || 0),
    }
  }) || []

  const throughputChartData = result?.policies?.map((p: any) => {
    const shop = p.tenants.find((t: any) => t.tenant_id === 'shop_a')
    const game = p.tenants.find((t: any) => t.tenant_id === 'game_b')
    const food = p.tenants.find((t: any) => t.tenant_id === 'food_c')
    return {
      policy: p.policy_label,
      'Shop A': shop?.accepted || 0,
      'Game B': game?.accepted || 0,
      'Food C': food?.accepted || 0,
    }
  }) || []

  return (
    <div className="page-view" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Simulation Banner */}
      <section style={{
        background: 'linear-gradient(135deg, #1e1b4b 0%, #312e81 100%)',
        color: '#fff',
        borderRadius: 12,
        padding: '20px 24px',
        boxShadow: '0 4px 20px rgba(49, 46, 129, 0.25)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 16
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span style={{
              background: '#4f46e5',
              color: '#fff',
              fontSize: 10,
              fontWeight: 700,
              padding: '3px 8px',
              borderRadius: 4,
              letterSpacing: '0.05em'
            }}>
              SIMULATION MODE
            </span>
            <span style={{ fontSize: 12, opacity: 0.8 }}>
              Deterministic Evaluation Engine · Traceable Seed #{seed}
            </span>
          </div>
          <h2 style={{
            fontFamily: 'var(--font-serif)',
            fontSize: 22,
            margin: '0 0 6px',
            color: '#fff'
          }}>
            Fairness Lab: 3-Policy Multi-Tenant Evaluation
          </h2>
          <p style={{ margin: 0, fontSize: 13, opacity: 0.85, maxWidth: 680, lineHeight: 1.5 }}>
            Evaluating real resource allocation under identical workloads: <strong>Shop A</strong> (E-Commerce steady), <strong>Game B</strong> (Traffic burst), and <strong>Food C</strong> (Delivery API). Compare Unprotected Sharing vs Fixed Quotas vs Adaptive Borrowing.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            onClick={triggerGameBSpike}
            disabled={loading}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 14px',
              borderRadius: 8,
              border: 'none',
              background: '#dc2626',
              color: '#fff',
              fontSize: 12,
              fontWeight: 650,
              cursor: 'pointer',
              boxShadow: '0 2px 8px rgba(220,38,38,0.3)'
            }}
          >
            <Zap size={14} /> Trigger Game B Spike (5x)
          </button>
          <button
            onClick={handlePauseSimulator}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 12px',
              borderRadius: 8,
              border: '1px solid rgba(255,255,255,0.2)',
              background: 'rgba(255,255,255,0.08)',
              color: '#fff',
              fontSize: 12,
              cursor: 'pointer'
            }}
          >
            Pause
          </button>
          <button
            onClick={handleResetSimulator}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 12px',
              borderRadius: 8,
              border: '1px solid rgba(255,255,255,0.2)',
              background: 'rgba(255,255,255,0.08)',
              color: '#fff',
              fontSize: 12,
              cursor: 'pointer'
            }}
          >
            <RotateCcw size={14} /> Reset
          </button>
          <button
            onClick={runSimulation}
            disabled={loading}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 16px',
              borderRadius: 8,
              border: 'none',
              background: '#6366f1',
              color: '#fff',
              fontSize: 13,
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 2px 10px rgba(0,0,0,0.2)'
            }}
          >
            <Play size={14} /> {loading ? 'Simulating…' : 'Run 3-Policy Comparison'}
          </button>
        </div>
      </section>

      {/* Preset Scenarios bar */}
      <section style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted-ink)' }}>Repeatable Scenarios:</span>
        {[
          { key: 'a', label: 'Scenario A: Baseline (Normal)' },
          { key: 'b', label: 'Scenario B: Game B Spike (Noisy Neighbor)' },
          { key: 'c', label: 'Scenario C: Cascading Overload' },
          { key: 'd', label: 'Scenario D: Borrow & Return' },
          { key: 'e', label: 'Scenario E: Priority SLA' },
        ].map((s) => (
          <button
            key={s.key}
            onClick={() => applyPresetScenario(s.key)}
            className="secondary-button"
            style={{ fontSize: 11, padding: '4px 10px', height: 28 }}
          >
            {s.label}
          </button>
        ))}
      </section>

      {/* Simulator Interactive Controls */}
      <section className="panel" style={{ padding: '18px 22px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <Sliders size={17} style={{ color: '#2563eb' }} />
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700 }}>Simulation Parameters & Workload Contention</h3>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 18 }}>
          {/* Game B Burst */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <label style={{ fontSize: 12, fontWeight: 600 }}>Game B Traffic Burst</label>
              <strong style={{ color: '#dc2626', fontSize: 12 }}>{burstFactor}x Spike</strong>
            </div>
            <input
              type="range"
              min="1.0"
              max="10.0"
              step="0.5"
              value={burstFactor}
              onChange={(e) => setBurstFactor(parseFloat(e.target.value))}
              style={{ width: '100%', accentColor: '#dc2626' }}
            />
            <div style={{ fontSize: 10, color: '#687588', marginTop: 4 }}>
              Sudden surge simulating noisy-neighbor traffic
            </div>
          </div>

          {/* Processing Pool */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <label style={{ fontSize: 12, fontWeight: 600 }}>Shared Worker Pool</label>
              <strong style={{ color: '#2563eb', fontSize: 12 }}>{totalWorkers} Concurrent Workers</strong>
            </div>
            <input
              type="range"
              min="4"
              max="32"
              step="2"
              value={totalWorkers}
              onChange={(e) => setTotalWorkers(parseInt(e.target.value))}
              style={{ width: '100%', accentColor: '#2563eb' }}
            />
            <div style={{ fontSize: 10, color: '#687588', marginTop: 4 }}>
              Host execution capacity bound
            </div>
          </div>

          {/* Base Quota */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <label style={{ fontSize: 12, fontWeight: 600 }}>Fixed Quota / Tenant</label>
              <strong style={{ color: '#16a34a', fontSize: 12 }}>{quotaPerTenant} RPS</strong>
            </div>
            <input
              type="range"
              min="15"
              max="100"
              step="5"
              value={quotaPerTenant}
              onChange={(e) => setQuotaPerTenant(parseInt(e.target.value))}
              style={{ width: '100%', accentColor: '#16a34a' }}
            />
            <div style={{ fontSize: 10, color: '#687588', marginTop: 4 }}>
              Upper request boundary under fixed quota
            </div>
          </div>

          {/* Random Seed */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <label style={{ fontSize: 12, fontWeight: 600 }}>Deterministic Seed</label>
              <span className="mono" style={{ fontSize: 12 }}>#{seed}</span>
            </div>
            <input
              type="number"
              value={seed}
              onChange={(e) => setSeed(parseInt(e.target.value) || 1)}
              style={{
                width: '100%',
                padding: '6px 10px',
                border: '1px solid var(--border)',
                borderRadius: 6,
                fontSize: 12,
                background: 'var(--surface)',
                color: 'var(--text)'
              }}
            />
            <div style={{ fontSize: 10, color: '#687588', marginTop: 4 }}>
              Identical seed = exactly reproducible metrics
            </div>
          </div>
        </div>
      </section>

      {/* View Switcher */}
      <div style={{ display: 'flex', gap: 8, borderBottom: '1px solid var(--border)', paddingBottom: 10 }}>
        {[
          { key: 'comparison', label: 'Side-by-Side Policy Comparison', icon: Layers },
          { key: 'chart', label: 'Latency & Throughput Charts', icon: BarChart3 },
          { key: 'tenants', label: 'Tenant Level Breakdown', icon: Shield },
        ].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key as any)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 14px',
              borderRadius: 6,
              border: activeTab === key ? '1px solid #2563eb' : '1px solid transparent',
              background: activeTab === key ? '#edf3ff' : 'transparent',
              color: activeTab === key ? '#1d4ed8' : 'var(--muted-ink)',
              fontWeight: activeTab === key ? 650 : 500,
              fontSize: 12,
              cursor: 'pointer'
            }}
          >
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {error && (
        <div style={{ padding: 16, background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, color: '#b91c1c', fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* Tab: Side-by-Side Policies */}
      {activeTab === 'comparison' && result && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
          {result.policies.map((p: any) => {
            const isWinner = p.winner
            const borderColor = p.policy === 'unprotected' ? '#ef4444' : p.policy === 'fixed_quota' ? '#f59e0b' : '#10b981'
            const badgeColor = p.policy === 'unprotected' ? '#fef2f2' : p.policy === 'fixed_quota' ? '#fffbeb' : '#f0fdf4'
            const textColor = p.policy === 'unprotected' ? '#b91c1c' : p.policy === 'fixed_quota' ? '#b45309' : '#15803d'

            const innocentShop = p.tenants.find((t: any) => t.tenant_id === 'shop_a')
            const burstingGame = p.tenants.find((t: any) => t.tenant_id === 'game_b')
            const innocentFood = p.tenants.find((t: any) => t.tenant_id === 'food_c')

            return (
              <div
                key={p.policy}
                style={{
                  background: 'var(--surface)',
                  border: `2px solid ${borderColor}`,
                  borderRadius: 12,
                  padding: 20,
                  display: 'flex',
                  flexDirection: 'column',
                  position: 'relative',
                  boxShadow: isWinner ? '0 8px 24px rgba(16, 185, 129, 0.15)' : 'none'
                }}
              >
                {isWinner && (
                  <div style={{
                    position: 'absolute',
                    top: -12,
                    right: 18,
                    background: '#10b981',
                    color: '#fff',
                    padding: '2px 10px',
                    borderRadius: 99,
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: '0.04em'
                  }}>
                    RECOMMENDED POLICY
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                  <div>
                    <h3 style={{ margin: '0 0 4px', fontSize: 16, fontFamily: 'var(--font-serif)' }}>
                      {p.policy_label}
                    </h3>
                    <div style={{ fontSize: 11, color: 'var(--muted-ink)' }}>{p.policy_description}</div>
                  </div>
                </div>

                <div style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: 10,
                  margin: '14px 0',
                  padding: 12,
                  background: badgeColor,
                  borderRadius: 8
                }}>
                  <div>
                    <div style={{ fontSize: 10, color: textColor, fontWeight: 600 }}>Overall Acceptance</div>
                    <strong style={{ fontSize: 18, color: textColor }}>{p.overall_acceptance_rate.toFixed(1)}%</strong>
                    <div style={{ fontSize: 10, opacity: 0.8, color: textColor }}>{p.overall_accepted} req accepted</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: textColor, fontWeight: 600 }}>System Fairness Index</div>
                    <strong style={{ fontSize: 18, color: textColor }}>{p.system_fairness_index.toFixed(2)}</strong>
                    <div style={{ fontSize: 10, opacity: 0.8, color: textColor }}>Capacity Util: {p.system_throughput_pct.toFixed(0)}%</div>
                  </div>
                </div>

                {/* Innocent vs Offending Impact */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, margin: '6px 0 16px' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)' }}>Cross-Tenant Experience:</div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '4px 0', borderBottom: '1px solid var(--line)' }}>
                    <span>Shop A (Innocent) p95 Latency</span>
                    <strong className="mono" style={{ color: innocentShop?.p95_latency_ms > 200 ? '#dc2626' : '#16a34a' }}>
                      {Math.round(innocentShop?.p95_latency_ms || 0)} ms
                    </strong>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '4px 0', borderBottom: '1px solid var(--line)' }}>
                    <span>Food C (Innocent) p95 Latency</span>
                    <strong className="mono" style={{ color: innocentFood?.p95_latency_ms > 200 ? '#dc2626' : '#16a34a' }}>
                      {Math.round(innocentFood?.p95_latency_ms || 0)} ms
                    </strong>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '4px 0', borderBottom: '1px solid var(--line)' }}>
                    <span>Game B (Spike) Rejections</span>
                    <strong className="mono" style={{ color: burstingGame?.rejected > 0 ? '#b45309' : '#16a34a' }}>
                      {burstingGame?.rejected || 0} rejected
                    </strong>
                  </div>

                  {p.policy === 'adaptive' && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '4px 0', borderBottom: '1px solid var(--line)' }}>
                      <span>Borrowed / Reclaimed Slots</span>
                      <strong className="mono" style={{ color: '#2563eb' }}>
                        {burstingGame?.borrowed_slots || 0} borrowed · {burstingGame?.returned_slots || 0} reclaimed
                      </strong>
                    </div>
                  )}
                </div>

                {/* Behavioral takeaway */}
                <div style={{
                  marginTop: 'auto',
                  padding: '10px 12px',
                  background: 'var(--app-bg)',
                  borderRadius: 8,
                  fontSize: 11,
                  lineHeight: 1.5,
                  color: 'var(--muted-ink)'
                }}>
                  {p.policy === 'unprotected' && (
                    <span><strong>Trade-off:</strong> High total requests, but Game B monopolizes queues, ballooning innocent Shop A & Food C latency. Noisy neighbor unchecked.</span>
                  )}
                  {p.policy === 'fixed_quota' && (
                    <span><strong>Trade-off:</strong> Complete isolation protects innocent tenants from latency spikes, but excess worker slots sit idle when demand fluctuates.</span>
                  )}
                  {p.policy === 'adaptive' && (
                    <span><strong>Trade-off:</strong> Guarantees minimum capacity to Shop A & Food C, lets Game B borrow idle headroom, and immediately reclaims capacity upon contention.</span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Tab: Charts */}
      {activeTab === 'chart' && result && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <section className="panel" style={{ padding: 18 }}>
            <h3 style={{ margin: '0 0 4px', fontSize: 14 }}>p95 Latency by Policy (ms)</h3>
            <p style={{ margin: '0 0 16px', fontSize: 11, color: 'var(--muted-ink)' }}>
              Lower is better · Innocent tenants (Shop A & Food C) suffer severe degradation under Unprotected sharing.
            </p>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={latencyChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" strokeOpacity={0.4} />
                <XAxis dataKey="policy" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} unit="ms" />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="Shop A (Innocent)" fill="#6366f1" />
                <Bar dataKey="Food C (Innocent)" fill="#f59e0b" />
                <Bar dataKey="Game B (Bursting)" fill="#10b981" />
              </BarChart>
            </ResponsiveContainer>
          </section>

          <section className="panel" style={{ padding: 18 }}>
            <h3 style={{ margin: '0 0 4px', fontSize: 14 }}>Accepted Requests Throughput</h3>
            <p style={{ margin: '0 0 16px', fontSize: 11, color: 'var(--muted-ink)' }}>
              Adaptive fairness captures extra throughput without sacrificing fairness.
            </p>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={throughputChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" strokeOpacity={0.4} />
                <XAxis dataKey="policy" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="Shop A" fill="#6366f1" />
                <Bar dataKey="Food C" fill="#f59e0b" />
                <Bar dataKey="Game B" fill="#10b981" />
              </BarChart>
            </ResponsiveContainer>
          </section>
        </div>
      )}

      {/* Tab: Tenants Detailed Table */}
      {activeTab === 'tenants' && result && (
        <section className="panel">
          <div className="panel-header" style={{ padding: '16px 20px 12px' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: 15 }}>Per-Tenant Evaluation Records Across All 3 Policies</h3>
              <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--muted-ink)' }}>
                Demonstrating reproducible resource allocation, guarantee attainment, and capacity reclamation
              </p>
            </div>
            <span style={{
              background: '#e0e7ff',
              color: '#3730a3',
              fontSize: 11,
              fontWeight: 700,
              padding: '3px 8px',
              borderRadius: 6
            }}>
              SIMULATION MODE
            </span>
          </div>

          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Policy</th>
                  <th>Tenant / Workload</th>
                  <th>Accepted</th>
                  <th>Throttled</th>
                  <th>Success %</th>
                  <th>p95 Latency</th>
                  <th>Queue Wait</th>
                  <th>Borrowed / Returned</th>
                  <th>Guarantee Attainment</th>
                </tr>
              </thead>
              <tbody>
                {result.policies.flatMap((p: any) =>
                  p.tenants.map((t: any, idx: number) => {
                    const isGuaranteeMet = t.acceptance_rate >= 90.0 && t.p95_latency_ms < 150
                    return (
                      <tr key={`${p.policy}-${t.tenant_id}`}>
                        {idx === 0 ? (
                          <td rowSpan={p.tenants.length} style={{ fontWeight: 700, verticalAlign: 'top', background: 'var(--app-bg)' }}>
                            {p.policy_label}
                          </td>
                        ) : null}
                        <td>
                          <div style={{ fontWeight: 600, color: t.color }}>{t.tenant_name}</div>
                          <div style={{ fontSize: 10, opacity: 0.6 }}>{t.tenant_id}</div>
                        </td>
                        <td className="mono"><strong>{t.accepted}</strong></td>
                        <td className="mono">{t.rejected > 0 ? <span style={{ color: '#dc2626' }}>{t.rejected}</span> : '0'}</td>
                        <td className="mono">{t.acceptance_rate.toFixed(1)}%</td>
                        <td className="mono" style={{ color: t.p95_latency_ms > 200 ? '#dc2626' : '#16a34a' }}>
                          {Math.round(t.p95_latency_ms)} ms
                        </td>
                        <td className="mono">{Math.round(t.avg_queue_wait_ms)} ms</td>
                        <td className="mono">
                          {t.borrowed_slots > 0 ? `+${t.borrowed_slots} / -${t.returned_slots}` : '—'}
                        </td>
                        <td>
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            padding: '3px 7px',
                            borderRadius: 4,
                            fontSize: 10,
                            fontWeight: 650,
                            background: isGuaranteeMet ? '#dcfce7' : '#fee2e2',
                            color: isGuaranteeMet ? '#15803d' : '#b91c1c'
                          }}>
                            {isGuaranteeMet ? 'Satisfied' : 'Degraded'}
                          </span>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Lab Key Insight */}
      {result?.key_insight && (
        <div style={{
          padding: '14px 18px',
          background: '#f0fdf4',
          border: '1px solid #bbf7d0',
          borderRadius: 8,
          fontSize: 12,
          lineHeight: 1.6,
          color: '#166534',
          display: 'flex',
          alignItems: 'center',
          gap: 12
        }}>
          <Sparkles size={18} style={{ flexShrink: 0, color: '#16a34a' }} />
          <div>
            <strong>Evaluation Insight:</strong> {result.key_insight}
          </div>
        </div>
      )}
    </div>
  )
}
