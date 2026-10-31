'use client'

import React, { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { api, KBRecord, QualityReport, CoverageRow } from '@/lib/api'
import { TamilText } from '@/components/shared/TamilText'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { EmptyState } from '@/components/shared/EmptyState'
import { Search, Filter, Database, ShieldAlert, FileCode2, ExternalLink, RefreshCw } from 'lucide-react'

export default function KBExplorerPage() {
  const [tab, setTab] = useState<'records' | 'quality' | 'coverage'>('records')
  const [records, setRecords] = useState<KBRecord[]>([])
  const [quality, setQuality] = useState<QualityReport | null>(null)
  const [coverage, setCoverage] = useState<CoverageRow[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedJurisdiction, setSelectedJurisdiction] = useState<string>('')
  const [selectedRecord, setSelectedRecord] = useState<KBRecord | null>(null)

  useEffect(() => {
    loadData()
  }, [searchQuery, selectedJurisdiction])

  async function loadData() {
    setLoading(true)
    const [recRes, qRes, covRes] = await Promise.all([
      api.searchKB({
        q: searchQuery || undefined,
        jurisdiction: selectedJurisdiction || undefined,
        limit: 100,
      }),
      api.getKBQuality(),
      api.getKBCoverage(),
    ])

    if (recRes.data) setRecords(recRes.data)
    if (qRes.data) setQuality(qRes.data)
    if (covRes.data) setCoverage(covRes.data)
    setLoading(false)
  }

  return (
    <AppShell>
      <div className="space-y-6 max-w-6xl">
        {/* Header */}
        <div className="border-b border-[#263540] pb-5">
          <div className="text-[10px] uppercase font-bold tracking-widest text-[#718493] mb-1">
            Data Provenance · Ground Truth Repository
          </div>
          <h1 className="text-2xl font-bold text-[#eef5f7] tracking-tight">
            Knowledge Base Explorer
          </h1>
          <p className="text-xs text-[#8295a1] mt-1 max-w-2xl leading-relaxed">
            Every provision in this database was extracted from official gazettes and statutes with recorded SHA-256 hashes, exact character offsets, and parser metadata.
          </p>

          {/* Navigation Tabs */}
          <div className="flex gap-4 mt-6 border-b border-[#20303a]">
            <button
              onClick={() => setTab('records')}
              className={`pb-2.5 text-xs font-semibold border-b-2 transition-colors ${
                tab === 'records'
                  ? 'border-[#66d9e8] text-[#66d9e8]'
                  : 'border-transparent text-[#718493] hover:text-[#c4d1d7]'
              }`}
            >
              Provisions ({records.length})
            </button>
            <button
              onClick={() => setTab('coverage')}
              className={`pb-2.5 text-xs font-semibold border-b-2 transition-colors ${
                tab === 'coverage'
                  ? 'border-[#66d9e8] text-[#66d9e8]'
                  : 'border-transparent text-[#718493] hover:text-[#c4d1d7]'
              }`}
            >
              Statute Coverage ({coverage.length})
            </button>
            <button
              onClick={() => setTab('quality')}
              className={`pb-2.5 text-xs font-semibold border-b-2 transition-colors ${
                tab === 'quality'
                  ? 'border-[#66d9e8] text-[#66d9e8]'
                  : 'border-transparent text-[#718493] hover:text-[#c4d1d7]'
              }`}
            >
              Data Quality & Audit Spot-Check
            </button>
          </div>
        </div>

        {/* Tab 1: Records */}
        {tab === 'records' && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row gap-3 justify-between items-center bg-[#101922] p-3 rounded-lg border border-[#263540]">
              <div className="relative w-full sm:w-96">
                <Search size={14} className="absolute left-3 top-2.5 text-[#718493]" />
                <input
                  type="text"
                  placeholder="Search section text, Act name or number..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 bg-[#0b1117] border border-[#20303a] rounded text-xs text-[#e1edf0] placeholder-[#5a6c78] focus:outline-none focus:border-[#66d9e8]"
                />
              </div>

              <div className="flex items-center gap-2 w-full sm:w-auto">
                <Filter size={14} className="text-[#718493]" />
                <select
                  value={selectedJurisdiction}
                  onChange={(e) => setSelectedJurisdiction(e.target.value)}
                  className="bg-[#0b1117] border border-[#20303a] rounded text-xs text-[#c4d1d7] py-1.5 px-3 focus:outline-none focus:border-[#66d9e8]"
                >
                  <option value="">All Jurisdictions</option>
                  <option value="Central">Central Law</option>
                  <option value="Tamil Nadu">Tamil Nadu State Law</option>
                </select>
              </div>
            </div>

            {loading ? (
              <div className="text-center py-12 text-xs text-[#8295a1]">Loading knowledge base...</div>
            ) : records.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {records.map((r) => (
                  <div
                    key={r.record_id}
                    onClick={() => setSelectedRecord(r)}
                    className={`p-4 rounded-lg bg-[#111a23] hover:bg-[#15222e] border transition-colors cursor-pointer flex flex-col justify-between ${
                      selectedRecord?.record_id === r.record_id ? 'border-[#66d9e8]' : 'border-[#263540]'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className="font-mono text-xs font-bold text-[#66d9e8]">
                          Section {r.section_no}
                        </span>
                        <div className="flex gap-1.5">
                          <StatusBadge status={r.jurisdiction === 'Tamil Nadu' ? 'running' : 'completed'} label={r.jurisdiction} />
                          {r.in_force === false && <StatusBadge status="repealed" label="Repealed" />}
                        </div>
                      </div>

                      <div className="text-xs font-semibold text-[#e1edf0] mb-1">
                        {r.act_name_en}
                      </div>

                      <div className="text-xs text-[#95a8b5] mb-3 line-clamp-3">
                        <TamilText>{r.text_ta}</TamilText>
                      </div>
                    </div>

                    <div className="pt-2 border-t border-[#1d2b36] flex items-center justify-between text-[10px] text-[#6d818d] font-mono">
                      <span>SHA: {r.source_file_sha256.substring(0, 8)}...</span>
                      <span>Span: {r.raw_span || 'n/a'}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No records matched your criteria"
                description="Try broadening your search term or selecting a different jurisdiction."
              />
            )}

            {/* Record Provenance Modal */}
            {selectedRecord && (
              <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                <div className="bg-[#101922] border border-[#263540] rounded-xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-6 space-y-4">
                  <div className="flex items-start justify-between border-b border-[#20303a] pb-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm font-bold text-[#66d9e8]">
                          Section {selectedRecord.section_no}
                        </span>
                        <StatusBadge status={selectedRecord.jurisdiction} />
                        {selectedRecord.in_force === false && <StatusBadge status="repealed" label="Repealed" />}
                      </div>
                      <h3 className="text-base font-semibold text-[#eef5f7] mt-1">
                        {selectedRecord.act_name_en}
                      </h3>
                      <div className="text-xs text-[#8295a1] font-tamil">
                        {selectedRecord.act_name_ta}
                      </div>
                    </div>
                    <button
                      onClick={() => setSelectedRecord(null)}
                      className="text-[#718493] hover:text-[#eef5f7] text-lg font-bold p-1"
                    >
                      ×
                    </button>
                  </div>

                  <div className="space-y-3">
                    <div>
                      <div className="text-[10px] uppercase font-bold text-[#718493] mb-1">
                        Tamil Legal Text (Source Truth)
                      </div>
                      <div className="p-3 bg-[#0b1117] rounded border border-[#20303a] text-xs leading-relaxed text-[#d7e0e8]">
                        <TamilText>{selectedRecord.text_ta}</TamilText>
                      </div>
                    </div>

                    {selectedRecord.text_en && (
                      <div>
                        <div className="text-[10px] uppercase font-bold text-[#718493] mb-1">
                          Official English Translation
                        </div>
                        <div className="p-3 bg-[#0b1117] rounded border border-[#20303a] text-xs leading-relaxed text-[#8ca0ad]">
                          {selectedRecord.text_en}
                        </div>
                      </div>
                    )}

                    <div className="border-t border-[#20303a] pt-3">
                      <div className="text-[10px] uppercase font-bold text-[#718493] mb-2">
                        Provenance & Verification Trail
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-xs font-mono bg-[#0b1117] p-3 rounded border border-[#20303a]">
                        <div>
                          <span className="text-[#627783] block text-[10px]">Record ID</span>
                          <span className="text-[#95a8b5] break-all">{selectedRecord.record_id}</span>
                        </div>
                        <div>
                          <span className="text-[#627783] block text-[10px]">Extraction Method</span>
                          <span className="text-[#66d9e8]">{selectedRecord.extraction_method}</span>
                        </div>
                        <div>
                          <span className="text-[#627783] block text-[10px]">Source SHA-256</span>
                          <span className="text-[#95a8b5] break-all">{selectedRecord.source_file_sha256}</span>
                        </div>
                        <div>
                          <span className="text-[#627783] block text-[10px]">Character Span</span>
                          <span className="text-[#95a8b5]">{selectedRecord.raw_span || 'unknown'}</span>
                        </div>
                        <div>
                          <span className="text-[#627783] block text-[10px]">Parser Version</span>
                          <span className="text-[#95a8b5]">{selectedRecord.parser_name_and_version}</span>
                        </div>
                        <div>
                          <span className="text-[#627783] block text-[10px]">Retrieved Timestamp</span>
                          <span className="text-[#95a8b5]">{new Date(selectedRecord.retrieved_at).toLocaleString()}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex justify-between items-center pt-2">
                      <a
                        href={selectedRecord.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-[#66d9e8] hover:underline flex items-center gap-1 font-mono"
                      >
                        Official Source URL <ExternalLink size={12} />
                      </a>
                      <button
                        onClick={() => setSelectedRecord(null)}
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
        )}

        {/* Tab 2: Coverage */}
        {tab === 'coverage' && (
          <div className="space-y-4">
            <div className="p-4 rounded-lg bg-[#101922] border border-[#263540]">
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr className="border-b border-[#20303a] text-[#718493] font-medium text-[11px]">
                      <th className="py-2.5 px-3">Statute Title</th>
                      <th className="py-2.5 px-3">Jurisdiction</th>
                      <th className="py-2.5 px-3">Ingested Sections</th>
                      <th className="py-2.5 px-3">Declared in Official Gazette</th>
                      <th className="py-2.5 px-3">Coverage Ratio</th>
                      <th className="py-2.5 px-3">Last Synchronized</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1b2832]">
                    {coverage.map((c) => (
                      <tr key={c.act_name_en} className="hover:bg-[#131d27]/60">
                        <td className="py-3 px-3 font-medium text-[#e1edf0]">{c.act_name_en}</td>
                        <td className="py-3 px-3">
                          <StatusBadge status={c.jurisdiction} />
                        </td>
                        <td className="py-3 px-3 font-mono font-bold text-[#66d9e8]">{c.sections_ingested}</td>
                        <td className="py-3 px-3 font-mono text-[#8295a1]">{c.sections_in_source ?? 'Unknown'}</td>
                        <td className="py-3 px-3 font-mono">
                          <div className="flex items-center gap-2">
                            <span>{c.coverage_pct ? `${c.coverage_pct}%` : 'Partial'}</span>
                            {c.coverage_pct && (
                              <div className="w-20 bg-[#1c2a32] h-1.5 rounded-full overflow-hidden">
                                <div
                                  className="bg-[#66d9e8] h-full"
                                  style={{ width: `${Math.min(c.coverage_pct, 100)}%` }}
                                />
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-3 text-[#718493] font-mono">
                          {c.last_updated ? new Date(c.last_updated).toLocaleDateString() : 'Active'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Data Quality */}
        {tab === 'quality' && (
          <div className="space-y-6">
            {quality ? (
              <>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 rounded-lg bg-[#111a23] border border-[#263540]">
                    <div className="text-[10px] uppercase font-bold text-[#718493] mb-1">Total Ingested Records</div>
                    <div className="text-2xl font-mono font-bold text-[#e1edf0]">{quality.total_records}</div>
                    <div className="text-[11px] text-[#6d818d] mt-1">Verified with SHA-256</div>
                  </div>
                  <div className="p-4 rounded-lg bg-[#111a23] border border-[#263540]">
                    <div className="text-[10px] uppercase font-bold text-[#718493] mb-1">Empty Tamil Text</div>
                    <div className="text-2xl font-mono font-bold text-[#74c69d]">{quality.records_with_empty_tamil}</div>
                    <div className="text-[11px] text-[#6d818d] mt-1">Zero empty records allowed</div>
                  </div>
                  <div className="p-4 rounded-lg bg-[#111a23] border border-[#263540]">
                    <div className="text-[10px] uppercase font-bold text-[#718493] mb-1">Duplicate Prevention</div>
                    <div className="text-xs font-semibold text-[#74c69d] mt-1">Enforced at DB Layer</div>
                    <div className="text-[10px] text-[#6d818d] mt-1">UNIQUE(source_file_sha256, section_no)</div>
                  </div>
                </div>

                <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-4">
                  <h3 className="text-sm font-semibold text-[#e1edf0]">Human Spot-Check Sample (Live Inspection)</h3>
                  <p className="text-xs text-[#8295a1]">
                    Auditors may inspect these random provisions alongside their raw character spans to verify non-fabrication.
                  </p>

                  <div className="space-y-3">
                    {quality.spot_check_sample.map((sample) => (
                      <div key={sample.record_id} className="p-3 bg-[#0b1117] rounded border border-[#20303a] text-xs">
                        <div className="flex justify-between items-center text-[#718493] font-mono text-[11px] mb-1">
                          <span className="font-bold text-[#66d9e8]">{sample.act_name_en} · Sec {sample.section_no}</span>
                          <span>Span: {sample.raw_span || 'n/a'}</span>
                        </div>
                        <p className="text-[#c4d1d7] font-tamil text-[13px] my-1">
                          {sample.text_ta_preview}
                        </p>
                        <div className="text-[10px] text-[#627783] font-mono truncate">
                          Source: {sample.source_url}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <EmptyState title="Quality report not loaded" description="Unable to retrieve data quality statistics." />
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}
