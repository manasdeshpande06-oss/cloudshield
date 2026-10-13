'use client'

import TenantRouteWrapper from '@/components/tenant-guard'

export default function TenantReportsPage() {
  return <TenantRouteWrapper initialTab="Reports" />
}
