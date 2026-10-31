'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { AppShell } from '@/components/layout/AppShell'
import { api, LeaderboardResponse, ModelMetricRow } from '@/lib/api'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { EmptyState } from '@/components/shared/EmptyState'
import { Trophy, HelpCircle, ArrowRight, ShieldAlert, Info } from 'lucide-react'

export default function LeaderboardPage() {
  const [data, setData] = useState<LeaderboardResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadLeaderboard()
  }, [])

  async function loadLeaderboard() {
    setLoading(true)
    const res = await api.getLeaderboard()
    if (res.data) setData(res.data)
    setLoading(false)
  }

  return (
    <AppShell>
      <div className="space-y-6 max-w-6xl">
        {/* Header */}
        <div className="border-b border-[#263540] pb-5">
          <div className="text-[10px] uppercase font-bold tracking-widest text-[#718493] mb-1">
            Comparative Hallucination Metrics
          </div>
          <h1 className="text-2xl font-bold text-[#eef5f7] tracking-tight">
            Model Leaderboard & Rankings
          </h1>
          <p className="text-xs text-[#8295a1] mt-1 max-w-2xl leading-relaxed">
            Comparing candidate models across citation accuracy, severity-3 hallucination rate, and adversarial degradation. All numbers include 95% percentile bootstrap confidence intervals.
          </p>
        </div>

        {/* Warning Banner */}
        <div className="p-3.5 bg-[#101922] border border-[#20303a] rounded-lg text-xs text-[#8295a1] flex items-start gap-3">
          <Info size={16} className="text-[#66d9e8] mt-0.5 flex-shrink-0" />
          <div className="space-y-1">
            <span className="font-semibold text-[#c4d1d7]">Rigorous Evaluation Transparency</span>
            <p className="text-[11px] leading-relaxed">
              All models evaluated are general-purpose open models hosted on Groq, not fine-tuned for Tamil law. Rankings sort by lowest Severity-3 Hallucination Rate.
            </p>
          </div>
        </div>

        {/* Leaderboard Table */}
        {loading ? (
          <div className="text-center py-16 text-xs text-[#8295a1]">Computing live metrics and bootstrap CIs...</div>
        ) : data && data.models.length > 0 ? (
          <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-4">
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-[#20303a] text-[#718493] font-medium text-[11px]">
                    <th className="py-2.5 px-3">Model</th>
                    <th className="py-2.5 px-3">Citation Accuracy (95% CI)</th>
                    <th className="py-2.5 px-3">Severity-3 Hallucination Rate</th>
                    <th className="py-2.5 px-3">Jurisdiction Confusion</th>
                    <th className="py-2.5 px-3">Adversarial Drop (Δ)</th>
                    <th className="py-2.5 px-3">Evaluated Items</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1b2832]">
                  {data.models.map((m, idx) => (
                    <tr key={m.model_id} className="hover:bg-[#131d27]/60">
                      <td className="py-3 px-3">
                        <Link
                          href={`/models/${encodeURIComponent(m.model_id)}`}
                          className="group flex flex-col"
                        >
                          <span className="font-mono font-bold text-[#66d9e8] group-hover:underline flex items-center gap-1.5">
                            <span className="w-4 h-4 rounded bg-[#172832] text-[#8196a0] text-[10px] flex items-center justify-center font-bold">
                              {idx + 1}
                            </span>
                            {m.model_id}
                          </span>
                          <span className="text-[10px] text-[#627783] mt-0.5 max-w-xs truncate">
                            {m.display_name}
                          </span>
                        </Link>
                      </td>

                      <td className="py-3 px-3 font-mono">
                        {m.citation_accuracy !== null ? (
                          <div>
                            <span className="font-bold text-[#74c69d]">
                              {(m.citation_accuracy * 100).toFixed(1)}%
                            </span>
                            {m.citation_accuracy_ci_low !== null && (
                              <span className="text-[10px] text-[#6d818d] block">
                                [{(m.citation_accuracy_ci_low * 100).toFixed(1)}%, {(m.citation_accuracy_ci_high! * 100).toFixed(1)}%]
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-[#627783]">n/a</span>
                        )}
                      </td>

                      <td className="py-3 px-3 font-mono">
                        {m.severity3_rate !== null ? (
                          <div>
                            <span className="font-bold text-[#e1a85a]">
                              {(m.severity3_rate * 100).toFixed(1)}%
                            </span>
                            {m.severity3_rate_ci_low !== null && (
                              <span className="text-[10px] text-[#6d818d] block">
                                [{(m.severity3_rate_ci_low * 100).toFixed(1)}%, {(m.severity3_rate_ci_high! * 100).toFixed(1)}%]
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-[#627783]">n/a</span>
                        )}
                      </td>

                      <td className="py-3 px-3 font-mono">
                        {m.jurisdiction_confusion !== null ? (
                          <span>{(m.jurisdiction_confusion * 100).toFixed(1)}%</span>
                        ) : (
                          <span className="text-[#627783]">n/a</span>
                        )}
                      </td>

                      <td className="py-3 px-3 font-mono">
                        {m.adversarial_delta !== null ? (
                          <span className={m.adversarial_delta > 0.1 ? 'text-[#f87171]' : 'text-[#c4d1d7]'}>
                            −{(m.adversarial_delta * 100).toFixed(1)}%
                          </span>
                        ) : (
                          <span className="text-[#627783]">n/a</span>
                        )}
                      </td>

                      <td className="py-3 px-3 font-mono text-[#8295a1]">
                        {m.total_items_evaluated} ({m.run_count} runs)
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="text-[11px] text-[#718493] pt-3 border-t border-[#20303a] flex justify-between">
              <span>{data.note}</span>
              <span className="font-mono">
                Bootstrap: {data.bootstrap_resamples} resamples · seed {data.bootstrap_seed}
              </span>
            </div>
          </div>
        ) : (
          <EmptyState
            title="No completed evaluation runs yet"
            description="Run model evaluations from the Run Console to populate the leaderboard with real verifiable scores."
            action={
              <Link
                href="/runs"
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded bg-[#172832] hover:bg-[#203542] border border-[#263540] text-xs font-semibold text-[#66d9e8] transition-colors"
              >
                Go to Run Console <ArrowRight size={13} />
              </Link>
            }
          />
        )}
      </div>
    </AppShell>
  )
}
