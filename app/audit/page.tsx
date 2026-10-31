'use client'

import React, { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { api, AuditEntry } from '@/lib/api'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { EmptyState } from '@/components/shared/EmptyState'
import { ScrollText, ShieldCheck, RefreshCw, AlertTriangle, CheckCircle, Terminal } from 'lucide-react'

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [levelFilter, setLevelFilter] = useState('')
  const [actionFilter, setActionFilter] = useState('')

  // Integrity Check State
  const [integrityLoading, setIntegrityLoading] = useState(false)
  const [integrityResult, setIntegrityResult] = useState<any | null>(null)

  useEffect(() => {
    loadAudit()
  }, [levelFilter, actionFilter])

  async function loadAudit() {
    setLoading(true)
    const res = await api.getAuditLog({
      level: levelFilter || undefined,
      action: actionFilter || undefined,
      limit: 100,
    })
    if (res.data) setEntries(res.data)
    setLoading(false)
  }

  async function runIntegrity() {
    setIntegrityLoading(true)
    const res = await api.runIntegrityCheck()
    if (res.data) {
      setIntegrityResult(res.data)
    }
    setIntegrityLoading(false)
  }

  return (
    <AppShell>
      <div className="space-y-6 max-w-6xl">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-[#263540] pb-5">
          <div>
            <div className="text-[10px] uppercase font-bold tracking-widest text-[#718493] mb-1">
              Append-Only Audit Trail · System Integrity
            </div>
            <h1 className="text-2xl font-bold text-[#eef5f7] tracking-tight">
              Audit Log & Integrity Verifier
            </h1>
            <p className="text-xs text-[#8295a1] mt-1 max-w-2xl leading-relaxed">
              Every ingestion action, rejected record, model retry, and evaluation event is permanently logged with timestamps and provenance URLs.
            </p>
          </div>

          <button
            onClick={runIntegrity}
            disabled={integrityLoading}
            className="px-3.5 py-2 rounded bg-[#172832] hover:bg-[#203542] border border-[#263540] text-xs font-semibold text-[#66d9e8] flex items-center gap-1.5 transition-colors disabled:opacity-50"
          >
            <ShieldCheck size={14} />
            {integrityLoading ? 'Running 7 Integrity Checks...' : 'Run Integrity Checker'}
          </button>
        </div>

        {/* Integrity Check Result Modal/Card */}
        {integrityResult && (
          <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-3">
            <div className="flex justify-between items-center border-b border-[#20303a] pb-2">
              <div className="flex items-center gap-2">
                <ShieldCheck size={16} className={integrityResult.all_passed ? 'text-[#74c69d]' : 'text-[#f87171]'} />
                <h3 className="text-sm font-semibold text-[#eef5f7]">
                  Integrity Verification Report: {integrityResult.all_passed ? 'ALL CHECKS PASSED' : 'INTEGRITY ISSUES DETECTED'}
                </h3>
              </div>
              <button
                onClick={() => setIntegrityResult(null)}
                className="text-xs text-[#718493] hover:text-[#eef5f7] font-mono"
              >
                Dismiss
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
              {integrityResult.checks && Object.entries(integrityResult.checks).map(([checkName, checkData]: any) => (
                <div key={checkName} className="p-2.5 bg-[#0b1117] rounded border border-[#20303a] flex justify-between items-center">
                  <span className="text-[#c4d1d7] capitalize">{checkName.replace(/_/g, ' ')}</span>
                  <StatusBadge status={checkData.passed ? 'ok' : 'error'} label={checkData.passed ? 'PASS' : 'FAIL'} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-wrap gap-3 items-center justify-between p-3 rounded-lg bg-[#101922] border border-[#263540] text-xs">
          <div className="flex gap-2 items-center">
            <select
              value={levelFilter}
              onChange={(e) => setLevelFilter(e.target.value)}
              className="bg-[#0b1117] border border-[#20303a] rounded py-1 px-2.5 text-[#c4d1d7]"
            >
              <option value="">All Log Levels</option>
              <option value="INFO">INFO</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
              <option value="RETRY">RETRY</option>
            </select>

            <input
              type="text"
              placeholder="Filter by action name..."
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="bg-[#0b1117] border border-[#20303a] rounded py-1 px-2.5 text-[#c4d1d7] focus:outline-none focus:border-[#66d9e8]"
            />
          </div>

          <div className="flex items-center gap-3">
            <span className="text-[11px] text-[#718493] font-mono">
              {entries.length} log events recorded
            </span>
            <button
              onClick={loadAudit}
              className="text-xs text-[#66d9e8] hover:underline flex items-center gap-1 font-mono"
            >
              <RefreshCw size={11} /> Refresh
            </button>
          </div>
        </div>

        {/* Log Stream */}
        {loading ? (
          <div className="text-center py-16 text-xs text-[#8295a1]">Loading audit trail...</div>
        ) : entries.length > 0 ? (
          <div className="p-4 rounded-lg bg-[#101922] border border-[#263540] space-y-2 font-mono text-xs">
            {entries.map((e) => (
              <div
                key={e.id}
                className="p-2.5 bg-[#0b1117] rounded border border-[#1b2832] flex flex-col sm:flex-row sm:items-center justify-between gap-2"
              >
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[#627783] text-[10px]">
                    {new Date(e.timestamp).toLocaleTimeString()}
                  </span>
                  <StatusBadge status={e.level} label={e.level} />
                  <span className="text-[#66d9e8] font-bold text-[11px]">
                    {e.action}
                  </span>
                  <span className="text-[#95a8b5] font-sans text-xs">
                    {e.detail}
                  </span>
                </div>

                <div className="text-[10px] text-[#556977] flex items-center gap-2 flex-shrink-0">
                  {e.run_id && <span>run:{e.run_id.substring(0, 6)}</span>}
                  {e.source_url && <span className="truncate max-w-xs">{e.source_url}</span>}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No audit entries found"
            description="No log events match your current filter criteria."
          />
        )}
      </div>
    </AppShell>
  )
}
