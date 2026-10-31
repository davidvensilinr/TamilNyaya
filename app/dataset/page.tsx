'use client'

import React, { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { api, BenchmarkItem, DatasetStats } from '@/lib/api'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { EmptyState } from '@/components/shared/EmptyState'
import { TamilText } from '@/components/shared/TamilText'
import { Filter, Sparkles, AlertTriangle, ShieldCheck, ChevronRight, FileSpreadsheet } from 'lucide-react'

export default function DatasetPage() {
  const [items, setItems] = useState<BenchmarkItem[]>([])
  const [stats, setStats] = useState<DatasetStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [generateMsg, setGenerateMsg] = useState<string | null>(null)

  // Filters
  const [taskFamily, setTaskFamily] = useState('')
  const [jurisdiction, setJurisdiction] = useState('')
  const [adversarialOnly, setAdversarialOnly] = useState<boolean | undefined>(undefined)
  const [selectedItem, setSelectedItem] = useState<BenchmarkItem | null>(null)

  useEffect(() => {
    loadData()
  }, [taskFamily, jurisdiction, adversarialOnly])

  async function loadData() {
    setLoading(true)
    const [itemsRes, statsRes] = await Promise.all([
      api.getItems({
        task_family: taskFamily || undefined,
        jurisdiction: jurisdiction || undefined,
        is_adversarial: adversarialOnly,
        limit: 100,
      }),
      api.getDatasetStats(),
    ])

    if (itemsRes.data) setItems(itemsRes.data)
    if (statsRes.data) setStats(statsRes.data)
    setLoading(false)
  }

  async function handleGenerate() {
    setGenerating(true)
    setGenerateMsg(null)
    const res = await api.generateItems(42)
    if (res.data) {
      setGenerateMsg(`Generated ${res.data.total_generated} benchmark items across 5 families.`)
      await loadData()
    } else {
      setGenerateMsg(res.error || 'Generation failed')
    }
    setGenerating(false)
  }

  return (
    <AppShell>
      <div className="space-y-6 max-w-6xl">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-[#263540] pb-5">
          <div>
            <div className="text-[10px] uppercase font-bold tracking-widest text-[#718493] mb-1">
              Benchmark Dataset · Auditable Item Suites
            </div>
            <h1 className="text-2xl font-bold text-[#eef5f7] tracking-tight">
              Benchmark Dataset Explorer
            </h1>
            <p className="text-xs text-[#8295a1] mt-1 max-w-2xl leading-relaxed">
              Every item is programmatically generated from real KB records using documented templates. Extractive gold answers ensure zero LLM hallucination in the test set.
            </p>
          </div>

          <button
            onClick={handleGenerate}
            disabled={generating}
            className="px-3.5 py-2 rounded bg-[#172832] hover:bg-[#203542] border border-[#263540] text-xs font-semibold text-[#66d9e8] flex items-center gap-1.5 transition-colors disabled:opacity-50"
          >
            <Sparkles size={14} />
            {generating ? 'Generating Items...' : 'Regenerate Items'}
          </button>
        </div>

        {generateMsg && (
          <div className="p-3 bg-[#66d9e8]/10 border border-[#66d9e8]/30 rounded text-xs text-[#66d9e8]">
            {generateMsg}
          </div>
        )}

        {/* Stats Grid */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 rounded bg-[#111a23] border border-[#263540]">
              <span className="text-[10px] uppercase font-bold text-[#718493] block">Total Items</span>
              <span className="text-xl font-mono font-bold text-[#e1edf0]">{stats.total_items}</span>
            </div>
            <div className="p-3 rounded bg-[#111a23] border border-[#263540]">
              <span className="text-[10px] uppercase font-bold text-[#718493] block">Adversarial Traps</span>
              <span className="text-xl font-mono font-bold text-[#e1a85a]">{stats.adversarial_count}</span>
            </div>
            <div className="p-3 rounded bg-[#111a23] border border-[#263540]">
              <span className="text-[10px] uppercase font-bold text-[#718493] block">Derived Gold</span>
              <span className="text-xl font-mono font-bold text-[#74c69d]">{stats.derived_gold_count}</span>
            </div>
            <div className="p-3 rounded bg-[#111a23] border border-[#263540]">
              <span className="text-[10px] uppercase font-bold text-[#718493] block">Human Labeled</span>
              <span className="text-xl font-mono font-bold text-[#8295a1]">{stats.human_labeled_count}</span>
            </div>
          </div>
        )}

        {/* Filter Strip */}
        <div className="flex flex-wrap gap-3 items-center justify-between p-3 rounded-lg bg-[#101922] border border-[#263540] text-xs">
          <div className="flex flex-wrap gap-2 items-center">
            <Filter size={14} className="text-[#718493]" />
            <select
              value={taskFamily}
              onChange={(e) => setTaskFamily(e.target.value)}
              className="bg-[#0b1117] border border-[#20303a] rounded py-1 px-2.5 text-[#c4d1d7]"
            >
              <option value="">All Task Families</option>
              <option value="citation_completion">Citation Completion</option>
              <option value="grounded_qa">Grounded QA</option>
              <option value="closed_book_legal_qa">Closed-Book Legal QA</option>
              <option value="jurisdiction_probe">Jurisdiction Probe</option>
              <option value="adversarial">Adversarial Traps</option>
            </select>

            <select
              value={jurisdiction}
              onChange={(e) => setJurisdiction(e.target.value)}
              className="bg-[#0b1117] border border-[#20303a] rounded py-1 px-2.5 text-[#c4d1d7]"
            >
              <option value="">All Jurisdictions</option>
              <option value="Central">Central</option>
              <option value="Tamil Nadu">Tamil Nadu</option>
            </select>

            <button
              onClick={() => setAdversarialOnly(adversarialOnly ? undefined : true)}
              className={`px-2.5 py-1 rounded border text-xs font-mono transition-colors ${
                adversarialOnly
                  ? 'bg-[#e1a85a]/20 border-[#e1a85a] text-[#e1a85a]'
                  : 'bg-[#0b1117] border-[#20303a] text-[#8295a1]'
              }`}
            >
              Traps Only
            </button>
          </div>

          <span className="text-[11px] text-[#718493] font-mono">
            Showing {items.length} items
          </span>
        </div>

        {/* Items Grid */}
        {loading ? (
          <div className="text-center py-12 text-xs text-[#8295a1]">Loading items...</div>
        ) : items.length > 0 ? (
          <div className="space-y-3">
            {items.map((item) => (
              <div
                key={item.item_id}
                onClick={() => setSelectedItem(item)}
                className={`p-4 rounded-lg bg-[#111a23] hover:bg-[#15222e] border transition-colors cursor-pointer ${
                  selectedItem?.item_id === item.item_id ? 'border-[#66d9e8]' : 'border-[#263540]'
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-bold text-[#66d9e8] capitalize">
                      {item.task_family.replace(/_/g, ' ')}
                    </span>
                    <StatusBadge status={item.jurisdiction} />
                    {item.is_adversarial && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#e1a85a]/10 border border-[#e1a85a]/30 text-[#e1a85a]">
                        Trap
                      </span>
                    )}
                    <span className="text-[10px] font-mono text-[#6d818d]">
                      template: {item.template_name}
                    </span>
                  </div>
                  <span className="font-mono text-[10px] text-[#6d818d]">
                    ID: {item.item_id.substring(0, 8)}...
                  </span>
                </div>

                <div className="text-xs text-[#c4d1d7] mb-2 line-clamp-2">
                  {item.gold_derivation}
                </div>

                <div className="flex items-center justify-between text-[11px] text-[#718493] pt-2 border-t border-[#1d2b36]">
                  <span>Topic: <b className="text-[#a4b5bf]">{item.topic_tag}</b></span>
                  <span className="font-mono text-[#66d9e8] text-[10px]">
                    Gold: {item.gold_status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No benchmark items found"
            description="No items match your filter criteria. Try resetting filters."
          />
        )}

        {/* Item Detail Modal */}
        {selectedItem && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-[#101922] border border-[#263540] rounded-xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-6 space-y-4">
              <div className="flex items-start justify-between border-b border-[#20303a] pb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-bold text-[#66d9e8] capitalize">
                      {selectedItem.task_family.replace(/_/g, ' ')}
                    </span>
                    <StatusBadge status={selectedItem.jurisdiction} />
                    {selectedItem.is_adversarial && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#e1a85a]/10 border border-[#e1a85a]/30 text-[#e1a85a]">
                        Adversarial
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-[#718493] font-mono mt-1">
                    Item ID: {selectedItem.item_id}
                  </div>
                </div>
                <button
                  onClick={() => setSelectedItem(null)}
                  className="text-[#718493] hover:text-[#eef5f7] text-lg font-bold p-1"
                >
                  ×
                </button>
              </div>

              <div className="space-y-3">
                <div>
                  <div className="text-[10px] uppercase font-bold text-[#718493] mb-1">
                    Gold Derivation & Prompt Description
                  </div>
                  <div className="p-3 bg-[#0b1117] rounded border border-[#20303a] text-xs leading-relaxed text-[#d7e0e8]">
                    {selectedItem.gold_derivation}
                  </div>
                </div>

                <div>
                  <div className="text-[10px] uppercase font-bold text-[#718493] mb-1">
                    Structured Gold Answer
                  </div>
                  <pre className="p-3 bg-[#0b1117] rounded border border-[#20303a] text-xs font-mono text-[#8ca0ad] overflow-x-auto whitespace-pre-wrap">
                    {selectedItem.gold_answer ? JSON.stringify(JSON.parse(selectedItem.gold_answer), null, 2) : 'null'}
                  </pre>
                </div>

                {selectedItem.is_adversarial && selectedItem.adversarial_perturbation && (
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[#e1a85a] mb-1">
                      Perturbation Details (Trap Specification)
                    </div>
                    <pre className="p-3 bg-[#e1a85a]/5 rounded border border-[#e1a85a]/30 text-xs font-mono text-[#e1a85a] overflow-x-auto whitespace-pre-wrap">
                      {JSON.stringify(JSON.parse(selectedItem.adversarial_perturbation), null, 2)}
                    </pre>
                  </div>
                )}

                <div className="border-t border-[#20303a] pt-3">
                  <div className="text-[10px] uppercase font-bold text-[#718493] mb-2">
                    Provenance Metadata
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs font-mono bg-[#0b1117] p-3 rounded border border-[#20303a]">
                    <div>
                      <span className="text-[#627783] block text-[10px]">Primary KB Record ID</span>
                      <span className="text-[#95a8b5] break-all">{selectedItem.primary_source_record_id}</span>
                    </div>
                    <div>
                      <span className="text-[#627783] block text-[10px]">Generator Script</span>
                      <span className="text-[#66d9e8]">{selectedItem.generator_script}</span>
                    </div>
                    <div>
                      <span className="text-[#627783] block text-[10px]">Template Name</span>
                      <span className="text-[#95a8b5]">{selectedItem.template_name}</span>
                    </div>
                    <div>
                      <span className="text-[#627783] block text-[10px]">Template Version</span>
                      <span className="text-[#95a8b5]">{selectedItem.template_version}</span>
                    </div>
                  </div>
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    onClick={() => setSelectedItem(null)}
                    className="px-4 py-1.5 bg-[#172832] hover:bg-[#203542] rounded text-xs font-medium text-[#c4d1d7]"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
