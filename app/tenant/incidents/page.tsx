'use client'

import TenantRouteWrapper from '@/components/tenant-guard'

export default function TenantIncidentsPage() {
  return <TenantRouteWrapper initialTab="Incidents" />
}
