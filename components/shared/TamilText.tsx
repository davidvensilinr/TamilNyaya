import React from 'react'

interface TamilTextProps {
  children: React.ReactNode
  className?: string
}

export function TamilText({ children, className = '' }: TamilTextProps) {
  return (
    <span
      className={`font-tamil tracking-wide leading-relaxed ${className}`}
      style={{ fontFamily: '"Noto Sans Tamil", system-ui, sans-serif' }}
    >
      {children}
    </span>
  )
}
