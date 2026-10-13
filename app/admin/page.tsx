'use client'

import AdminRouteWrapper from '@/components/admin-guard'

export default function AdminPage() {
  return <AdminRouteWrapper initialTab="Overview" />
}
