/**
 * BlueprintOverlay
 * ----------------
 * Reusable semi-transparent tour overlay with blueprint-style
 * SVG lines pointing at DOM elements.
 *
 * Used by all three pages: Contradiction Engine, Zenith Dashboard,
 * Alpha Analysis.
 */

import { useEffect, useState } from 'react'
import { X } from 'lucide-react'

export interface TourStep {
  label: string          // e.g. "STEP 01"
  title: string
  body:  string
  anchor: string         // CSS selector of the element to highlight
  side:  'right' | 'left' | 'top' | 'bottom'
}

interface Props {
  steps:     TourStep[]
  onDismiss: () => void
  finishLabel?: string   // text on the last button, default "ENTER TERMINAL"
}

export function BlueprintOverlay({ steps, onDismiss, finishLabel = 'ENTER TERMINAL' }: Props) {
  const [active, setActive]       = useState(0)
  const [rects, setRects]         = useState<Record<string, DOMRect>>({})

  // Measure all anchors once on mount
  useEffect(() => {
    const measured: Record<string, DOMRect> = {}
    steps.forEach(s => {
      const el = document.querySelector(s.anchor)
      if (el) measured[s.anchor] = el.getBoundingClientRect()
    })
    setRects(measured)
  }, [steps])

  // Re-measure when active step changes (element may have scrolled)
  useEffect(() => {
    const el = document.querySelector(steps[active].anchor)
    if (el) {
      setRects(prev => ({ ...prev, [steps[active].anchor]: el.getBoundingClientRect() }))
    }
  }, [active, steps])

  const step = steps[active]
  const rect = rects[step.anchor]
  const isLast = active === steps.length - 1

  const next = () => isLast ? onDismiss() : setActive(a => a + 1)

  // Card position: place beside the highlighted element
  const cardLeft = (() => {
    if (!rect) return 100
    if (step.side === 'right') return rect.right + 24
    if (step.side === 'left')  return rect.left  - 320
    return rect.left
  })()
  const cardTop = (() => {
    if (!rect) return 100
    if (step.side === 'top')    return rect.top  - 200
    if (step.side === 'bottom') return rect.bottom + 16
    return Math.max(16, rect.top + rect.height / 2 - 90)
  })()

  // SVG line endpoints
  const lineX1 = rect ? (step.side === 'right' ? rect.right + 6  : step.side === 'left' ? rect.left - 6  : rect.left + rect.width / 2) : 0
  const lineY1 = rect ? (step.side === 'top'   ? rect.top   - 6  : step.side === 'bottom' ? rect.bottom + 6 : rect.top + rect.height / 2) : 0
  const lineX2 = rect ? (step.side === 'right' ? rect.right + 22 : step.side === 'left' ? rect.left - 22 : rect.left + rect.width / 2) : 0
  const lineY2 = rect ? (step.side === 'top'   ? rect.top   - 22 : step.side === 'bottom' ? rect.bottom + 22 : rect.top + rect.height / 2) : 0

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 9000,
        background: 'rgba(11,14,17,0.85)',
        backdropFilter: 'blur(2px)',
      }}
    >
      {/* Skip button */}
      <button
        onClick={onDismiss}
        style={{
          position: 'absolute', top: 16, right: 16,
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '5px 12px', border: '1px solid #2B2F36',
          background: '#131720', color: '#5A6070',
          fontFamily: 'JetBrains Mono,monospace', fontSize: 10,
          letterSpacing: '0.1em', cursor: 'pointer',
        }}
      >
        <X size={10} /> SKIP TOUR
      </button>

      {/* Step counter */}
      <div style={{
        position: 'absolute', top: 20, left: '50%', transform: 'translateX(-50%)',
        fontFamily: 'JetBrains Mono,monospace', fontSize: 10,
        color: '#5A6070', letterSpacing: '0.15em',
      }}>
        {active + 1} / {steps.length}
      </div>

      {/* Highlight box */}
      {rect && (
        <div style={{
          position: 'absolute', pointerEvents: 'none',
          top:    rect.top    - 6,
          left:   rect.left   - 6,
          width:  rect.width  + 12,
          height: rect.height + 12,
          border: '1px solid #00C805',
          boxShadow: '0 0 0 2px rgba(0,200,5,0.12), 0 0 20px rgba(0,200,5,0.08)',
        }} />
      )}

      {/* SVG lines + corner ticks */}
      {rect && (
        <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
          <defs>
            <marker id="tip" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z" fill="#00C805" />
            </marker>
          </defs>
          <line
            x1={lineX1} y1={lineY1} x2={lineX2} y2={lineY2}
            stroke="#00C805" strokeWidth="1" strokeDasharray="4 3"
            markerEnd="url(#tip)"
            style={{ animation: 'dash-draw 0.5s ease forwards' }}
          />
          {/* Corner ticks */}
          {([
            [rect.left - 6,  rect.top    - 6],
            [rect.right + 6, rect.top    - 6],
            [rect.left - 6,  rect.bottom + 6],
            [rect.right + 6, rect.bottom + 6],
          ] as [number, number][]).map(([cx, cy], i) => (
            <g key={i}>
              <line x1={cx-6} y1={cy}   x2={cx+6} y2={cy}   stroke="#00C805" strokeWidth="1" opacity="0.5" />
              <line x1={cx}   y1={cy-6} x2={cx}   y2={cy+6} stroke="#00C805" strokeWidth="1" opacity="0.5" />
            </g>
          ))}
        </svg>
      )}

      {/* Label card */}
      <div style={{
        position: 'absolute',
        top:  Math.max(16, Math.min(cardTop,  window.innerHeight - 240)),
        left: Math.max(16, Math.min(cardLeft, window.innerWidth  - 316)),
        width: 300,
        border: '1px solid #00C805',
        background: '#0B0E11',
        boxShadow: '0 0 24px rgba(0,200,5,0.1)',
      }}>
        {/* Card header */}
        <div style={{
          padding: '8px 14px', display: 'flex', justifyContent: 'space-between',
          borderBottom: '1px solid #2B2F36', background: '#131720',
        }}>
          <span style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 10, color: '#00C805', letterSpacing: '0.15em' }}>
            {step.label}
          </span>
          <span style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 10, color: '#5A6070' }}>
            BLUEPRINT
          </span>
        </div>

        {/* Card body */}
        <div style={{ padding: 16 }}>
          <div style={{ fontFamily: 'Playfair Display,serif', fontSize: 14, color: '#E8EAF0', marginBottom: 8 }}>
            {step.title}
          </div>
          <p style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 11, color: '#5A6070', lineHeight: 1.7, marginBottom: 16 }}>
            {step.body}
          </p>
          <button
            onClick={next}
            style={{
              width: '100%', padding: '8px 0',
              background: '#00C805', color: '#0B0E11', border: 'none',
              fontFamily: 'JetBrains Mono,monospace', fontSize: 11,
              fontWeight: 700, letterSpacing: '0.1em', cursor: 'pointer',
            }}
          >
            {isLast ? finishLabel : 'NEXT →'}
          </button>
        </div>
      </div>

      {/* Step dots */}
      <div style={{
        position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)',
        display: 'flex', gap: 8,
      }}>
        {steps.map((_, i) => (
          <button
            key={i}
            onClick={() => setActive(i)}
            style={{
              width: 6, height: 6, border: 'none', cursor: 'pointer',
              background: i === active ? '#00C805' : '#2B2F36',
            }}
          />
        ))}
      </div>
    </div>
  )
}
