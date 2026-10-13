'use client'

import TenantRouteWrapper from '@/components/tenant-guard'

export default function TenantUsagePage() {
  return <TenantRouteWrapper initialTab="Resource Usage" />
}
