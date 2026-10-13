'use client'

import TenantRouteWrapper from '@/components/tenant-guard'

export default function TenantTenantsPage() {
  return <TenantRouteWrapper initialTab="My Tenants" />
}
