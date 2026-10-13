'use client'

import AdminRouteWrapper from '@/components/admin-guard'

export default function AdminAuditPage() {
  return <AdminRouteWrapper initialTab="Settings" />
}
