'use client'

import React, { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { api, TaxonomyCategory, MetricExplanation } from '@/lib/api'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { BookOpen, FlaskConical, Scale, ShieldAlert, CheckCircle2, ChevronRight } from 'lucide-react'

export default function MethodologyPage() {
  const [taxonomy, setTaxonomy] = useState<TaxonomyCategory[]>([])
  const [metrics, setMetrics] = useState<Record<string, MetricExplanation>>({})
  const [selectedMetric, setSelectedMetric] = useState<string>('citation_accuracy')
  const [loading, setLoading] = useState(true)

  const metricNames = [
    'citation_accuracy',
    'severity3_rate',
    'faithfulness_score',
    'jurisdiction_confusion',
    'adversarial_robustness',
  ]

  useEffect(() => {
    async function loadData() {
      setLoading(true)
      const taxRes = await api.getTaxonomy()
      if (taxRes.data) setTaxonomy(taxRes.data.categories)

      const metricPromises = metricNames.map((name) => api.explainMetric(name))
      const metricResults = await Promise.all(metricPromises)

      const map: Record<string, MetricExplanation> = {}
      metricResults.forEach((res, i) => {
        if (res.data) map[metricNames[i]] = res.data
      })
      setMetrics(map)
      setLoading(false)
    }
    loadData()
  }, [])

  return (
    <AppShell>
      <div className="space-y-8 max-w-6xl">
        {/* Header */}
        <div className="border-b border-[#263540] pb-5">
          <div className="text-[10px] uppercase font-bold tracking-widest text-[#718493] mb-1">
            Research Reproducibility & Formulas
          </div>
          <h1 className="text-2xl font-bold text-[#eef5f7] tracking-tight">
            Methodology & Error Taxonomy
          </h1>
          <p className="text-xs text-[#8295a1] mt-1 max-w-2xl leading-relaxed">
            Every metric displayed in TamilNyaya-Bench is inspectable, computed on-demand, and traceable to exact code formulas. No hardcoded or precomputed values are permitted.
          </p>
        </div>

        {/* Metric Explanation Interactive Section */}
        <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-4">
          <div className="flex items-center gap-2 border-b border-[#20303a] pb-3">
            <FlaskConical size={16} className="text-[#66d9e8]" />
            <h2 className="text-sm font-semibold text-[#eef5f7]">Inspectable Metric Formulas</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-1">
              {metricNames.map((key) => {
                const m = metrics[key]
                return (
                  <button
                    key={key}
                    onClick={() => setSelectedMetric(key)}
                    className={`w-full text-left px-3 py-2 rounded text-xs transition-colors flex justify-between items-center ${
                      selectedMetric === key
                        ? 'bg-[#172832] text-[#66d9e8] font-bold'
                        : 'text-[#8295a1] hover:bg-[#131d26] hover:text-[#c4d1d7]'
                    }`}
                  >
                    <span>{m?.name || key.replace(/_/g, ' ')}</span>
                    {selectedMetric === key && <ChevronRight size={14} />}
                  </button>
                )
              })}
            </div>

            {metrics[selectedMetric] && (
              <div className="md:col-span-2 p-4 bg-[#0b1117] rounded border border-[#20303a] space-y-3 text-xs">
                <div>
                  <h3 className="text-sm font-bold text-[#e1edf0]">
                    {metrics[selectedMetric].name}
                  </h3>
                  <p className="text-[11px] text-[#8295a1] mt-1">
                    {metrics[selectedMetric].description}
                  </p>
                </div>

                <div>
                  <span className="text-[10px] uppercase font-bold text-[#718493] block mb-1">
                    Exact Mathematical Formula
                  </span>
                  <div className="p-2.5 bg-[#111a23] rounded border border-[#263540] font-mono text-sm text-[#66d9e8]">
                    {metrics[selectedMetric].formula}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                  <div>
                    <span className="text-[#627783] block text-[10px]">Numerator:</span>
                    <span className="text-[#c4d1d7]">{metrics[selectedMetric].numerator}</span>
                  </div>
                  <div>
                    <span className="text-[#627783] block text-[10px]">Denominator:</span>
                    <span className="text-[#c4d1d7]">{metrics[selectedMetric].denominator}</span>
                  </div>
                </div>

                <div className="pt-2 border-t border-[#1b2832] text-[10px] text-[#6d818d] font-mono">
                  Implementation: <code>{metrics[selectedMetric].implementation}</code>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Error Taxonomy Section */}
        <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-4">
          <div className="flex items-center justify-between border-b border-[#20303a] pb-3">
            <div className="flex items-center gap-2">
              <Scale size={16} className="text-[#66d9e8]" />
              <h2 className="text-sm font-semibold text-[#eef5f7]">Legal Hallucination Taxonomy v1.0.0</h2>
            </div>
            <span className="text-xs font-mono text-[#718493]">
              {taxonomy.length} defined categories
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-[#20303a] text-[#718493] font-medium text-[11px]">
                  <th className="py-2.5 px-3">Category Name</th>
                  <th className="py-2.5 px-3">Group</th>
                  <th className="py-2.5 px-3">Severity</th>
                  <th className="py-2.5 px-3">Verification Layer</th>
                  <th className="py-2.5 px-3">Description</th>
                  <th className="py-2.5 px-3">Rule Reference</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1b2832]">
                {taxonomy.map((c) => (
                  <tr key={c.category} className="hover:bg-[#131d27]/60">
                    <td className="py-3 px-3 font-mono font-bold text-[#c4d1d7]">
                      {c.category}
                    </td>
                    <td className="py-3 px-3 text-[#95a8b5]">
                      {c.group}
                    </td>
                    <td className="py-3 px-3">
                      <StatusBadge
                        status={`severity ${c.severity}`}
                        label={`Sev ${c.severity} · ${c.severity_label}`}
                      />
                    </td>
                    <td className="py-3 px-3 font-mono text-[#66d9e8]">
                      {c.layer}
                    </td>
                    <td className="py-3 px-3 text-[11px] text-[#8295a1] max-w-sm">
                      {c.description}
                    </td>
                    <td className="py-3 px-3 font-mono text-[10px] text-[#627783]">
                      {c.rule_reference}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
