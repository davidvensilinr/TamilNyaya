'use client'

import React, { useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { api, LiveCheckResponse } from '@/lib/api'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { TamilText } from '@/components/shared/TamilText'
import { CheckCircle2, AlertTriangle, ShieldCheck, Play, Sparkles } from 'lucide-react'

export default function LiveCheckPage() {
  const [question, setQuestion] = useState(
    'தமிழ்நாடு பெண்கள் வன்கொடுமை தடுப்புச் சட்டம், 1998 பிரிவு 4 எதை விவரிக்கிறது?'
  )
  const [answer, setAnswer] = useState(
    'தமிழ்நாடு பெண்கள் வன்கொடுமை தடுப்புச் சட்டம், 1998 பிரிவு 4 இன் படி, பெண்ணை வன்கொடுமை செய்யும் எவருக்கும் மூன்று ஆண்டுகள் வரை சிறைத்தண்டனையும் பத்தாயிரம் ரூபாய் அபராதமும் விதிக்கப்படும்.'
  )
  const [jurisdiction, setJurisdiction] = useState<string>('Tamil Nadu')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<LiveCheckResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleCheck(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)

    const res = await api.liveCheck({
      question,
      answer,
      required_jurisdiction: jurisdiction || null,
      run_faithfulness: true,
      run_judge: false,
    })

    if (res.data) {
      setResult(res.data)
    } else {
      setError(res.error || 'Verification check failed')
    }
    setLoading(false)
  }

  function handlePreset(type: 'real' | 'fabricated') {
    if (type === 'real') {
      setQuestion('தமிழ்நாடு பெண்கள் வன்கொடுமை தடுப்புச் சட்டம், 1998 பிரிவு 4 எதை விவரிக்கிறது?')
      setAnswer('தமிழ்நாடு பெண்கள் வன்கொடுமை தடுப்புச் சட்டம், 1998 பிரிவு 4 இன் கீழ் பெண்களுக்கு வன்கொடுமை செய்த குற்றத்திற்கான தண்டனை மூன்று ஆண்டுகள் வரை சிறை மற்றும் பத்தாயிரம் ரூபாய் அபராதம்.')
      setJurisdiction('Tamil Nadu')
    } else {
      setQuestion('குடும்ப வன்முறைச் சட்டம் பிரிவு 999 என்ன கூறுகிறது?')
      setAnswer('The Protection of Women from Domestic Violence Act, 2005 பிரிவு 999 இன் படி குடும்ப வன்முறைக்கு தூக்கு தண்டனை விதிக்கப்படும்.')
      setJurisdiction('Central')
    }
  }

  return (
    <AppShell>
      <div className="space-y-6 max-w-5xl">
        {/* Header */}
        <div className="border-b border-[#263540] pb-5">
          <div className="text-[10px] uppercase font-bold tracking-widest text-[#718493] mb-1">
            Real-Time Audit Harness · Interactive Verification
          </div>
          <h1 className="text-2xl font-bold text-[#eef5f7] tracking-tight">
            Live Citation & Faithfulness Check
          </h1>
          <p className="text-xs text-[#8295a1] mt-1 max-w-2xl leading-relaxed">
            Test any model answer or legal passage. Layer 1 executes deterministic regex and fuzzy matching against official KB statutes. Layer 2 executes NLI entailment scoring.
          </p>
        </div>

        {/* Input Form */}
        <form onSubmit={handleCheck} className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-4">
          <div className="flex justify-between items-center">
            <span className="text-xs font-semibold text-[#e1edf0]">Verification Inputs</span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => handlePreset('real')}
                className="text-[10px] font-mono px-2 py-1 rounded bg-[#131d26] hover:bg-[#1a2834] border border-[#20303a] text-[#66d9e8]"
              >
                Sample: Real Citation
              </button>
              <button
                type="button"
                onClick={() => handlePreset('fabricated')}
                className="text-[10px] font-mono px-2 py-1 rounded bg-[#131d26] hover:bg-[#1a2834] border border-[#20303a] text-[#e1a85a]"
              >
                Sample: Fabricated Citation
              </button>
            </div>
          </div>

          <div className="space-y-3 text-xs">
            <div>
              <label className="text-[10px] uppercase font-bold text-[#718493] block mb-1">
                Legal Question / Prompt
              </label>
              <textarea
                rows={2}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                className="w-full bg-[#0b1117] border border-[#20303a] rounded p-2.5 text-xs text-[#c4d1d7] font-tamil focus:outline-none focus:border-[#66d9e8]"
                placeholder="Enter legal question in Tamil or English..."
                required
              />
            </div>

            <div>
              <label className="text-[10px] uppercase font-bold text-[#718493] block mb-1">
                Model Output / Passage to Verify
              </label>
              <textarea
                rows={4}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                className="w-full bg-[#0b1117] border border-[#20303a] rounded p-2.5 text-xs text-[#c4d1d7] font-tamil focus:outline-none focus:border-[#66d9e8]"
                placeholder="Paste the legal answer or claim here..."
                required
              />
            </div>

            <div className="flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center pt-2">
              <div className="flex items-center gap-2">
                <span className="text-[10px] uppercase font-bold text-[#718493]">
                  Required Jurisdiction:
                </span>
                <select
                  value={jurisdiction}
                  onChange={(e) => setJurisdiction(e.target.value)}
                  className="bg-[#0b1117] border border-[#20303a] rounded py-1 px-2.5 text-[#c4d1d7]"
                >
                  <option value="">Any Jurisdiction</option>
                  <option value="Central">Central Law</option>
                  <option value="Tamil Nadu">Tamil Nadu State Law</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="px-5 py-2 rounded bg-[#66d9e8] hover:bg-[#52c8d7] text-[#071117] font-bold text-xs flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                <CheckCircle2 size={14} />
                {loading ? 'Verifying Layers...' : 'Run Verification Harness'}
              </button>
            </div>
          </div>
        </form>

        {error && (
          <div className="p-3 bg-[#f87171]/10 border border-[#f87171]/30 rounded text-xs text-[#f87171]">
            {error}
          </div>
        )}

        {/* Results Display */}
        {result && (
          <div className="space-y-6">
            {/* Layer 1 Result */}
            <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-4">
              <div className="flex items-center justify-between border-b border-[#20303a] pb-3">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-[#66d9e8]/10 text-[#66d9e8] text-[11px] font-mono font-bold flex items-center justify-center">
                    L1
                  </span>
                  <h2 className="text-sm font-semibold text-[#eef5f7]">
                    Layer 1: Deterministic Citation Verifier Result
                  </h2>
                </div>
                <StatusBadge
                  status={result.layer1.correct_citations === result.layer1.total_citations && result.layer1.total_citations > 0 ? 'ok' : 'degraded'}
                  label={`${result.layer1.correct_citations} / ${result.layer1.total_citations} Verified`}
                />
              </div>

              {result.layer1.verdicts.length > 0 ? (
                <div className="space-y-3">
                  {result.layer1.verdicts.map((v, idx) => (
                    <div key={idx} className="p-3.5 bg-[#0b1117] rounded border border-[#20303a] text-xs space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="font-mono text-sm font-bold text-[#66d9e8]">
                          "{v.raw_text}"
                        </span>
                        <StatusBadge
                          status={v.is_correct ? 'ok' : `severity ${v.severity}`}
                          label={v.verdict}
                        />
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px] text-[#718493] font-mono pt-1 border-t border-[#1b2832]">
                        <div>Normalized: <b className="text-[#c4d1d7]">Section {v.normalized_section}</b></div>
                        <div>Matched Act: <b className="text-[#c4d1d7]">{v.matched_act_name || 'None'}</b></div>
                        <div>Fuzzy Score: <b className="text-[#c4d1d7]">{v.fuzzy_score ? `${v.fuzzy_score.toFixed(0)}%` : 'Exact'}</b></div>
                        <div>Severity Tier: <b className="text-[#e1a85a]">{v.severity}</b></div>
                      </div>

                      <div className="text-[11px] text-[#8295a1] font-mono bg-[#111a23] p-2 rounded">
                        Audit Trail: {v.lookup_description}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-[#8295a1] py-2">
                  No legal citations detected in the input answer.
                </div>
              )}
            </div>

            {/* Layer 2 Result */}
            {result.layer2 && (
              <div className="p-5 rounded-lg bg-[#101922] border border-[#263540] space-y-3">
                <div className="flex items-center gap-2 border-b border-[#20303a] pb-3">
                  <span className="w-5 h-5 rounded-full bg-[#7aa2f7]/10 text-[#7aa2f7] text-[11px] font-mono font-bold flex items-center justify-center">
                    L2
                  </span>
                  <h2 className="text-sm font-semibold text-[#eef5f7]">
                    Layer 2: NLI Faithfulness Scorer Result
                  </h2>
                </div>

                <div className="text-xs space-y-2">
                  <div className="flex items-center gap-4 text-[#8295a1]">
                    <span>Score: <b className="text-[#7aa2f7] font-mono">{result.layer2.faithfulness_score ?? 'n/a'}</b></span>
                    <span>Entailed Claims: <b>{result.layer2.entailed_count ?? 0}</b></span>
                    <span>Neutral Claims: <b>{result.layer2.neutral_count ?? 0}</b></span>
                    <span>Contradicted: <b>{result.layer2.contradicted_count ?? 0}</b></span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}
