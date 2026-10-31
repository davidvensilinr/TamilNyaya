'use client'

import React, { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { AppShell } from '@/components/layout/AppShell'
import { api, ModelDetailResponse } from '@/lib/api'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { EmptyState } from '@/components/shared/EmptyState'
import { TamilText } from '@/components/shared/TamilText'
import { ArrowLeft, AlertTriangle, ShieldCheck, Cpu, Info } from 'lucide-react'

export default function ModelDetailPage() {
  const params = useParams()
  const rawModelId = params?.modelId as string
  const modelId = decodeURIComponent(rawModelId || '')

  const [model, setModel] = useState<ModelDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (modelId) loadModel()
  }, [modelId])

  async function loadModel() {
    setLoading(true)
    const res = await api.getModelDetail(modelId)
    if (res.data) {
      setModel(res.data)
    } else {
      setError(res.error || 'Failed to load model details')
    }
    setLoading(false)
  }

  return (
    <AppShell>
      <div className="space-y-6 max-w-6xl">
        <Link
          href="/leaderboard"
          className="inline-flex items-center gap-1.5 text-xs text-[#718493] hover:text-[#66d9e8] font-mono transition-colors"
        >
          <ArrowLeft size={13} /> Back to Leaderboard
        </Link>

        {loading ? (
          <div className="text-center py-16 text-xs text-[#8295a1]">Loading model metrics...</div>
        ) : error || !model ? (
          <EmptyState
            title="Model not found"
            description={error || `No evaluations found for model ${modelId}.`}
          />
        ) : (
          <div className="space-y-6">
            {/* Header */}
            <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] flex flex-col md:flex-row justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-xs font-bold text-[#66d9e8]">
                    Model Profile
                  </span>
                  <StatusBadge
                    status={model.is_fine_tuned_for_tamil_law ? 'ok' : 'degraded'}
                    label={model.is_fine_tuned_for_tamil_law ? 'Tamil Fine-Tuned' : 'General Purpose (Groq)'}
                  />
                </div>
                <h1 className="text-2xl font-bold text-[#eef5f7] font-mono">
                  {model.model_id}
                </h1>
                <p className="text-xs text-[#8295a1] mt-1 max-w-2xl leading-relaxed">
                  {model.description}
                </p>
              </div>

              <div className="text-xs font-mono text-right text-[#8295a1] flex flex-col justify-center">
                <div>Evaluated Items: <b className="text-[#e1edf0]">{model.total_items_evaluated}</b></div>
                <div>Evaluation Runs: <b className="text-[#e1edf0]">{model.run_count}</b></div>
                <div>Hosted On: <b className="text-[#66d9e8] capitalize">{model.provider}</b></div>
              </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-4 rounded bg-[#111a23] border border-[#263540]">
                <span className="text-[10px] uppercase font-bold text-[#718493] block">Citation Accuracy</span>
                <span className="text-xl font-mono font-bold text-[#74c69d]">
                  {model.citation_accuracy !== null ? `${(model.citation_accuracy * 100).toFixed(1)}%` : 'n/a'}
                </span>
              </div>
              <div className="p-4 rounded bg-[#111a23] border border-[#263540]">
                <span className="text-[10px] uppercase font-bold text-[#718493] block">Severity-3 Rate</span>
                <span className="text-xl font-mono font-bold text-[#e1a85a]">
                  {model.severity3_rate !== null ? `${(model.severity3_rate * 100).toFixed(1)}%` : 'n/a'}
                </span>
              </div>
              <div className="p-4 rounded bg-[#111a23] border border-[#263540]">
                <span className="text-[10px] uppercase font-bold text-[#718493] block">Jurisdiction Confusion</span>
                <span className="text-xl font-mono font-bold text-[#eaf4f5]">
                  {model.jurisdiction_confusion !== null ? `${(model.jurisdiction_confusion * 100).toFixed(1)}%` : 'n/a'}
                </span>
              </div>
              <div className="p-4 rounded bg-[#111a23] border border-[#263540]">
                <span className="text-[10px] uppercase font-bold text-[#718493] block">Adversarial Drop (Δ)</span>
                <span className="text-xl font-mono font-bold text-[#f87171]">
                  {model.adversarial_delta !== null ? `−${(model.adversarial_delta * 100).toFixed(1)}%` : 'n/a'}
                </span>
              </div>
            </div>

            {/* Category Breakdown & Fairness Gaps */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Category Breakdown */}
              <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-3">
                <h2 className="text-sm font-semibold text-[#e1edf0]">Error Category Breakdown</h2>
                <p className="text-[11px] text-[#8295a1]">
                  Distribution of detected errors across verification layers.
                </p>

                {Object.keys(model.category_breakdown).length > 0 ? (
                  <div className="space-y-2 pt-2">
                    {Object.entries(model.category_breakdown).map(([cat, count]) => (
                      <div key={cat} className="flex justify-between items-center text-xs p-2 rounded bg-[#0b1117] border border-[#20303a]">
                        <span className="font-mono text-[#c4d1d7]">{cat}</span>
                        <span className="font-mono font-bold text-[#e1a85a] bg-[#e1a85a]/10 px-2 py-0.5 rounded">
                          {count}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-xs text-[#718493] py-4">No specific error labels recorded.</div>
                )}
              </div>

              {/* Fairness Gaps */}
              <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-3">
                <h2 className="text-sm font-semibold text-[#e1edf0]">Jurisdiction Fairness Disaggregation</h2>
                <p className="text-[11px] text-[#8295a1]">
                  Checking whether the model performs systematically worse on Tamil Nadu state law compared to Central Indian law.
                </p>

                <div className="p-3 bg-[#0b1117] rounded border border-[#20303a] text-xs font-mono space-y-2 text-[#95a8b5]">
                  <div>Central Accuracy: <b className="text-[#e1edf0]">{model.fairness?.central_accuracy !== undefined ? `${(model.fairness.central_accuracy * 100).toFixed(1)}%` : 'n/a'}</b></div>
                  <div>Tamil Nadu Accuracy: <b className="text-[#e1edf0]">{model.fairness?.tamil_nadu_accuracy !== undefined ? `${(model.fairness.tamil_nadu_accuracy * 100).toFixed(1)}%` : 'n/a'}</b></div>
                  <div>Disparity Gap: <b className="text-[#e1a85a]">{model.fairness?.gap !== undefined ? `${(model.fairness.gap * 100).toFixed(1)}%` : 'n/a'}</b></div>
                </div>
              </div>
            </div>

            {/* Flagged High-Severity Examples */}
            <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-4">
              <h2 className="text-sm font-semibold text-[#e1edf0]">Flagged Severe Hallucination Samples</h2>
              <p className="text-xs text-[#8295a1]">
                High-impact errors (Severity 2 & 3) flagged by deterministic verification.
              </p>

              {model.flagged_examples.length > 0 ? (
                <div className="space-y-3">
                  {model.flagged_examples.map((ex, idx) => (
                    <div key={idx} className="p-3.5 bg-[#0b1117] rounded border border-[#20303a] text-xs space-y-2">
                      <div className="flex justify-between items-center text-[11px]">
                        <span className="font-mono text-[#66d9e8] font-bold">
                          Item {ex.item_id.substring(0, 8)}... · {ex.task_family}
                        </span>
                        <StatusBadge status={`severity ${ex.max_severity}`} label={`Severity ${ex.max_severity}`} />
                      </div>

                      <div className="text-[11px] text-[#718493]">
                        <b>Prompt snippet:</b> <span className="text-[#95a8b5] font-tamil">{ex.user_prompt_snippet}</span>
                      </div>

                      <div className="text-[11px] text-[#e1a85a] bg-[#e1a85a]/5 p-2 rounded border border-[#e1a85a]/20">
                        <b>Raw Model Answer:</b> <span className="font-tamil">{ex.raw_response_snippet}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-[#718493] py-4">No high-severity errors flagged for this model.</div>
              )}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
