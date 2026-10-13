'use client'

import TenantRouteWrapper from '@/components/tenant-guard'

export default function TenantContractsPage() {
  return <TenantRouteWrapper initialTab="Fairness Contracts" />
}
