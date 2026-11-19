import { useState } from 'react'
import type { ConceptGraph, ConceptNode, MasteryStatus } from '../api'

interface NodePos extends ConceptNode {
  x: number
  y: number
}

const MASTERY_COLORS: Record<MasteryStatus, { fill: string; label: string }> = {
  UNKNOWN: { fill: '#9ca3af', label: 'نامشخص' },
  WEAK: { fill: '#fca5a5', label: 'ضعیف' },
  PARTIAL: { fill: '#fde047', label: 'جزئی' },
  KNOWN: { fill: '#6ee7b7', label: 'مسلط' },
}

const EDGE_LABELS: Record<string, string> = {
  PREREQUISITE_OF: 'پیش‌نیاز',
  PART_OF: 'جزء',
  RELATED_TO: 'مرتبط',
  APPLIED_IN: 'کاربرد در',
  MISCONCEPTION_OF: 'بدفهمی',
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

/**
 * گراف مفاهیم با چیدمان دایره‌ای؛ رنگ هر نود بر اساس وضعیت تسلط کاربر
 * (برای کارکنان بدون داده تسلط، همه نودها «نامشخص» دیده می‌شود).
 */
export default function ConceptMap({ graph }: { graph: ConceptGraph }) {
  const [tooltip, setTooltip] = useState<{ node: ConceptNode; x: number; y: number } | null>(null)

  if (!graph.nodes || graph.nodes.length === 0) {
    return <div className="empty-box"><strong>نقشه مفاهیم خالی است</strong>برای این درس هنوز مفهومی ثبت نشده است.</div>
  }

  const W = 760
  const H = 560
  const cx = W / 2
  const cy = H / 2
  const radius = Math.max(160, Math.min(235, 105 + graph.nodes.length * 9))

  const nodes: NodePos[] = graph.nodes.map((n, i) => {
    const angle = (2 * Math.PI * i) / graph.nodes.length - Math.PI / 2
    return {
      ...n,
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    }
  })
  const posById = new Map(nodes.map((n) => [n.id, n]))

  return (
    <div style={{ position: 'relative' }}>
      <div className="concept-map-wrap">
        <svg className="concept-map-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="نقشه مفاهیم درس">
          {/* یال‌ها */}
          {graph.edges.map((e, i) => {
            const a = posById.get(e.from)
            const b = posById.get(e.to)
            if (!a || !b) return null
            const isPrereq = e.type === 'PREREQUISITE_OF'
            return (
              <line
                key={i}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke={isPrereq ? '#2563eb' : '#cbd5e1'}
                strokeWidth={isPrereq ? 2 : 1.4}
                strokeDasharray={isPrereq ? undefined : '5 4'}
              >
                <title>{`${a.name} ← ${b.name} (${EDGE_LABELS[e.type] || e.type})`}</title>
              </line>
            )
          })}
          {/* نودها */}
          {nodes.map((n) => {
            const masteryStatus: MasteryStatus = n.mastery?.status ?? 'UNKNOWN'
            const color = MASTERY_COLORS[masteryStatus]?.fill || MASTERY_COLORS.UNKNOWN.fill
            return (
              <g
                key={n.id}
                transform={`translate(${n.x}, ${n.y})`}
                style={{ cursor: 'pointer' }}
                onMouseEnter={(ev) => {
                  const rect = (ev.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
                  setTooltip({ node: n, x: ev.clientX - rect.left, y: ev.clientY - rect.top })
                }}
                onMouseLeave={() => setTooltip(null)}
              >
                <circle r={26} fill={color} stroke="#ffffff" strokeWidth={2.5} />
                <circle r={26} fill="transparent" stroke="#94a3b8" strokeWidth={1} />
                <text textAnchor="middle" dy="0.35em" fontSize="11" fill="#1f2937" fontWeight="700">
                  {truncate(n.name, 3)}
                </text>
                <text textAnchor="middle" y={42} fontSize="11.5" fill="#334155" fontWeight="700">
                  {truncate(n.name, 16)}
                </text>
                <text textAnchor="middle" y={57} fontSize="9.5" fill="#6b7280">
                  تسلط: {MASTERY_COLORS[masteryStatus]?.label || 'نامشخص'}
                </text>
                <title>{`${n.name} — تسلط: ${MASTERY_COLORS[masteryStatus]?.label || 'نامشخص'}`}</title>
              </g>
            )
          })}
        </svg>
        {tooltip && (
          <div className="map-tooltip" style={{ left: Math.min(tooltip.x + 14, 320), top: tooltip.y + 14 }}>
            <strong>{tooltip.node.name}</strong>
            <div>{tooltip.node.description || 'بدون توضیح ثبت‌شده'}</div>
            <div style={{ marginTop: 4 }}>
              وضعیت تسلط: {MASTERY_COLORS[tooltip.node.mastery?.status ?? 'UNKNOWN']?.label}
              {tooltip.node.mastery?.estimated_mastery != null &&
                ` (${Math.round(tooltip.node.mastery.estimated_mastery * 100)}٪)`}
            </div>
          </div>
        )}
      </div>
      <div className="map-legend">
        {(Object.keys(MASTERY_COLORS) as MasteryStatus[]).map((s) => (
          <span key={s}>
            <span className="legend-dot" style={{ background: MASTERY_COLORS[s].fill }} />
            {MASTERY_COLORS[s].label}
          </span>
        ))}
        <span>
          <span className="legend-dot" style={{ background: '#2563eb' }} />
          خط پیوسته: پیش‌نیاز — خط نقطه‌چین: سایر روابط
        </span>
      </div>
    </div>
  )
}
