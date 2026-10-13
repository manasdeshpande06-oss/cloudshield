'use client'

import TenantRouteWrapper from '@/components/tenant-guard'

export default function TenantProfilePage() {
  return <TenantRouteWrapper initialTab="Company Profile" />
}
