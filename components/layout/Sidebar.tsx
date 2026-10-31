'use client'

import React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  Layers3,
  Database,
  FileSpreadsheet,
  PlaySquare,
  Trophy,
  CheckCircle2,
  Users,
  ScrollText,
  BookOpen,
  ShieldCheck,
} from 'lucide-react'

const navItems = [
  { href: '/', label: 'Overview', sub: 'System status & metrics', icon: Layers3 },
  { href: '/kb', label: 'Knowledge Base', sub: 'Acts, sections & provenance', icon: Database },
  { href: '/dataset', label: 'Benchmark Items', sub: 'Generated test suites', icon: FileSpreadsheet },
  { href: '/runs', label: 'Run Console', sub: 'Model evaluations', icon: PlaySquare },
  { href: '/leaderboard', label: 'Leaderboard', sub: 'Rankings & CIs', icon: Trophy },
  { href: '/check', label: 'Live Check', sub: 'Interactive verification', icon: CheckCircle2 },
  { href: '/annotations', label: 'Annotations', sub: 'Human gold & calibration', icon: Users },
  { href: '/audit', label: 'Audit Log', sub: 'Traceability & integrity', icon: ScrollText },
  { href: '/methodology', label: 'Methodology', sub: 'Formulas & taxonomy', icon: BookOpen },
]

export function Sidebar({ kbCount, itemCount }: { kbCount?: number; itemCount?: number }) {
  const pathname = usePathname()

  return (
    <aside className="w-64 flex-none border-r border-[#263540] bg-[#0d151d] flex flex-col justify-between p-4 min-h-[calc(100vh-70px)]">
      <div>
        <div className="text-[10px] uppercase font-bold tracking-widest text-[#718493] px-2 mb-3">
          Evaluation Console
        </div>
        <nav className="flex flex-col gap-1">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href))
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-md transition-colors text-left ${
                  isActive
                    ? 'bg-[#172832] text-[#66d9e8] font-medium'
                    : 'text-[#8295a1] hover:bg-[#131d26] hover:text-[#c4d1d7]'
                }`}
              >
                <Icon size={16} className={isActive ? 'text-[#66d9e8]' : 'text-[#718493]'} />
                <div className="flex flex-col">
                  <span className="text-xs font-semibold leading-tight">{item.label}</span>
                  <span className="text-[10px] text-[#627783] leading-tight mt-0.5">{item.sub}</span>
                </div>
              </Link>
            )
          })}
        </nav>
      </div>

      <div className="mt-8 pt-4 border-t border-[#263540] flex flex-col gap-3">
        <div className="text-[10px] uppercase font-bold tracking-widest text-[#718493] px-1">
          Knowledge State
        </div>
        <div className="bg-[#111a23] p-3 rounded border border-[#20303a] text-xs flex flex-col gap-2">
          <div className="flex justify-between items-center text-[#7e929c]">
            <span>KB Provisions:</span>
            <span className="font-mono font-bold text-[#e1edf0]">{kbCount ?? '...'}</span>
          </div>
          <div className="flex justify-between items-center text-[#7e929c]">
            <span>Benchmark Items:</span>
            <span className="font-mono font-bold text-[#e1edf0]">{itemCount ?? '...'}</span>
          </div>
        </div>

        <div className="flex items-center gap-2 p-2 rounded bg-[#0b1218] border border-[#1b2832] text-[10px] text-[#718590]">
          <ShieldCheck size={14} className="text-[#74c69d] flex-shrink-0" />
          <span>Strict auditability · No synthetic data</span>
        </div>
      </div>
    </aside>
  )
}
