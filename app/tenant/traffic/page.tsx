'use client'

import TenantRouteWrapper from '@/components/tenant-guard'

export default function TenantTrafficPage() {
  return <TenantRouteWrapper initialTab="Traffic & Quotas" />
}
