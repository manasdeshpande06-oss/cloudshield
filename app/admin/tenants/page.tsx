'use client'

import AdminRouteWrapper from '@/components/admin-guard'

export default function AdminTenantsPage() {
  return <AdminRouteWrapper initialTab="Tenants" />
}
