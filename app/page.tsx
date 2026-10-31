'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { AppShell } from '@/components/layout/AppShell'
import { api, HealthInfo, DatasetStats, RunSummary, CoverageRow } from '@/lib/api'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { EmptyState } from '@/components/shared/EmptyState'
import {
  Database,
  FileSpreadsheet,
  PlaySquare,
  ShieldCheck,
  ArrowRight,
  Sparkles,
  Search,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
} from 'lucide-react'

export default function OverviewPage() {
  const [health, setHealth] = useState<HealthInfo | null>(null)
  const [stats, setStats] = useState<DatasetStats | null>(null)
  const [coverage, setCoverage] = useState<CoverageRow[]>([])
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadData() {
      setLoading(true)
      const [hRes, sRes, cRes, rRes] = await Promise.all([
        api.getHealth(),
        api.getDatasetStats(),
        api.getKBCoverage(),
        api.listRuns(5, 0),
      ])

      if (hRes.data) setHealth(hRes.data)
      if (sRes.data) setStats(sRes.data)
      if (cRes.data) setCoverage(cRes.data)
      if (rRes.data) setRuns(rRes.data)
      setLoading(false)
    }
    loadData()
  }, [])

  return (
    <AppShell>
      <div className="space-y-8 max-w-6xl">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-[#263540] pb-6">
          <div>
            <div className="flex items-center gap-2 text-[10px] uppercase font-bold tracking-widest text-[#718493] mb-1">
              <span className="w-2 h-2 rounded-full bg-[#66d9e8]" />
              System Status & Verification Console
            </div>
            <h1 className="text-2xl md:text-3xl font-bold text-[#eef5f7] tracking-tight">
              TamilNyaya-Bench
            </h1>
            <p className="text-xs text-[#8295a1] mt-1.5 max-w-2xl leading-relaxed">
              Evaluating small language models on Indian and Tamil Nadu law. Checking citations against real official statutes with zero tolerance for fabricated legal references.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <Link
              href="/check"
              className="px-3.5 py-2 rounded bg-[#111a23] hover:bg-[#182632] border border-[#263540] text-xs font-semibold text-[#e1edf0] flex items-center gap-1.5 transition-colors"
            >
              <CheckCircle2 size={14} className="text-[#66d9e8]" />
              Live Check
            </Link>
            <Link
              href="/runs"
              className="px-3.5 py-2 rounded bg-[#66d9e8] hover:bg-[#52c8d7] text-[#071117] text-xs font-bold flex items-center gap-1.5 transition-colors"
            >
              <PlaySquare size={14} />
              Evaluation Runs
            </Link>
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 rounded-lg bg-[#111a23] border border-[#263540]">
            <div className="text-[10px] uppercase font-bold text-[#718493] tracking-wider mb-2 flex items-center justify-between">
              <span>KB Provisions</span>
              <Database size={14} className="text-[#66d9e8]" />
            </div>
            <div className="text-2xl font-mono font-bold text-[#eaf4f5]">
              {health?.kb_record_count ?? (loading ? '...' : 0)}
            </div>
            <div className="text-[11px] text-[#6d818d] mt-1">
              From {coverage.length} real parsed Acts
            </div>
          </div>

          <div className="p-4 rounded-lg bg-[#111a23] border border-[#263540]">
            <div className="text-[10px] uppercase font-bold text-[#718493] tracking-wider mb-2 flex items-center justify-between">
              <span>Benchmark Items</span>
              <FileSpreadsheet size={14} className="text-[#66d9e8]" />
            </div>
            <div className="text-2xl font-mono font-bold text-[#eaf4f5]">
              {stats?.total_items ?? (loading ? '...' : 0)}
            </div>
            <div className="text-[11px] text-[#6d818d] mt-1">
              5 task families · 100% derived from KB
            </div>
          </div>

          <div className="p-4 rounded-lg bg-[#111a23] border border-[#263540]">
            <div className="text-[10px] uppercase font-bold text-[#718493] tracking-wider mb-2 flex items-center justify-between">
              <span>Adversarial Traps</span>
              <ShieldCheck size={14} className="text-[#e1a85a]" />
            </div>
            <div className="text-2xl font-mono font-bold text-[#e1a85a]">
              {stats?.adversarial_count ?? (loading ? '...' : 0)}
            </div>
            <div className="text-[11px] text-[#6d818d] mt-1">
              Wrong Acts, repealed & flipped traps
            </div>
          </div>

          <div className="p-4 rounded-lg bg-[#111a23] border border-[#263540]">
            <div className="text-[10px] uppercase font-bold text-[#718493] tracking-wider mb-2 flex items-center justify-between">
              <span>Evaluated Runs</span>
              <PlaySquare size={14} className="text-[#74c69d]" />
            </div>
            <div className="text-2xl font-mono font-bold text-[#eaf4f5]">
              {runs.length}
            </div>
            <div className="text-[11px] text-[#6d818d] mt-1">
              {runs.filter(r => r.status === 'done').length} completed
            </div>
          </div>
        </div>

        {/* Knowledge Base Coverage Status */}
        <div className="p-5 rounded-lg bg-[#101922] border border-[#263540]">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-[#e1edf0]">Official Legislation Coverage</h2>
              <p className="text-[11px] text-[#8295a1] mt-0.5">
                Provisions ingested from Tamil Nadu Gazette and India Code with complete provenance
              </p>
            </div>
            <Link
              href="/kb"
              className="text-xs text-[#66d9e8] hover:underline flex items-center gap-1 font-mono"
            >
              Explore KB <ArrowRight size={12} />
            </Link>
          </div>

          {coverage.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-[#20303a] text-[#718493] font-medium text-[11px]">
                    <th className="py-2.5 px-3">Act Name</th>
                    <th className="py-2.5 px-3">Jurisdiction</th>
                    <th className="py-2.5 px-3">Sections Ingested</th>
                    <th className="py-2.5 px-3">Declared in Source</th>
                    <th className="py-2.5 px-3">Coverage %</th>
                    <th className="py-2.5 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1b2832]">
                  {coverage.map((row) => (
                    <tr key={row.act_name_en} className="hover:bg-[#131d27]/60">
                      <td className="py-2.5 px-3 font-medium text-[#c4d1d7]">
                        {row.act_name_en}
                      </td>
                      <td className="py-2.5 px-3">
                        <StatusBadge
                          status={row.jurisdiction === 'Tamil Nadu' ? 'running' : 'completed'}
                          label={row.jurisdiction}
                        />
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[#e1edf0]">
                        {row.sections_ingested}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[#8295a1]">
                        {row.sections_in_source ?? 'Unknown'}
                      </td>
                      <td className="py-2.5 px-3 font-mono">
                        {row.coverage_pct ? `${row.coverage_pct}%` : 'Partial'}
                      </td>
                      <td className="py-2.5 px-3">
                        <StatusBadge status={row.complete ? 'done' : 'pending'} label={row.complete ? 'Full' : 'Partial'} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="No Acts ingested yet"
              description="Run the ingestion pipeline to parse official legislation into the knowledge base."
            />
          )}
        </div>

        {/* Two Column Section: Benchmark Breakdown & Recent Runs */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Benchmark Task Breakdown */}
          <div className="p-5 rounded-lg bg-[#101922] border border-[#263540]">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-[#e1edf0]">Benchmark Task Families</h2>
              <Link href="/dataset" className="text-xs text-[#66d9e8] hover:underline font-mono">
                View items ({stats?.total_items ?? 0})
              </Link>
            </div>

            {stats?.by_task_family ? (
              <div className="space-y-3">
                {Object.entries(stats.by_task_family).map(([family, count]) => (
                  <div key={family} className="flex items-center justify-between p-2.5 rounded bg-[#131d26] border border-[#1d2b36] text-xs">
                    <div>
                      <span className="font-semibold text-[#c4d1d7] capitalize font-mono text-[11px]">
                        {family.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <span className="font-mono font-bold text-[#66d9e8] bg-[#66d9e8]/10 px-2 py-0.5 rounded">
                      {count} items
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No items generated"
                description="Generate benchmark items from ingested KB records."
              />
            )}
          </div>

          {/* Recent Runs */}
          <div className="p-5 rounded-lg bg-[#101922] border border-[#263540]">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-[#e1edf0]">Evaluation Runs</h2>
              <Link href="/runs" className="text-xs text-[#66d9e8] hover:underline font-mono">
                Run console
              </Link>
            </div>

            {runs.length > 0 ? (
              <div className="space-y-3">
                {runs.map((r) => (
                  <Link
                    key={r.run_id}
                    href={`/runs`}
                    className="block p-3 rounded bg-[#131d26] hover:bg-[#172531] border border-[#1d2b36] transition-colors"
                  >
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-mono text-[#66d9e8] font-medium">
                        {r.model_id}
                      </span>
                      <StatusBadge status={r.status} />
                    </div>
                    <div className="text-[11px] text-[#718590] mt-1.5 flex justify-between">
                      <span>{r.completed_items} / {r.total_items} evaluated</span>
                      <span>{new Date(r.started_at).toLocaleDateString()}</span>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No evaluation runs executed yet"
                description="Start your first evaluation run from the Run Console to evaluate models against the benchmark."
                action={
                  <Link
                    href="/runs"
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-[#172832] border border-[#263540] text-xs text-[#66d9e8] hover:bg-[#1d3340] font-medium"
                  >
                    Go to Run Console <ArrowRight size={12} />
                  </Link>
                }
              />
            )}
          </div>
        </div>
      </div>
    </AppShell>
  )
}
