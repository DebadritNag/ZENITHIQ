import { useState } from 'react'

interface Props {
  onAnalyse: (ticker: string) => void
  loading: boolean
}

export function Masthead({ onAnalyse, loading }: Props) {
  const [input, setInput] = useState('')

  const submit = () => {
    const t = input.trim().toUpperCase()
    if (t) onAnalyse(t)
  }

  return (
    <header
      style={{ borderBottom: '2px solid #121212' }}
      className="bg-[#F9F9F8] px-8 py-4"
    >
      {/* Newspaper nameplate */}
      <div className="flex items-baseline justify-between mb-3">
        <div>
          <h1
            className="text-4xl font-bold tracking-tight leading-none"
            style={{ fontFamily: 'Playfair Display, serif' }}
          >
            ZENITH IQ
          </h1>
          <p
            className="text-[11px] tracking-[0.25em] uppercase mt-0.5"
            style={{ color: '#6B6B6B', fontFamily: 'JetBrains Mono, monospace' }}
          >
            Financial Intelligence Terminal · Est. 2025
          </p>
        </div>

        <div
          className="text-right text-[11px]"
          style={{ color: '#6B6B6B', fontFamily: 'JetBrains Mono, monospace' }}
        >
          <div>{new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</div>
          <div className="mt-0.5">Multi-Agent Risk Analysis System</div>
        </div>
      </div>

      {/* Rule */}
      <div style={{ borderTop: '1px solid #D1D1D1' }} className="mb-3" />

      {/* Search bar */}
      <div className="flex gap-0 max-w-xl">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && submit()}
          placeholder="Enter ticker symbol — AAPL, TSLA, MSFT..."
          className="flex-1 px-4 py-2 text-sm bg-white outline-none"
          style={{
            border: '1px solid #121212',
            borderRight: 'none',
            fontFamily: 'JetBrains Mono, monospace',
          }}
        />
        <button
          onClick={submit}
          disabled={loading}
          className="px-6 py-2 text-sm font-semibold text-white disabled:opacity-50"
          style={{
            background: '#121212',
            border: '1px solid #121212',
            fontFamily: 'JetBrains Mono, monospace',
            cursor: loading ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? 'ANALYSING...' : 'RUN ANALYSIS'}
        </button>
      </div>
    </header>
  )
}
