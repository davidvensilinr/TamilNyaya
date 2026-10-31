'use client'

import React from 'react'
import Link from 'next/link'
import { GitBranch, AlertTriangle, ShieldCheck } from 'lucide-react'
import { StatusBadge } from '../shared/StatusBadge'

interface TopHeaderProps {
  health?: {
    status: 'ok' | 'degraded'
    llm_enabled: boolean
    llm_disabled_reason: string
    kb_record_count: number
  } | null
}

export function TopHeader({ health }: TopHeaderProps) {
  const llmDisabled = health ? !health.llm_enabled : false

  return (
    <header className="border-b border-[#263540] bg-[#0b1117]/95 sticky top-0 z-50">
      <div className="h-[70px] px-6 flex justify-between items-center max-w-[1600px] mx-auto">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-8 h-8 rounded-lg bg-[#66d9e8] text-[#071117] flex items-center justify-center font-bold">
            <GitBranch size={18} />
          </div>
          <div>
            <div className="font-bold text-sm tracking-tight text-[#edf5f7] group-hover:text-[#66d9e8] transition-colors">
              TamilNyaya-Bench
            </div>
            <div className="text-[11px] text-[#8797a5]">
              Audit-first Legal Hallucination Benchmark <span className="text-[#465b68]">/</span> v0.1.0
            </div>
          </div>
        </Link>

        <div className="flex items-center gap-4 text-xs">
          {health ? (
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${health.status === 'ok' ? 'bg-[#74c69d]' : 'bg-[#e1a85a]'}`} />
              <span className="text-[#8797a5] font-mono text-[11px]">
                {health.status === 'ok' ? 'Full Operational' : 'Degraded Mode'}
              </span>
            </div>
          ) : (
            <span className="text-[#8797a5] font-mono text-[11px]">Connecting...</span>
          )}

          <StatusBadge
            status={health?.llm_enabled ? 'ok' : 'degraded'}
            label={health?.llm_enabled ? 'LLM Active' : 'LLM Disabled'}
          />
        </div>
      </div>

      {llmDisabled && (
        <div className="bg-[#e1a85a]/10 border-t border-b border-[#e1a85a]/30 px-6 py-2 text-xs text-[#e1a85a] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle size={15} className="flex-shrink-0" />
            <span>
              <strong>LLM features disabled:</strong> {health?.llm_disabled_reason || 'Add GROQ_API_KEY to .env to enable model evaluation and NLI scoring.'} Deterministic citation verification and KB exploration remain fully functional.
            </span>
          </div>
          <span className="text-[10px] font-mono uppercase tracking-wider bg-[#e1a85a]/20 px-2 py-0.5 rounded">
            Deterministic Only
          </span>
        </div>
      )}
    </header>
  )
}
