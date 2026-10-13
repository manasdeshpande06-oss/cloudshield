'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function TenantReportsPage() {
  const router = useRouter()
  useEffect(() => {
    router.replace('/tenant')
  }, [router])
  return null
}
