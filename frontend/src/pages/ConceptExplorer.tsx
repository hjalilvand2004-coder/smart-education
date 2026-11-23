import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { ConceptMapData, MapNodeCard } from '../api'

/** نقشه مفاهیم قابل‌کاوش — دو نمایش: مسیر ساده روزمره + گراف کاوشی. */
export default function ConceptExplorer({ courseId }: { courseId: string }) {
  const [mode, setMode] = useState<'simple' | 'full'>('simple')
  const [data, setData] = useState<ConceptMapData | null>(null)
  const [selected, setSelected] = useState<MapNodeCard | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.title = 'نقشه مفاهیم | دانشجو۳۶۰'
  }, [])

  const load = useCallback((m: 'simple' | 'full') => {
    let alive = true
    setData(null)
    setSelected(null)
    api
      .get<ConceptMapData>(`/me/courses/${courseId}/concept-map?mode=${m}`)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e instanceof Error ? e.message : 'خطا در دریافت نقشه'))
    return () => {
      alive = false
    }
  }, [courseId])

  useEffect(() => {
    load(mode)
  }, [mode, load])

  const stageLabel = (i: number, total: number) =>
    total > 1 ? `مرحله ${i + 1} از ${total} — پایه‌ها اول` : 'همه مفاهیم'

  return (
    <div>
      <div className="page-header">
        <h1>🗺 نقشه مفاهیم — رصدخانه درس</h1>
        <div className="muted">
          مفاهیم مانند نقاط روشن‌اند؛ با انتخاب هر نقطه، توضیح ساده، پیش‌نیازها، کاربرد واقعی،
          شواهد و تمرین پیشنهادی همان مفهوم باز می‌شود.
        </div>
        <div className="tabs" role="tablist" aria-label="نوع نمایش">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'simple'}
            className={`tab${mode === 'simple' ? ' active' : ''}`}
            onClick={() => setMode('simple')}
          >
            مسیر ساده (روزمره)
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'full'}
            className={`tab${mode === 'full' ? ' active' : ''}`}
            onClick={() => setMode('full')}
          >
            نمای گرافیکی (کاوش)
          </button>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}
      {!data && !error && (
        <div className="center-note">
          <div className="spinner" />
        </div>
      )}

      {data && mode === 'simple' && (
        <div className="stage-path">
          {(data.stages ?? []).map((stage, si) => (
            <div key={si} className="stage-block">
              <div className="st-title">{stageLabel(si, data.stages?.length ?? 1)}</div>
              <div className="st-items">
                {stage.map((n) => (
                  <button
                    key={n.concept_id}
                    type="button"
                    className="map-node"
                    onClick={() => setMode('full')}
                    title={n.state_label ?? ''}
                  >
                    <span className={`dot ${n.status}`} />
                    {n.concept_name}
                    {n.next_step && <span className="muted" style={{ fontSize: '0.7rem' }}>→ {n.next_step.label}</span>}
                  </button>
                ))}
              </div>
            </div>
          ))}
          <p className="muted" style={{ fontSize: '0.8rem' }}>
            برای کارت کامل هر مفهوم (توضیح، پیش‌نیاز، کاربرد، تمرین و پرسش از استاد)، «نمای گرافیکی» را باز کنید.
          </p>
        </div>
      )}

      {data && mode === 'full' && (
        <>
          <p className="muted" style={{ fontSize: '0.85rem' }}>
            یک مفهوم را انتخاب کنید تا کارت کامل آن باز شود:
          </p>
          <div className="st-items" style={{ marginBottom: 6 }}>
            {(data.nodes ?? []).map((n) => (
              <button
                key={n.concept_id}
                type="button"
                className={`map-node${selected?.concept_id === n.concept_id ? ' on' : ''}`}
                onClick={() => setSelected(n)}
              >
                <span className={`dot ${n.status}`} />
                {n.concept_name}
              </button>
            ))}
          </div>

          {selected && (
            <div className="concept-card">
              <h2 style={{ fontSize: '1.1rem' }}>
                {selected.concept_name}{' '}
                <span className="muted" style={{ fontSize: '0.8rem' }}>
                  ({selected.card.evidence.state_label ?? 'نامشخص'})
                </span>
              </h2>
              <p style={{ fontSize: '0.9rem', lineHeight: 2 }}>{selected.card.simple_explanation}</p>
              <div className="cc-row">
                {selected.card.real_use && (
                  <span className="chip">🧪 کاربرد واقعی: {selected.card.real_use}</span>
                )}
                {selected.card.prerequisites.map((p) => (
                  <span key={p} className="chip">↩ پیش‌نیاز: {p}</span>
                ))}
                {selected.card.common_pitfalls.map((m) => (
                  <span key={m} className="chip" style={{ borderColor: 'var(--warn-border)' }}>
                    ⚠ بدفهمی رایج: {m}
                  </span>
                ))}
                <span className="chip">📊 شواهد: {selected.card.evidence.count} پاسخ</span>
              </div>
              <div className="btn-row" style={{ marginTop: 12 }}>
                <Link className="btn btn-primary btn-sm" to={selected.card.practice.url}>
                  {selected.card.practice.label}
                </Link>
                <Link className="btn btn-sm" to={selected.card.ask_tutor.url}>
                  {selected.card.ask_tutor.label}
                </Link>
              </div>
            </div>
          )}
          {data.legend_note && (
            <p className="muted" style={{ fontSize: '0.78rem', marginTop: 10 }}>
              {data.legend_note}
            </p>
          )}
        </>
      )}
    </div>
  )
}
