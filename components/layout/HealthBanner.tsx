'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import type { HealthResponse } from '@/lib/api';

export function HealthBanner() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('http://localhost:8000/api/health')
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((d) => setHealth(d as HealthResponse))
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="flex items-center gap-3 px-6 py-2.5 bg-[rgba(220,80,80,.08)] border-b border-[rgba(220,80,80,.25)] text-[#e05555] text-xs">
        <XCircle size={14} />
        <span>Backend unreachable ({error}). Ensure FastAPI is running on port 8000.</span>
      </div>
    );
  }

  if (!health) return null;

  const llmOff = !health.llm_enabled;

  return (
    <div
      className={`flex items-center gap-3 px-6 py-2 border-b text-xs ${
        llmOff
          ? 'bg-[rgba(225,168,90,.06)] border-[rgba(225,168,90,.25)] text-[#e1a85a]'
          : 'bg-[rgba(116,198,157,.06)] border-[rgba(116,198,157,.2)] text-[#74c69d]'
      }`}
    >
      {llmOff ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
      <span>
        {llmOff
          ? 'LLM not enabled — judge-based metrics will be unavailable. Set GROQ_API_KEY to enable.'
          : `Backend connected · ${health.kb_record_count} KB records · ${health.models?.length ?? 0} models available`}
      </span>
    </div>
  );
}
