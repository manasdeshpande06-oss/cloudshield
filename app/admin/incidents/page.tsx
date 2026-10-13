'use client'

import AdminRouteWrapper from '@/components/admin-guard'

export default function AdminIncidentsPage() {
  return <AdminRouteWrapper initialTab="Noisy-Neighbor Incidents" />
}
