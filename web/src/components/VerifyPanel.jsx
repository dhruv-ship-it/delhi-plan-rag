import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { MapContainer, Marker, TileLayer } from 'react-leaflet'
import {
  getDevQuestion,
  getDevQuestions,
  postDevDecision,
  postDevLeakage,
} from '../api.js'
import { markerIcon } from '../marker.js'

// The question verification screen. Shown only when /api/health reports dev_mode, and
// the endpoints behind it 404 without ZONEWISE_DEV=1, so this is a convenience rather
// than a second access control (see app/api.py and D-075).
//
// The shape of the screen follows the shape of the job. Verifying a question means
// answering four things — does the expected clause really answer this, is the one-line
// answer right, would a person ask it this way, and does the rewrite still avoid naming
// the zone — and all four need the clause text and the retrieval results visible at the
// same time as the editable question. So everything is on one screen and the keyboard
// does the navigation: A accept, E save edit, R reject, S skip, arrows for next and
// previous (D-076).

const SHORTCUTS = { a: 'accepted', e: 'edited', r: 'rejected', s: 'skipped' }

// Long enough that it does not fire on every keystroke, short enough to feel live.
const LEAKAGE_DELAY_MS = 350

function statusLabel(status) {
  if (status === 'pending') return ''
  return status
}

