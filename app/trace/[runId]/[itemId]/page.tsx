'use client'

import React, { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { AppShell } from '@/components/layout/AppShell'
import { api, TraceData } from '@/lib/api'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { EmptyState } from '@/components/shared/EmptyState'
import { TamilText } from '@/components/shared/TamilText'
import { ArrowLeft, CheckCircle2, AlertTriangle, Layers, Clock, Cpu } from 'lucide-react'

export default function TracePage() {
  const params = useParams()
  const runId = params?.runId as string
  const itemId = params?.itemId as string

  const [trace, setTrace] = useState<TraceData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (runId && itemId) {
      loadTrace()
    }
  }, [runId, itemId])

  async function loadTrace() {
    setLoading(true)
    const res = await api.getTrace(runId, itemId)
    if (res.data) {
      setTrace(res.data)
    } else {
      setError(res.error || 'Failed to load trace')
    }
    setLoading(false)
  }

  return (
    <AppShell>
      <div className="space-y-6 max-w-5xl">
        <Link
          href="/runs"
          className="inline-flex items-center gap-1.5 text-xs text-[#718493] hover:text-[#66d9e8] font-mono transition-colors"
        >
          <ArrowLeft size={13} /> Back to Runs
        </Link>

        {loading ? (
          <div className="text-center py-16 text-xs text-[#8295a1]">Loading verification trace...</div>
        ) : error || !trace ? (
          <EmptyState
            title="Verification trace not found"
            description={error || `No recorded result found for run ${runId} and item ${itemId}.`}
          />
        ) : (
          <div className="space-y-6">
            {/* Header */}
            <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] flex flex-col md:flex-row justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-xs font-bold text-[#66d9e8]">
                    Verification Trace
                  </span>
                  <StatusBadge
                    status={trace.max_severity ? `severity ${trace.max_severity}` : 'ok'}
                    label={trace.max_severity ? `Severity ${trace.max_severity}` : 'Clean · No Hallucination'}
                  />
                </div>
                <h1 className="text-xl font-bold text-[#eef5f7]">
                  Item {itemId.substring(0, 12)}...
                </h1>
                <div className="text-[11px] text-[#718493] font-mono mt-1">
                  Run ID: {runId}
                </div>
              </div>

              <div className="flex items-center gap-4 text-xs font-mono text-[#8295a1]">
                <div className="flex items-center gap-1.5">
                  <Clock size={14} className="text-[#718493]" />
                  <span>{trace.latency_ms ?? '...'} ms</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Cpu size={14} className="text-[#718493]" />
                  <span>{trace.completion_tokens ?? '...'} tokens</span>
                </div>
              </div>
            </div>

            {/* Prompts and Response */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-lg bg-[#111a23] border border-[#263540] space-y-2">
                <div className="text-[10px] uppercase font-bold text-[#718493] tracking-wider">
                  User Prompt Delivered to Model
                </div>
                <div className="p-3 bg-[#0b1117] rounded border border-[#20303a] text-xs font-mono text-[#c4d1d7] leading-relaxed whitespace-pre-wrap max-h-60 overflow-y-auto">
                  <TamilText>{trace.user_prompt}</TamilText>
                </div>
              </div>

              <div className="p-4 rounded-lg bg-[#111a23] border border-[#263540] space-y-2">
                <div className="text-[10px] uppercase font-bold text-[#718493] tracking-wider">
                  Raw Model Response (Untouched)
                </div>
                <div className="p-3 bg-[#0b1117] rounded border border-[#20303a] text-xs font-mono text-[#c4d1d7] leading-relaxed whitespace-pre-wrap max-h-60 overflow-y-auto">
                  <TamilText>{trace.raw_response}</TamilText>
                </div>
              </div>
            </div>

            {/* Layer 1 Verification Details */}
            <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-4">
              <div className="flex items-center justify-between border-b border-[#20303a] pb-3">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-[#66d9e8]/10 text-[#66d9e8] text-[11px] font-mono font-bold flex items-center justify-center">
                    L1
                  </span>
                  <h2 className="text-sm font-semibold text-[#e1edf0]">
                    Layer 1: Deterministic Citation Verification
                  </h2>
                </div>
                <span className="text-[11px] text-[#718493] font-mono">
                  Exact regex + KB lookup
                </span>
              </div>

              {trace.layer1_result ? (
                <div className="space-y-3">
                  <div className="text-xs text-[#8295a1]">
                    Citations Found: <b>{trace.layer1_result.total_citations}</b> · Correct: <b>{trace.layer1_result.correct_citations}</b>
                  </div>

                  {trace.layer1_result.verdicts?.map((v: any, idx: number) => (
                    <div key={idx} className="p-3 bg-[#0b1117] rounded border border-[#20303a] text-xs space-y-1.5 font-mono">
                      <div className="flex justify-between items-center">
                        <span className="text-[#66d9e8] font-bold">
                          "{v.raw_text}"
                        </span>
                        <StatusBadge status={v.verdict || 'CORRECT'} />
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px] text-[#718493] pt-1 border-t border-[#1b2832]">
                        <div>Branch: <span className="text-[#c4d1d7]">{v.branch_fired}</span></div>
                        <div>Normalized: <span className="text-[#c4d1d7]">{v.normalized_section}</span></div>
                        <div>Fuzzy Score: <span className="text-[#c4d1d7]">{v.fuzzy_score ?? 'exact'}</span></div>
                        <div>Severity: <span className="text-[#e1a85a] font-bold">{v.severity}</span></div>
                      </div>

                      <div className="text-[10px] text-[#556977]">
                        Lookup: {v.lookup_description}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-[#8295a1]">No citation verification record.</div>
              )}
            </div>

            {/* Layer 2 NLI Faithfulness Details */}
            <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-3">
              <div className="flex items-center justify-between border-b border-[#20303a] pb-3">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-[#7aa2f7]/10 text-[#7aa2f7] text-[11px] font-mono font-bold flex items-center justify-center">
                    L2
                  </span>
                  <h2 className="text-sm font-semibold text-[#e1edf0]">
                    Layer 2: NLI Faithfulness Scorer
                  </h2>
                </div>
                <span className="text-[11px] text-[#718493] font-mono">
                  Atomic claim entailment
                </span>
              </div>

              {trace.layer2_result ? (
                <div className="text-xs space-y-2">
                  <div className="flex items-center gap-4 text-[#8295a1]">
                    <span>Score: <b className="text-[#7aa2f7] font-mono">{trace.layer2_result.faithfulness_score ?? 'n/a'}</b></span>
                    <span>Entailed: <b>{trace.layer2_result.entailed_count ?? 0}</b></span>
                    <span>Neutral: <b>{trace.layer2_result.neutral_count ?? 0}</b></span>
                    <span>Contradicted: <b>{trace.layer2_result.contradicted_count ?? 0}</b></span>
                  </div>
                </div>
              ) : (
                <div className="text-xs text-[#8295a1]">
                  NLI verification was not applicable or LLM was disabled.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
