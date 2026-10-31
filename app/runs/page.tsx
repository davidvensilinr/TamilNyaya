'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { AppShell } from '@/components/layout/AppShell'
import { api, RunSummary, HealthInfo } from '@/lib/api'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { EmptyState } from '@/components/shared/EmptyState'
import { PlaySquare, Download, RefreshCw, AlertCircle, Sparkles, Terminal, CheckCircle2 } from 'lucide-react'

export default function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [health, setHealth] = useState<HealthInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // Start Run Form State
  const [modelId, setModelId] = useState('qwen/qwen3.8-27b')
  const [temperature, setTemperature] = useState(0.0)
  const [maxTokens, setMaxTokens] = useState(512)
  const [seed, setSeed] = useState(42)

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    const [rRes, hRes] = await Promise.all([
      api.listRuns(50, 0),
      api.getHealth(),
    ])
    if (rRes.data) setRuns(rRes.data)
    if (hRes.data) setHealth(hRes.data)
    setLoading(false)
  }

  async function handleStartRun(e: React.FormEvent) {
    e.preventDefault()
    setStarting(true)
    setErrorMsg(null)

    const res = await api.startRun({
      model_id: modelId,
      temperature,
      max_tokens: maxTokens,
      seed,
    })

    if (res.data) {
      await loadData()
    } else {
      setErrorMsg(res.error || 'Failed to trigger evaluation run')
    }
    setStarting(false)
  }

  return (
    <AppShell>
      <div className="space-y-6 max-w-6xl">
        {/* Header */}
        <div className="border-b border-[#263540] pb-5">
          <div className="text-[10px] uppercase font-bold tracking-widest text-[#718493] mb-1">
            Execution Harness · Traceable Evaluations
          </div>
          <h1 className="text-2xl font-bold text-[#eef5f7] tracking-tight">
            Evaluation Run Console
          </h1>
          <p className="text-xs text-[#8295a1] mt-1 max-w-2xl leading-relaxed">
            Execute model evaluations against real benchmark items. Every raw prompt, LLM completion token, and verification step is persisted for auditability.
          </p>
        </div>

        {/* Start Run Box */}
        <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-4">
          <div className="flex items-center justify-between border-b border-[#20303a] pb-3">
            <div className="flex items-center gap-2">
              <PlaySquare size={16} className="text-[#66d9e8]" />
              <h2 className="text-sm font-semibold text-[#e1edf0]">Configure New Evaluation Run</h2>
            </div>
            <StatusBadge
              status={health?.llm_enabled ? 'ok' : 'degraded'}
              label={health?.llm_enabled ? 'Groq Active' : 'LLM Disabled'}
            />
          </div>

          {!health && !loading && (
            <div className="p-3 bg-[#f87171]/10 border border-[#f87171]/30 rounded text-xs text-[#f87171] flex items-start gap-2">
              <AlertCircle size={15} className="mt-0.5 flex-shrink-0" />
              <div>
                <strong>Cannot connect to Backend API.</strong> Make sure your backend service is running and accessible (or check NEXT_PUBLIC_API_URL).
              </div>
            </div>
          )}

          {health && !health.llm_enabled && (
            <div className="p-3 bg-[#e1a85a]/10 border border-[#e1a85a]/30 rounded text-xs text-[#e1a85a] flex items-start gap-2">
              <AlertCircle size={15} className="mt-0.5 flex-shrink-0" />
              <div>
                <strong>LLM features are currently disabled.</strong> {health.llm_disabled_reason || 'Set GROQ_API_KEY in backend environment variables to enable evaluation runs.'}
              </div>
            </div>
          )}

          {errorMsg && (
            <div className="p-3 bg-[#f87171]/10 border border-[#f87171]/30 rounded text-xs text-[#f87171]">
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleStartRun} className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            <div>
              <label className="text-[10px] uppercase font-bold text-[#718493] block mb-1">
                Model Under Test
              </label>
              <select
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
                disabled={!health?.llm_enabled || starting}
                className="w-full bg-[#0b1117] border border-[#20303a] rounded py-1.5 px-3 text-[#c4d1d7] focus:outline-none focus:border-[#66d9e8]"
              >
                <option value="qwen/qwen3.8-27b">qwen/qwen3.8-27b (Groq - Active)</option>
                <option value="openai/gpt-oss-120b">openai/gpt-oss-120b (Groq - Active)</option>
                <option value="openai/gpt-oss-20b">openai/gpt-oss-20b (Groq - Active)</option>
                <option value="allam-2-7b">allam-2-7b (Groq - Active)</option>
              </select>
              <span className="text-[9px] text-[#556977] block mt-1">
                General-purpose model, not fine-tuned for Tamil law
              </span>
            </div>

            <div>
              <label className="text-[10px] uppercase font-bold text-[#718493] block mb-1">
                Temperature
              </label>
              <input
                type="number"
                step="0.1"
                min="0"
                max="1"
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                disabled={!health?.llm_enabled || starting}
                className="w-full bg-[#0b1117] border border-[#20303a] rounded py-1.5 px-3 text-[#c4d1d7] focus:outline-none focus:border-[#66d9e8]"
              />
              <span className="text-[9px] text-[#556977] block mt-1">0.0 for deterministic baseline</span>
            </div>

            <div>
              <label className="text-[10px] uppercase font-bold text-[#718493] block mb-1">
                Max Completion Tokens
              </label>
              <input
                type="number"
                step="64"
                min="128"
                max="2048"
                value={maxTokens}
                onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                disabled={!health?.llm_enabled || starting}
                className="w-full bg-[#0b1117] border border-[#20303a] rounded py-1.5 px-3 text-[#c4d1d7] focus:outline-none focus:border-[#66d9e8]"
              />
              <span className="text-[9px] text-[#556977] block mt-1">Default: 512 tokens</span>
            </div>

            <div className="flex flex-col justify-end">
              <button
                type="submit"
                disabled={!health?.llm_enabled || starting}
                className="w-full py-2 px-4 rounded bg-[#66d9e8] hover:bg-[#52c8d7] text-[#071117] font-bold text-xs flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
              >
                <PlaySquare size={14} />
                {starting ? 'Initializing Run...' : 'Launch Evaluation Run'}
              </button>
            </div>
          </form>
        </div>

        {/* Existing Runs List */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-[#e1edf0]">Recorded Evaluation Runs ({runs.length})</h2>
            <button
              onClick={loadData}
              className="text-xs text-[#718493] hover:text-[#eef5f7] flex items-center gap-1 font-mono"
            >
              <RefreshCw size={12} /> Refresh
            </button>
          </div>

          {loading ? (
            <div className="text-center py-12 text-xs text-[#8295a1]">Loading runs...</div>
          ) : runs.length > 0 ? (
            <div className="space-y-3">
              {runs.map((r) => (
                <div
                  key={r.run_id}
                  className="p-4 rounded-lg bg-[#111a23] border border-[#263540] flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs font-bold text-[#66d9e8]">
                        {r.model_id}
                      </span>
                      <StatusBadge status={r.status} />
                      <span className="text-[10px] text-[#6d818d] font-mono">
                        temp: {r.temperature} · max_tokens: {r.max_tokens}
                      </span>
                    </div>

                    <div className="text-xs text-[#8295a1] font-mono">
                      Run ID: {r.run_id}
                    </div>

                    <div className="text-[11px] text-[#718493]">
                      Started: {new Date(r.started_at).toLocaleString()}
                      {r.completed_at && ` · Completed: ${new Date(r.completed_at).toLocaleTimeString()}`}
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <div className="text-xs font-mono font-bold text-[#e1edf0]">
                        {r.completed_items} / {r.total_items} items
                      </div>
                      <div className="text-[10px] text-[#718493] font-mono">
                        {r.error_count > 0 ? (
                          <span className="text-[#f87171]">{r.error_count} errors</span>
                        ) : (
                          <span className="text-[#74c69d]">0 errors</span>
                        )}
                      </div>
                    </div>

                    <a
                      href={`/api/runs/${r.run_id}/bundle`}
                      download
                      className="px-3 py-1.5 rounded bg-[#172832] hover:bg-[#203542] border border-[#263540] text-xs font-mono text-[#66d9e8] flex items-center gap-1.5 transition-colors"
                      title="Download complete audit bundle with inputs, raw outputs, and verification traces"
                    >
                      <Download size={13} />
                      Export Bundle
                    </a>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No evaluation runs yet"
              description="Configure and launch a run above to benchmark candidate language models."
            />
          )}
        </div>
      </div>
    </AppShell>
  )
}
