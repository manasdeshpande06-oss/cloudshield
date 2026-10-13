"""
CloudShield FairGuard — Pydantic models (request & response shapes).
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

class CompanyOut(BaseModel):
    id: str
    name: str
    slug: str
    registered_at: str
    status: str
    tenant_count: int = 0


class CompanyDetail(CompanyOut):
    total_requests_per_minute: int = 0
    total_accepted: int = 0
    total_rejected: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    active_incidents: int = 0
    total_cpu_budget: float = 0.0
    total_mem_budget: float = 0.0


# ---------------------------------------------------------------------------
# Tenants
# ---------------------------------------------------------------------------

class TenantOut(BaseModel):
    id: str
    company_id: str
    company_name: str = ""
    name: str
    workload_type: str
    status: str
    created_at: str
    accepted_count: int = 0
    rejected_count: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    requests_per_minute: float = 0.0
    quota_rpm: int = 0


class TenantQuota(BaseModel):
    requests_per_minute: int = Field(ge=1, le=100_000)
    max_concurrency: int = Field(ge=1, le=1000)
    queue_limit: int = Field(default=100, ge=1, le=10_000)
    resource_budget_cpu: float = Field(default=25.0, ge=0, le=100)
    resource_budget_memory: float = Field(default=25.0, ge=0, le=100)
    window_seconds: int = Field(default=60, ge=10, le=3600)


class TenantQuotaOut(BaseModel):
    tenant_id: str
    requests_per_minute: int
    max_concurrency: int
    queue_limit: int = 100
    resource_budget_cpu: float = 25.0
    resource_budget_memory: float = 25.0
    window_seconds: int
    updated_at: str


class TenantMetrics(BaseModel):
    tenant: TenantOut
    quota: TenantQuotaOut
    requests_per_minute: float = 0
    accepted_count: int = 0
    rejected_count: int = 0
    avg_latency_ms: float = 0
    p95_latency_ms: float = 0
    active_jobs: int = 0
    queued_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    # Resource (job-level where available, else machine-level labelled)
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    cpu_scope: str = "not_measured"  # "job-level", "machine-estimate", "not_measured"
    memory_scope: str = "not_measured"
    queue_depth: int = 0
    queue_wait_ms: float = 0
    quota_utilization_pct: float = 0   # rpm / quota * 100
    cpu_budget_utilization_pct: Optional[float] = None
    quota_violations: int = 0
    resource_violations: int = 0
    active_protection: Optional[str] = None


class TenantComparisonRow(BaseModel):
    """Flat row used for the cross-tenant comparison table."""
    tenant_id: str
    tenant_name: str
    company_id: str
    company_name: str
    workload_type: str
    status: str
    requests_per_minute: float = 0
    quota_rpm: int = 0
    quota_utilization_pct: float = 0
    accepted_count: int = 0
    rejected_count: int = 0
    avg_latency_ms: float = 0
    p95_latency_ms: float = 0
    active_jobs: int = 0
    queued_jobs: int = 0
    queue_depth: int = 0
    queue_wait_ms: float = 0
    max_concurrency: int = 0
    queue_limit: int = 0
    resource_budget_cpu: float = 0
    resource_budget_memory: float = 0
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    cpu_scope: str = "not_measured"
    quota_violations: int = 0
    resource_violations: int = 0
    active_protection: Optional[str] = None
    open_incidents: int = 0


# ---------------------------------------------------------------------------
# Workload requests
# ---------------------------------------------------------------------------

class WorkloadRequest(BaseModel):
    tenant_id: str
    api_key: str
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkloadResponse(BaseModel):
    status: str
    tenant_id: str
    latency_ms: float = 0
    message: str = ""
    retry_after_seconds: float | None = None


# ---------------------------------------------------------------------------
# Traffic / Events
# ---------------------------------------------------------------------------

class RequestEventOut(BaseModel):
    id: int
    tenant_id: str
    timestamp: str
    status: str
    latency_ms: float | None
    reason: str | None
    is_simulated: bool


class TrafficBucket(BaseModel):
    time: str
    accepted: int = 0
    rejected: int = 0


class SecurityEventOut(BaseModel):
    id: int
    tenant_id: str | None
    timestamp: str
    event_type: str
    severity: str
    description: str | None
    is_simulated: bool


class ResourceMeasurementOut(BaseModel):
    id: int
    tenant_id: str | None
    timestamp: str
    cpu_percent: float | None
    memory_percent: float | None
    queue_depth: int | None
    queue_wait_ms: float | None = None
    active_jobs: int | None = None
    scope: str = "machine"
    is_simulated: bool


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

class JobOut(BaseModel):
    id: int
    tenant_id: str
    job_type: str = "generic"
    status: str
    priority: int = 5
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[float] = None
    queue_wait_ms: Optional[float] = None
    worker_id: Optional[int] = None
    is_simulated: bool = False


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------

class SchedulingDecisionOut(BaseModel):
    id: int
    job_id: int
    tenant_id: str
    tenant_name: str = ""
    company_id: str
    company_name: str = ""
    event: str
    scheduling_turn: Optional[int] = None
    queue_wait_ms: Optional[float] = None
    execution_ms: Optional[float] = None
    worker_id: Optional[int] = None
    result: Optional[str] = None
    decision_reason: Optional[str] = None
    timestamp: str


class SchedulerStatus(BaseModel):
    running: bool
    active_workers: int = 0
    max_workers: int = 12
    queued_jobs_total: int = 0
    per_tenant_queues: dict[str, int] = Field(default_factory=dict)
    scheduling_turn: int = 0
    jobs_completed: int = 0
    jobs_failed: int = 0


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

class SimulationConfig(BaseModel):
    tenant_ids: list[str] = Field(default_factory=list, description="Empty = all tenants")
    requests_per_second: float = Field(default=10, ge=0.1, le=1000)
    duration_seconds: int = Field(default=30, ge=5, le=300)
    scenario: str = Field(default="normal", description="normal|overuse|noisy|harmless_traffic")


class SimulationStatus(BaseModel):
    running: bool
    started_at: str | None = None
    config: SimulationConfig | None = None
    requests_sent: int = 0
    requests_accepted: int = 0
    requests_rejected: int = 0
    elapsed_seconds: float = 0
    scenario: str = "normal"


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

class AffectedTenantInfo(BaseModel):
    tenant_id: str
    company: str
    baseline_p95_ms: float = 0
    observed_p95_ms: float = 0
    queue_wait_increase_ms: float = 0


class IncidentOut(BaseModel):
    id: int
    tenant_id: str
    tenant_name: str = ""
    company_name: str = ""
    title: str
    description: str | None
    severity: str
    status: str
    detected_at: str
    resolved_at: str | None
    evidence: dict[str, Any] | None = None
    affected_tenants: list[AffectedTenantInfo] | None = None
    detection_rules: list[str] | None = None
    baseline_metrics: dict[str, Any] | None = None
    observed_metrics: dict[str, Any] | None = None
    is_simulated: bool


# ---------------------------------------------------------------------------
# Protection actions
# ---------------------------------------------------------------------------

class ProtectionActionRequest(BaseModel):
    tenant_id: str
    action_type: str = Field(description="concurrency_reduction | rate_limit_override | defer_background")
    parameters: dict[str, Any] = Field(default_factory=dict)
    incident_id: int | None = None
    duration_minutes: int = Field(default=30, ge=1, le=1440)


class ProtectionActionOut(BaseModel):
    id: int
    incident_id: int | None
    tenant_id: str
    action_type: str
    parameters: dict[str, Any] | None = None
    applied_at: str | None
    rolled_back_at: str | None
    expires_at: str | None = None
    result_metrics: dict[str, Any] | None = None
    outcome: str | None = None
    status: str


class RollbackRequest(BaseModel):
    action_id: int


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------

class ExperimentRequest(BaseModel):
    tenant_id: str
    name: str = "Unnamed experiment"
    scenario: str = Field(default="custom", description="scenario_a|b|c|d|e|custom")
    config: dict[str, Any] = Field(default_factory=dict)
    duration_seconds: int = Field(default=30, ge=5, le=300)


class ExperimentOut(BaseModel):
    id: int
    tenant_id: str
    name: str
    scenario: str | None = None
    status: str
    config: dict[str, Any] | None = None
    started_at: str | None
    completed_at: str | None
    before_metrics: dict[str, Any] | None = None
    after_metrics: dict[str, Any] | None = None
    outcome: str | None = None
    is_simulated: bool


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

class OverviewResponse(BaseModel):
    total_requests_per_minute: int
    total_accepted: int
    total_rejected: int
    success_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    active_incidents: int
    open_protection_actions: int = 0
    machine_cpu_percent: float | None = None
    machine_memory_percent: float | None = None
    active_workers: int = 0
    total_queued_jobs: int = 0
    is_simulated: bool = False
    controller_status: str = "monitoring"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.2.0"
    database: str = "connected"
    timestamp: str


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class ControllerLogOut(BaseModel):
    id: int
    timestamp: str
    level: str
    event: str
    tenant_id: str | None
    detail: str | None


# ---------------------------------------------------------------------------
# Fairness Receipt
# ---------------------------------------------------------------------------

class FairnessReceipt(BaseModel):
    incident_id: int
    title: str
    detected_at: str
    cause_classification: str  # "Observed" | "Suspected cause" | "Confirmed cause" | "Cause undetermined"
    observed_workload_pattern: str
    suspected_tenant_id: str
    suspected_tenant_name: str
    suspected_company_name: str
    affected_tenants: list[dict[str, Any]]
    evidence_signals: list[str]
    confidence_level: str
    policy_action_taken: Optional[dict[str, Any]] = None
    before_metrics: Optional[dict[str, Any]] = None
    after_metrics: Optional[dict[str, Any]] = None
    recovery_status: str  # "measured_recovered" | "measuring_in_progress" | "not_yet_measured"
    data_source_label: str  # "LIVE APPLICATION DATA" | "SIMULATION MODE"
    summary_text: str

