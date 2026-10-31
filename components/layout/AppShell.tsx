'use client'

import React, { useEffect, useState } from 'react'
import { TopHeader } from './TopHeader'
import { Sidebar } from './Sidebar'
import { api, HealthInfo, DatasetStats } from '@/lib/api'

export function AppShell({ children }: { children: React.ReactNode }) {
  const [health, setHealth] = useState<HealthInfo | null>(null)
  const [stats, setStats] = useState<DatasetStats | null>(null)

  useEffect(() => {
    let mounted = true
    async function loadState() {
      const hRes = await api.getHealth()
      if (mounted && hRes.data) setHealth(hRes.data)

      const sRes = await api.getDatasetStats()
      if (mounted && sRes.data) setStats(sRes.data)
    }
    loadState()
    return () => {
      mounted = false
    }
  }, [])

  return (
    <div className="min-h-screen flex flex-col bg-[#0b1117]">
      <TopHeader health={health} />
      <div className="flex flex-1 max-w-[1600px] w-full mx-auto">
        <Sidebar kbCount={health?.kb_record_count} itemCount={stats?.total_items} />
        <main className="flex-1 p-6 md:p-8 min-w-0 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  )
}
