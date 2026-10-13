'use client'

import TenantRouteWrapper from '@/components/tenant-guard'

export default function TenantPage() {
  return <TenantRouteWrapper initialTab="My Overview" />
}
