import { Fragment } from 'react'

// Renders the answer with every citation marker turned into a clickable chip.
//
// There are two marker formats, because the two endpoints number their sources
// differently: /api/ask uses [C1], [C2] against the clauses it was given, and
// /api/agent uses [S1], [S2] - a label its own search issued, since it chose what to
// retrieve (D-089). Both arrive as `citations` with a `marker` field, so the renderer
// just looks each bracketed token up in that list and needs no rule of its own.

const MARKER = /\[([^\]\s][^\]]*)\]/g

function ReasonNote({ reason }) {
  const [kind, ...rest] = (reason || '').split(':')
  const extra = rest.join(':').trim()

  const explanations = {
    outside_delhi:
      'That point is outside Delhi, so the Master Plan for Delhi 2047 does not apply to it.',
    weak_retrieval:
      'Nothing in the indexed documents came close enough to this question to answer it from.',
    citation_check_failed:
      'An answer was written twice but could not be traced back to the clauses, so it was discarded rather than shown.',
    model_abstained: 'The retrieved clauses do not answer this question.',
    max_rounds_reached:
      'The agent used all its tool calls without reaching an answer.',
    no_llm: 'No API key is configured, so no answer can be written.',
  }

  return (
    <div className="abstain">
      <h3>No answer given</h3>
      <p>{explanations[kind] || 'This question could not be answered from the documents.'}</p>
      {extra && <p className="abstain-detail">{extra}</p>}
      <p className="muted">
        Declining is a deliberate outcome, not a failure: an answer with nothing behind it
        would be worse than none. The clauses that were found are listed below.
      </p>
    </div>
  )
}

function CitedText({ text, citations, onOpen }) {
  const byMarker = new Map(citations.map((citation) => [citation.marker, citation]))
  const pieces = []
  let cursor = 0
  let key = 0

  for (const match of text.matchAll(MARKER)) {
    const citation = byMarker.get(match[1])
    if (!citation) continue
    if (match.index > cursor) {
      pieces.push(<Fragment key={key++}>{text.slice(cursor, match.index)}</Fragment>)
    }
    const number = citations.indexOf(citation) + 1
    pieces.push(
      <button
        key={key++}
        type="button"
        className="cite"
        onClick={() => onOpen(citation)}
        title={`${citation.doc_title} - clause ${citation.clause_id || 'not numbered'}, pages ${citation.page_start}-${citation.page_end}`}
      >
        {number}
      </button>,
    )
    cursor = match.index + match[0].length
  }
  if (cursor < text.length) pieces.push(<Fragment key={key++}>{text.slice(cursor)}</Fragment>)

  return <div className="answer-text">{pieces}</div>
}

export default function AnswerPanel({ result, onOpenCitation, onOpenChunk }) {
  if (!result) return null

  const clauses = result.retrieval || []

  return (
    <section className="answer">
      {result.abstained ? (
        <ReasonNote reason={result.abstain_reason} />
      ) : (
        <>
          <h3>Answer</h3>
          <CitedText
            text={result.answer_markdown || ''}
            citations={result.citations || []}
            onOpen={onOpenCitation}
          />
          {result.citations?.length > 0 && (
            <ol className="sources">
              {result.citations.map((citation, index) => (
                <li key={citation.marker}>
                  <button type="button" className="link" onClick={() => onOpenCitation(citation)}>
                    {index + 1}. {citation.doc_title}
                    {citation.clause_id ? `, clause ${citation.clause_id}` : ''}, pages{' '}
                    {citation.page_start}-{citation.page_end}
                  </button>
                </li>
              ))}
            </ol>
          )}
        </>
      )}

      {clauses.length > 0 && (
        <details className="clause-list" open={result.abstained}>
          <summary>{clauses.length} clause(s) retrieved for this question</summary>
          <ul>
            {clauses.map((clause) => (
              <li key={clause.chunk_id}>
                <button type="button" className="link" onClick={() => onOpenChunk(clause.chunk_id)}>
                  {clause.clause_id ? `Clause ${clause.clause_id}` : clause.chunk_id} &mdash; pages{' '}
                  {clause.page_start}-{clause.page_end}
                </button>
                <p className="snippet">{(clause.text || '').slice(0, 180)}...</p>
              </li>
            ))}
          </ul>
        </details>
      )}

      {typeof result.latency_ms === 'number' && (
        <p className="muted small">
          {result.llm_calls} model call(s), {(result.latency_ms / 1000).toFixed(1)}s
        </p>
      )}
    </section>
  )
}
