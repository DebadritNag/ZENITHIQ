/**
 * NarrativeConflictPanel
 * ----------------------
 * Displays the filing vs. news narrative conflict level and key points.
 */

import { AlertTriangle, CheckCircle, Info } from 'lucide-react'
import type { NarrativeConflict } from '../types'

interface Props {
  data: NarrativeConflict
}

const LEVEL_CFG = {
  NONE:     { color: '#00C805', bg: '#002B01', Icon: CheckCircle  },
  LOW:      { color: '#F59E0B', bg: '#2D1F00', Icon: Info         },
  MEDIUM:   { color: '#F59E0B', bg: '#2D1F00', Icon: Info         },
  STRONG:   { color: '#E31B23', bg: '#3D0A0C', Icon: AlertTriangle },
  CRITICAL: { color: '#E31B23', bg: '#3D0A0C', Icon: AlertTriangle },
}

export function NarrativeConflictPanel({ data }: Props) {
  const cfg = LEVEL_CFG[data.level] ?? LEVEL_CFG.MEDIUM

  return (
    <div style={{ border: '1px solid #2B2F36', background: '#131720', padding: 20 }}>
      <div style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 9, letterSpacing: '0.15em', color: '#5A6070', textTransform: 'uppercase', marginBottom: 12 }}>
        Narrative Conflict · Filing vs. Reality
      </div>

      {/* Level badge */}
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '5px 10px', marginBottom: 12,
        border: `1px solid ${cfg.color}`, background: cfg.bg,
      }}>
        <cfg.Icon size={12} color={cfg.color} />
        <span style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 11, fontWeight: 700, color: cfg.color }}>
          {data.level}
        </span>
      </div>

      {/* Summary */}
      {data.summary && (
        <p style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 11, color: '#E8EAF0', lineHeight: 1.7, marginBottom: 12 }}>
          {data.summary}
        </p>
      )}

      {/* Conflict points */}
      {data.points.length > 0 && (
        <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {data.points.map((pt, i) => (
            <li key={i} style={{
              display: 'flex', gap: 8, padding: '6px 8px',
              border: '1px solid #2B2F36', borderLeft: `2px solid ${cfg.color}`,
              fontFamily: 'JetBrains Mono,monospace', fontSize: 10, color: '#E8EAF0',
            }}>
              <span style={{ color: cfg.color, flexShrink: 0 }}>▸</span>
              {pt}
            </li>
          ))}
        </ul>
      )}

      {data.points.length === 0 && (
        <div style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 10, color: '#3A3F4A' }}>
          No specific conflict points detected.
        </div>
      )}
    </div>
  )
}
