'use client'

import React, { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { api, AnnotationItem, CalibrationRow } from '@/lib/api'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { EmptyState } from '@/components/shared/EmptyState'
import { Users, Scale, FileText, CheckCircle2, AlertTriangle, Download, Upload } from 'lucide-react'

export default function AnnotationsPage() {
  const [tab, setTab] = useState<'calibration' | 'annotations' | 'label'>('calibration')
  const [calibration, setCalibration] = useState<CalibrationRow[]>([])
  const [annotations, setAnnotations] = useState<AnnotationItem[]>([])
  const [disagreements, setDisagreements] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  // Label Form
  const [itemId, setItemId] = useState('')
  const [annotatorId, setAnnotatorId] = useState('annotator_1')
  const [severity, setSeverity] = useState(1)
  const [selectedCats, setSelectedCats] = useState<string[]>([])
  const [notes, setNotes] = useState('')
  const [submitMsg, setSubmitMsg] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    const [cRes, aRes, dRes] = await Promise.all([
      api.getCalibration(),
      api.getAnnotations({ limit: 50 }),
      api.getDisagreements(),
    ])
    if (cRes.data) setCalibration(cRes.data)
    if (aRes.data) setAnnotations(aRes.data)
    if (dRes.data) setDisagreements(dRes.data)
    setLoading(false)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitMsg(null)

    const res = await api.createAnnotation({
      item_id: itemId,
      annotator_id: annotatorId,
      error_categories: selectedCats,
      severity,
      notes,
    })

    if (res.data) {
      setSubmitMsg('Human annotation saved successfully!')
      setItemId('')
      setNotes('')
      setSelectedCats([])
      await loadData()
    } else {
      setSubmitMsg(res.error || 'Failed to submit annotation')
    }
  }

  const categoryOptions = [
    'CitationFabrication',
    'WrongSection',
    'JurisdictionConflation',
    'ObsoleteLawAsCurrent',
    'UnsupportedElaboration',
    'TerminologyMistranslation',
    'WrongLegalConsequence',
    'PartialHallucination',
  ]

  return (
    <AppShell>
      <div className="space-y-6 max-w-6xl">
        {/* Header */}
        <div className="border-b border-[#263540] pb-5">
          <div className="text-[10px] uppercase font-bold tracking-widest text-[#718493] mb-1">
            Human Ground Truth · Inter-Annotator Agreement
          </div>
          <h1 className="text-2xl font-bold text-[#eef5f7] tracking-tight">
            Human Annotation & Judge Calibration
          </h1>
          <p className="text-xs text-[#8295a1] mt-1 max-w-2xl leading-relaxed">
            LLM judges must be calibrated against real human legal annotations. Cohen's κ is computed per error category, requiring κ ≥ 0.60 before judge verdicts are trusted.
          </p>

          <div className="flex gap-4 mt-6 border-b border-[#20303a]">
            <button
              onClick={() => setTab('calibration')}
              className={`pb-2.5 text-xs font-semibold border-b-2 transition-colors ${
                tab === 'calibration'
                  ? 'border-[#66d9e8] text-[#66d9e8]'
                  : 'border-transparent text-[#718493] hover:text-[#c4d1d7]'
              }`}
            >
              Judge Calibration (Cohen's κ)
            </button>
            <button
              onClick={() => setTab('annotations')}
              className={`pb-2.5 text-xs font-semibold border-b-2 transition-colors ${
                tab === 'annotations'
                  ? 'border-[#66d9e8] text-[#66d9e8]'
                  : 'border-transparent text-[#718493] hover:text-[#c4d1d7]'
              }`}
            >
              Annotations List ({annotations.length})
            </button>
            <button
              onClick={() => setTab('label')}
              className={`pb-2.5 text-xs font-semibold border-b-2 transition-colors ${
                tab === 'label'
                  ? 'border-[#66d9e8] text-[#66d9e8]'
                  : 'border-transparent text-[#718493] hover:text-[#c4d1d7]'
              }`}
            >
              + Submit Annotation
            </button>
          </div>
        </div>

        {/* Tab 1: Calibration Dashboard */}
        {tab === 'calibration' && (
          <div className="space-y-4">
            <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-4">
              <div className="flex justify-between items-center">
                <div>
                  <h2 className="text-sm font-semibold text-[#eef5f7]">Category Calibration Status</h2>
                  <p className="text-xs text-[#8295a1]">
                    Minimum 30 paired human labels required per category. Uncalibrated categories are suppressed from aggregate scoring.
                  </p>
                </div>
                <div className="text-xs font-mono text-[#718493]">
                  Threshold: <b>κ ≥ 0.60</b>
                </div>
              </div>

              {loading ? (
                <div className="text-center py-12 text-xs text-[#8295a1]">Computing calibration metrics...</div>
              ) : calibration.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead>
                      <tr className="border-b border-[#20303a] text-[#718493] font-medium text-[11px]">
                        <th className="py-2.5 px-3">Error Category</th>
                        <th className="py-2.5 px-3">Labeled Items</th>
                        <th className="py-2.5 px-3">Cohen's κ</th>
                        <th className="py-2.5 px-3">Threshold</th>
                        <th className="py-2.5 px-3">Calibration Status</th>
                        <th className="py-2.5 px-3">Audit Note</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1b2832]">
                      {calibration.map((row) => (
                        <tr key={row.category} className="hover:bg-[#131d27]/60">
                          <td className="py-3 px-3 font-mono font-medium text-[#c4d1d7]">
                            {row.category}
                          </td>
                          <td className="py-3 px-3 font-mono text-[#e1edf0]">
                            {row.labeled_items}
                          </td>
                          <td className="py-3 px-3 font-mono">
                            {row.kappa !== null ? row.kappa.toFixed(3) : 'n/a'}
                          </td>
                          <td className="py-3 px-3 font-mono text-[#8295a1]">
                            {row.kappa_threshold}
                          </td>
                          <td className="py-3 px-3">
                            <StatusBadge status={row.status} />
                          </td>
                          <td className="py-3 px-3 text-[11px] text-[#718493] max-w-xs truncate">
                            {row.note}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyState
                  title="No calibration data"
                  description="Human annotations are needed to compute inter-annotator agreement and judge calibration."
                />
              )}
            </div>

            {/* Disagreements */}
            {disagreements.length > 0 && (
              <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-3">
                <h3 className="text-sm font-semibold text-[#e1edf0]">Inter-Annotator Disagreements ({disagreements.length})</h3>
                <p className="text-xs text-[#8295a1]">
                  Items where multiple human annotators assigned differing error categories or severity tiers.
                </p>
                <div className="space-y-2">
                  {disagreements.map((d) => (
                    <div key={d.item_id} className="p-3 bg-[#0b1117] rounded border border-[#20303a] text-xs font-mono">
                      <div className="font-bold text-[#e1a85a] mb-1">Item: {d.item_id}</div>
                      <div className="text-[11px] text-[#8295a1]">
                        {d.annotations.length} conflicting annotations recorded
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Annotations List */}
        {tab === 'annotations' && (
          <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-sm font-semibold text-[#e1edf0]">Recorded Annotations</h2>
              <a
                href="/api/annotations/export/csv"
                download
                className="px-3 py-1.5 rounded bg-[#172832] hover:bg-[#203542] border border-[#263540] text-xs font-mono text-[#66d9e8] flex items-center gap-1.5"
              >
                <Download size={13} /> Export CSV
              </a>
            </div>

            {annotations.length > 0 ? (
              <div className="space-y-3">
                {annotations.map((a) => (
                  <div key={a.id} className="p-3 bg-[#0b1117] rounded border border-[#20303a] text-xs space-y-1">
                    <div className="flex justify-between items-center">
                      <span className="font-mono text-[#66d9e8] font-bold">
                        Item: {a.item_id.substring(0, 12)}...
                      </span>
                      <StatusBadge status={`severity ${a.severity}`} label={`Severity ${a.severity}`} />
                    </div>
                    <div className="text-[#8295a1] font-mono text-[11px]">
                      Annotator: <b>{a.annotator_id}</b> · Categories: {a.error_categories.join(', ') || 'None'}
                    </div>
                    {a.notes && <div className="text-[#c4d1d7] text-[11px] mt-1">{a.notes}</div>}
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No annotations recorded yet"
                description="Use the Submit Annotation tab to add ground-truth human labels."
              />
            )}
          </div>
        )}

        {/* Tab 3: Submit Annotation */}
        {tab === 'label' && (
          <form onSubmit={handleSubmit} className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-4 max-w-2xl">
            <h2 className="text-sm font-semibold text-[#e1edf0]">Submit New Human Annotation</h2>

            {submitMsg && (
              <div className="p-3 bg-[#66d9e8]/10 border border-[#66d9e8]/30 rounded text-xs text-[#66d9e8]">
                {submitMsg}
              </div>
            )}

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-[10px] uppercase font-bold text-[#718493] block mb-1">
                  Benchmark Item ID
                </label>
                <input
                  type="text"
                  value={itemId}
                  onChange={(e) => setItemId(e.target.value)}
                  placeholder="Paste UUID of benchmark item..."
                  className="w-full bg-[#0b1117] border border-[#20303a] rounded py-1.5 px-3 text-[#c4d1d7] font-mono focus:outline-none focus:border-[#66d9e8]"
                  required
                />
              </div>

              <div>
                <label className="text-[10px] uppercase font-bold text-[#718493] block mb-1">
                  Annotator Identifier
                </label>
                <input
                  type="text"
                  value={annotatorId}
                  onChange={(e) => setAnnotatorId(e.target.value)}
                  className="w-full bg-[#0b1117] border border-[#20303a] rounded py-1.5 px-3 text-[#c4d1d7] font-mono focus:outline-none focus:border-[#66d9e8]"
                  required
                />
              </div>

              <div>
                <label className="text-[10px] uppercase font-bold text-[#718493] block mb-1">
                  Assigned Severity Tier
                </label>
                <select
                  value={severity}
                  onChange={(e) => setSeverity(parseInt(e.target.value))}
                  className="w-full bg-[#0b1117] border border-[#20303a] rounded py-1.5 px-3 text-[#c4d1d7]"
                >
                  <option value={0}>0 — No Error (Clean)</option>
                  <option value={1}>1 — Minor Inaccuracy / Elaboration</option>
                  <option value={2}>2 — Moderate Error / Wrong Section</option>
                  <option value={3}>3 — Critical / Citation Fabrication / Jurisdiction Conflation</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] uppercase font-bold text-[#718493] block mb-1">
                  Error Categories (Select all that apply)
                </label>
                <div className="grid grid-cols-2 gap-2 mt-1">
                  {categoryOptions.map((cat) => (
                    <label key={cat} className="flex items-center gap-2 text-[11px] text-[#c4d1d7] cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedCats.includes(cat)}
                        onChange={(e) => {
                          if (e.target.checked) setSelectedCats([...selectedCats, cat])
                          else setSelectedCats(selectedCats.filter((c) => c !== cat))
                        }}
                        className="rounded border-[#20303a] bg-[#0b1117]"
                      />
                      <span>{cat}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-[10px] uppercase font-bold text-[#718493] block mb-1">
                  Annotation Notes / Legal Rationale
                </label>
                <textarea
                  rows={3}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Explain why this error category or severity was chosen..."
                  className="w-full bg-[#0b1117] border border-[#20303a] rounded p-2.5 text-xs text-[#c4d1d7] focus:outline-none focus:border-[#66d9e8]"
                />
              </div>

              <button
                type="submit"
                className="px-5 py-2 rounded bg-[#66d9e8] hover:bg-[#52c8d7] text-[#071117] font-bold text-xs flex items-center gap-1.5"
              >
                <CheckCircle2 size={14} /> Submit Ground Truth Label
              </button>
            </div>
          </form>
        )}
      </div>
    </AppShell>
  )
}
