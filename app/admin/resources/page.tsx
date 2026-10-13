'use client'

import AdminRouteWrapper from '@/components/admin-guard'

export default function AdminResourcesPage() {
  return <AdminRouteWrapper initialTab="Resource Monitoring" />
}
