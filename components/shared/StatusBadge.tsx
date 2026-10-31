import React from 'react'

interface StatusBadgeProps {
  status: string
  label?: string
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const norm = (status || '').toLowerCase()
  let bg = 'bg-[#1a2932] text-[#8196a0] border-[#263540]'

  if (['ok', 'completed', 'done', 'in force', 'calibrated', 'true', 'active'].includes(norm)) {
    bg = 'bg-[#74c69d]/10 text-[#74c69d] border-[#74c69d]/30'
  } else if (['pending', 'running', 'human_review_required'].includes(norm)) {
    bg = 'bg-[#66d9e8]/10 text-[#66d9e8] border-[#66d9e8]/30'
  } else if (['degraded', 'failed', 'repealed', 'severity 3', 'error', 'insufficient_data', 'not_run'].includes(norm)) {
    bg = 'bg-[#e1a85a]/10 text-[#e1a85a] border-[#e1a85a]/30'
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono border ${bg}`}>
      {label || status}
    </span>
  )
}
