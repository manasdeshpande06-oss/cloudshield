'use client'

import AdminRouteWrapper from '@/components/admin-guard'

export default function AdminPoliciesPage() {
  return <AdminRouteWrapper initialTab="Traffic & Quotas" />
}
