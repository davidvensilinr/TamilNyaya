import React from 'react'
import { AlertCircle } from 'lucide-react'

interface EmptyStateProps {
  title: string
  description: string
  action?: React.ReactNode
  icon?: React.ReactNode
}

export function EmptyState({ title, description, action, icon }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center border border-dashed border-[#263540] rounded-lg bg-[#0e161f]/60 my-4">
      <div className="p-3 bg-[#13232b] rounded-full text-[#66d9e8] mb-3">
        {icon || <AlertCircle size={24} />}
      </div>
      <h3 className="text-sm font-semibold text-[#e1edf0] mb-1">{title}</h3>
      <p className="text-xs text-[#8295a1] max-w-md mb-4">{description}</p>
      {action && <div>{action}</div>}
    </div>
  )
}
