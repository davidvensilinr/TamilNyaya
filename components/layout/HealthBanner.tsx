'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import { api, HealthInfo } from '@/lib/api';

export function HealthBanner() {
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getHealth()
      .then((res) => {
        if (res.data) {
          setHealth(res.data);
        } else {
          setError(res.error || 'Failed to reach backend API');
        }
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="flex items-center gap-3 px-6 py-2.5 bg-[rgba(220,80,80,.08)] border-b border-[rgba(220,80,80,.25)] text-[#e05555] text-xs">
        <XCircle size={14} />
        <span>Backend unreachable ({error}). Ensure your backend server is running.</span>
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
          ? `LLM not enabled — ${health.llm_disabled_reason || 'Set GROQ_API_KEY in environment variables.'}`
          : `Backend connected · ${health.kb_record_count} KB records · All models operational`}
      </span>
    </div>
  );
}
