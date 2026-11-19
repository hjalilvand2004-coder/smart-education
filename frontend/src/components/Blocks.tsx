import { useEffect, useRef } from 'react'
import type { Block } from '../api'

declare global {
  interface Window {
    renderMathInElement?: (
      element: HTMLElement,
      options?: { delimiters?: { left: string; right: string; display: boolean }[]; ignoredTags?: string[] },
    ) => void
  }
}

const BLOCK_KIND_LABELS: Record<string, string> = {
  heading: 'عنوان',
  text: 'متن',
  definition: 'تعریف',
  note: 'نکته',
  worked_example: 'مثال حل‌شده',
  exercise: 'تمرین',
  table: 'جدول',
  formula: 'فرمول',
  image: 'تصویر',
  code: 'کد',
  self_check: 'خودارزیابی',
  summary: 'جمع‌بندی',
  reference: 'منبع',
}

/** رندر فرمول‌های KaTeX داخل یک عنصر (با چند تلاش تا CDN لود شود). */
export function renderFormulasIn(element: HTMLElement | null, attempts = 8): void {
  if (!element) return
  if (window.renderMathInElement) {
    window.renderMathInElement(element, {
      delimiters: [{ left: '$$', right: '$$', display: true }],
      ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'],
    })
    return
  }
  if (attempts > 0) {
    window.setTimeout(() => renderFormulasIn(element, attempts - 1), 400)
  }
}

function TableBlock({ block }: { block: Block }) {
  const columns = block.columns || []
  const rows = block.rows || []
  if (!columns.length && !rows.length) return null
  return (
    <div className="table-wrap">
      <table className="table">
        {columns.length > 0 && (
          <thead>
            <tr>
              {columns.map((c, i) => (
                <th key={i}>{c}</th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {row.map((cell, ci) => (
                <td key={ci}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function BlockBody({ block }: { block: Block }) {
  switch (block.type) {
    case 'heading':
      return (
        <>
          {block.title && <h3>{block.title}</h3>}
          {block.body && <p>{block.body}</p>}
        </>
      )
    case 'table':
      return (
        <>
          {block.title && <h4>{block.title}</h4>}
          <TableBlock block={block} />
        </>
      )
    case 'formula':
      return (
        <>
          {block.title && <h4>{block.title}</h4>}
          <div className="formula">{`$$${block.formula || ''}$$`}</div>
        </>
      )
    case 'code':
      return (
        <>
          {block.language && <div className="code-lang">زبان: {block.language}</div>}
          <pre>
            <code>{block.body || ''}</code>
          </pre>
        </>
      )
    case 'worked_example':
      return (
        <>
          {block.title && <h4>{block.title}</h4>}
          {block.question && <p><strong>صورت مسئله:</strong> {block.question}</p>}
          {block.steps && block.steps.length > 0 && (
            <ol className="steps-list">
              {block.steps.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
          )}
          {block.answer && <p><strong>نتیجه:</strong> {block.answer}</p>}
          {block.explanation && <p className="muted">{block.explanation}</p>}
        </>
      )
    case 'exercise':
      return (
        <>
          {block.title && <h4>{block.title}</h4>}
          {block.question && <p>{block.question}</p>}
          {block.items && block.items.length > 0 && (
            <ul>
              {block.items.map((it, i) => (
                <li key={i}>{it}</li>
              ))}
            </ul>
          )}
        </>
      )
    case 'self_check':
      return (
        <>
          {block.title && <h4>{block.title}</h4>}
          {block.question && <p>{block.question}</p>}
          {block.answer && (
            <details className="details-box">
              <summary>نمایش پاسخ پیشنهادی</summary>
              <p>{block.answer}</p>
              {block.explanation && <p className="muted">{block.explanation}</p>}
            </details>
          )}
        </>
      )
    case 'reference':
      return (
        <>
          {block.title && <h4>{block.title}</h4>}
          {block.items && block.items.length > 0 && (
            <ul>
              {block.items.map((it, i) => (
                <li key={i}>{it}</li>
              ))}
            </ul>
          )}
        </>
      )
    default:
      // text / definition / note / summary / image
      return (
        <>
          {block.title && <h4>{block.title}</h4>}
          {block.body && <p>{block.body}</p>}
          {block.items && block.items.length > 0 && (
            <ul>
              {block.items.map((it, i) => (
                <li key={i}>{it}</li>
              ))}
            </ul>
          )}
        </>
      )
  }
}

/** رندر فهرست بلوک‌های محتوا با استایل متمایز برای هر نوع. */
export default function Blocks({ blocks }: { blocks: Block[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    renderFormulasIn(containerRef.current)
  }, [blocks])

  if (!blocks || blocks.length === 0) {
    return <div className="empty-box">هنوز محتوایی برای نمایش وجود ندارد.</div>
  }

  return (
    <div ref={containerRef}>
      {blocks.map((block) => (
        <section key={block.id} className={`block block-${block.type}`}>
          <span className="block-kind">{BLOCK_KIND_LABELS[block.type] || block.type}</span>
          <BlockBody block={block} />
        </section>
      ))}
    </div>
  )
}