export default function VerifyPanel() {
  const [list, setList] = useState(null)
  const [listError, setListError] = useState(null)
  const [position, setPosition] = useState(0)

  const [detail, setDetail] = useState(null)
  const [detailError, setDetailError] = useState(null)
  const [loading, setLoading] = useState(false)

  const [text, setText] = useState('')
  const [expected, setExpected] = useState([])
  const [acceptable, setAcceptable] = useState([])
  const [shouldAbstain, setShouldAbstain] = useState(false)
  const [notes, setNotes] = useState('')

  const [leaks, setLeaks] = useState([])
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [saved, setSaved] = useState(null)

  const textarea = useRef(null)

  const questions = list?.questions ?? []
  const current = questions[position] ?? null

  const refreshList = useCallback(async () => {
    try {
      setList(await getDevQuestions())
    } catch (error) {
      setListError(error.message)
    }
  }, [])

  useEffect(() => {
    refreshList()
  }, [refreshList])

  // Load one question and reset the form to what is stored for it.
  useEffect(() => {
    if (!current) return
    let cancelled = false
    setLoading(true)
    setDetailError(null)
    setSaved(null)
    setSaveError(null)
    getDevQuestion(current.id)
      .then((found) => {
        if (cancelled) return
        setDetail(found)
        setText(found.question)
        setExpected(found.expected_chunk_ids)
        setAcceptable(found.acceptable_chunk_ids)
        setShouldAbstain(found.should_abstain)
        setNotes(found.notes)
        setLeaks(found.leakage)
      })
      .catch((error) => !cancelled && setDetailError(error.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [current?.id])

  // The live leakage warning. Debounced, and it never blocks typing: the check is a
  // string comparison on the server against this question's own chunks.
  useEffect(() => {
    if (!detail) return
    const handle = setTimeout(async () => {
      try {
        const found = await postDevLeakage(detail.id, text)
        setLeaks(found.shared_word_runs)
      } catch {
        // a failed check must not stop the review; the save path checks again
      }
    }, LEAKAGE_DELAY_MS)
    return () => clearTimeout(handle)
  }, [text, detail?.id])

  const edited = useMemo(
    () => detail !== null && text.trim() !== detail.question.trim(),
    [text, detail],
  )

  const move = useCallback(
    (step) => {
      setPosition((at) => Math.min(Math.max(at + step, 0), Math.max(questions.length - 1, 0)))
    },
    [questions.length],
  )

  const save = useCallback(
    async (status) => {
      if (!detail || saving) return
      setSaving(true)
      setSaveError(null)
      try {
        const result = await postDevDecision(detail.id, {
          status,
          question: text,
          expected_chunk_ids: expected,
          acceptable_chunk_ids: acceptable,
          should_abstain: shouldAbstain,
          notes,
        })
        setSaved(result)
        await refreshList()
        if (position < questions.length - 1) move(1)
      } catch (error) {
        setSaveError(error.message)
      } finally {
        setSaving(false)
      }
    },
    [
      detail,
      saving,
      text,
      expected,
      acceptable,
      shouldAbstain,
      notes,
      refreshList,
      position,
      questions.length,
      move,
    ],
  )

  // Keyboard shortcuts, ignored while the caret is in a text box so typing an "a" in a
  // question does not accept it.
  useEffect(() => {
    function onKey(event) {
      const tag = event.target.tagName
      if (tag === 'TEXTAREA' || tag === 'INPUT' || event.metaKey || event.ctrlKey) return
      if (event.key === 'ArrowRight') return move(1)
      if (event.key === 'ArrowLeft') return move(-1)
      const status = SHORTCUTS[event.key.toLowerCase()]
      if (status) {
        event.preventDefault()
        save(status)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [move, save])

  function toggleId(listOfIds, setList_, chunkId) {
    setList_(
      listOfIds.includes(chunkId)
        ? listOfIds.filter((id) => id !== chunkId)
        : [...listOfIds, chunkId],
    )
  }

  if (listError) {
    return (
      <section className="verify">
        <p className="error">
          Could not load the questions. {listError} Is the backend running with{' '}
          <code>ZONEWISE_DEV=1</code>?
        </p>
      </section>
    )
  }
  if (!list) return <p className="muted">Loading the question set...</p>

  const done = list.progress.done
  const total = list.progress.total

  return (
    <section className="verify">
      <header className="verify-top">
        <strong>
          {done} / {total} done
        </strong>
        <span className="muted">
          {list.progress.accepted} accepted, {list.progress.edited} edited,{' '}
          {list.progress.rejected} rejected
        </span>
        <span className="verify-nav">
          <button type="button" onClick={() => move(-1)} disabled={position === 0}>
            &larr; Previous
          </button>
          <span className="muted">
            {position + 1} of {questions.length}
          </span>
          <button
            type="button"
            onClick={() => move(1)}
            disabled={position >= questions.length - 1}
          >
            Next &rarr;
          </button>
        </span>
      </header>

      <p className="muted verify-help">
        Keys: <kbd>A</kbd> accept &middot; <kbd>E</kbd> save edit &middot; <kbd>R</kbd>{' '}
        reject &middot; <kbd>S</kbd> skip &middot; <kbd>&larr;</kbd> <kbd>&rarr;</kbd> move.
        Shortcuts are off while you are typing.
      </p>

      {detailError && <p className="error">{detailError}</p>}
      {loading && <p className="muted">Loading question...</p>}

      {detail && !loading && (
        <>
          <div className="verify-meta">
            <span className="chip chip-zone">{detail.id}</span>
            <span className="chip">{detail.category}</span>
            {detail.point_name && <span className="chip">{detail.point_name}</span>}
            {current?.status !== 'pending' && (
              <span className="chip chip-policy">{statusLabel(current.status)}</span>
            )}
          </div>

          <label className="verify-label" htmlFor="verify-question">
            The question &mdash; rewrite it in your own words
          </label>
          <textarea
            id="verify-question"
            ref={textarea}
            className="verify-question"
            rows={3}
            value={text}
            maxLength={500}
            onChange={(event) => setText(event.target.value)}
          />
          {leaks.length > 0 ? (
            <p className="error">
              <strong>Leakage:</strong> this question copies{' '}
              {leaks.map((run) => `"${run}"`).join(', ')} from a chunk it points at.
              Reword it &mdash; a question that quotes its own answer tests nothing.
            </p>
          ) : (
            <p className="muted">No copied word runs. {edited ? 'Edited.' : 'Unchanged.'}</p>
          )}

          {detail.expected_answer_short && (
            <p className="muted">
              <strong>Claude&rsquo;s one-line answer:</strong> {detail.expected_answer_short}
            </p>
          )}

          <div className="verify-row">
            <label className="verify-toggle">
              <input
                type="checkbox"
                checked={shouldAbstain}
                onChange={(event) => setShouldAbstain(event.target.checked)}
              />
              Should abstain &mdash; the documents do not answer this
            </label>
          </div>

          {detail.lat != null && (
            <div className="verify-map">
              <MapContainer
                center={[detail.lat, detail.lon]}
                zoom={12}
                scrollWheelZoom={false}
                style={{ height: '160px' }}
              >
                <TileLayer
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  attribution="&copy; OpenStreetMap contributors"
                />
                <Marker position={[detail.lat, detail.lon]} icon={markerIcon} />
              </MapContainer>
              <p className="muted">
                {detail.point_name}: {detail.lat.toFixed(5)}, {detail.lon.toFixed(5)}
                {detail.zones?.planning_zone
                  ? ` — planning zone ${detail.zones.planning_zone}`
                  : ''}
              </p>
            </div>
          )}

          <h3>Expected clause{detail.expected_chunks.length === 1 ? '' : 's'}, in full</h3>
          {detail.expected_chunks.length === 0 ? (
            <p className="muted">
              None &mdash; correct for a should-abstain question, wrong for anything else.
            </p>
          ) : (
            detail.expected_chunks.map((chunk) => (
              <article key={chunk.chunk_id} className="verify-chunk">
                <p className="verify-chunk-head">
                  <code>{chunk.chunk_id}</code> &mdash; pages {chunk.page_start}-
                  {chunk.page_end}
                  {chunk.zone_primary ? ` — zone ${chunk.zone_primary}` : ''}
                </p>
                <p className="verify-chunk-path">{chunk.heading_path.join(' › ')}</p>
                <pre className="verify-chunk-text">{chunk.text}</pre>
              </article>
            ))
          )}

          <h3>Current top {detail.top_results.length} from hybrid+location</h3>
          <p className="muted">
            Click a result to mark it expected; click again for acceptable, again to clear.
          </p>
          <ol className="verify-results">
            {detail.top_results.map((result) => {
              const isExpected = expected.includes(result.chunk_id)
              const isAcceptable = acceptable.includes(result.chunk_id)
              return (
                <li key={result.chunk_id} className={result.is_expected ? 'hit' : ''}>
                  <div className="verify-result-head">
                    <code>{result.chunk_id}</code>
                    <span className="muted">
                      pages {result.page_start}-{result.page_end}
                      {result.dense_cosine != null
                        ? ` · cosine ${result.dense_cosine.toFixed(3)}`
                        : ''}
                    </span>
                  </div>
                  <p className="snippet">{result.text.slice(0, 260)}...</p>
                  <div className="verify-result-actions">
                    <button
                      type="button"
                      className={isExpected ? 'mode on' : 'mode'}
                      onClick={() => {
                        toggleId(expected, setExpected, result.chunk_id)
                        if (isAcceptable) toggleId(acceptable, setAcceptable, result.chunk_id)
                      }}
                    >
                      {isExpected ? 'Expected ✓' : 'Mark expected'}
                    </button>
                    <button
                      type="button"
                      className={isAcceptable ? 'mode on' : 'mode'}
                      onClick={() => {
                        toggleId(acceptable, setAcceptable, result.chunk_id)
                        if (isExpected) toggleId(expected, setExpected, result.chunk_id)
                      }}
                    >
                      {isAcceptable ? 'Acceptable ✓' : 'Mark acceptable'}
                    </button>
                  </div>
                </li>
              )
            })}
          </ol>

          <p className="muted">
            Expected: {expected.length ? expected.join(', ') : 'none'} &middot; acceptable:{' '}
            {acceptable.length ? acceptable.join(', ') : 'none'}
          </p>

          <label className="verify-label" htmlFor="verify-notes">
            Notes
          </label>
          <textarea
            id="verify-notes"
            rows={2}
            value={notes}
            maxLength={1000}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Anything the next reader should know about this question."
          />

          {saveError && <p className="error">{saveError}</p>}
          {saved && (
            <p className="notice">
              Saved <code>{saved.saved.id}</code> as <strong>{saved.saved.status}</strong>{' '}
              to <code>{saved.path}</code>
              {saved.replaced ? ' (replacing an earlier decision)' : ''}.
            </p>
          )}

          <div className="verify-actions">
            <button type="button" className="ask" disabled={saving} onClick={() => save('accepted')}>
              Accept <kbd>A</kbd>
            </button>
            <button type="button" className="mode" disabled={saving} onClick={() => save('edited')}>
              Save edit <kbd>E</kbd>
            </button>
            <button type="button" className="mode" disabled={saving} onClick={() => save('rejected')}>
              Reject <kbd>R</kbd>
            </button>
            <button type="button" className="mode" disabled={saving} onClick={() => save('skipped')}>
              Skip <kbd>S</kbd>
            </button>
          </div>
        </>
      )}
    </section>
  )
}
