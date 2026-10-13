'use client'

import TenantRouteWrapper from '@/components/tenant-guard'

export default function TenantPoliciesPage() {
  return <TenantRouteWrapper initialTab="Fairness Contracts" />
}
