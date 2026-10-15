// The drawer that opens when a citation chip is clicked: the clause in full, with the
// document it is from, its number, its pages and a link to the source PDF. This is the
// point of citing at all, so it has to be one click away from any marker in the answer.

export default function ClauseDrawer({ chunk, loading, error, onClose }) {
  if (!chunk && !loading && !error) return null

  return (
    <aside className="drawer" role="dialog" aria-label="Clause text">
      <div className="drawer-head">
        <h3>{loading ? 'Loading clause...' : chunk?.doc_title || 'Clause'}</h3>
        <button type="button" className="close" onClick={onClose} aria-label="Close">
          &times;
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {chunk && (
        <>
          <dl className="meta">
            {chunk.chapter_title && (
              <>
                <dt>Chapter</dt>
                <dd>
                  {chunk.chapter} &mdash; {chunk.chapter_title}
                </dd>
              </>
            )}
            {chunk.heading_path?.length > 0 && (
              <>
                <dt>Section</dt>
                <dd>{chunk.heading_path.join(' › ')}</dd>
              </>
            )}
            <dt>Clause</dt>
            <dd>{chunk.clause_id || 'not numbered'}</dd>
            <dt>Pages</dt>
            <dd>
              {chunk.page_start}
              {chunk.page_end !== chunk.page_start ? `-${chunk.page_end}` : ''}
            </dd>
            <dt>Authority</dt>
            <dd>
              rank {chunk.authority_rank}{' '}
              {chunk.authority_rank === 1
                ? '(gazette notification, the law)'
                : chunk.authority_rank === 2
                  ? '(court order)'
                  : '(FAQ, explainer or report)'}
            </dd>
          </dl>

          <pre className="clause-text">{chunk.text}</pre>

          {chunk.source_url && (
            <p>
              <a href={chunk.source_url} target="_blank" rel="noreferrer">
                Open the source document
              </a>{' '}
              <span className="muted small">
                (page {chunk.page_start} of the original PDF)
              </span>
            </p>
          )}
          <p className="muted small">{chunk.chunk_id}</p>
        </>
      )}
    </aside>
  )
}
