import { useCallback, useEffect, useState } from 'react'
import MapView from './components/MapView.jsx'
import Legend from './components/Legend.jsx'
import ZoneChips from './components/ZoneChips.jsx'
import AnswerPanel from './components/AnswerPanel.jsx'
import ClauseDrawer from './components/ClauseDrawer.jsx'
import ToolTrace from './components/ToolTrace.jsx'
import VerifyPanel from './components/VerifyPanel.jsx'
import { EXAMPLE_POINT, LAYERS } from './layers.js'
import { getChunk, getHealth, getZones, postAgent, postAsk, postSearch } from './api.js'

const SPOT = 'spot'
const AGENT = 'agent'

// Two top-level views, switched by plain state rather than a router. There are two of
// them, one of which only exists in dev mode, so a routing dependency would be the
// seventh npm package for a boolean (D-059, D-076).
const ASK_VIEW = 'ask'
const VERIFY_VIEW = 'verify'

export default function App() {
  const [health, setHealth] = useState(null)
  const [view, setView] = useState(ASK_VIEW)
  const [visible, setVisible] = useState(
    Object.fromEntries(LAYERS.map((layer) => [layer.name, layer.defaultOn])),
  )
  const [layerError, setLayerError] = useState(null)

  const [marker, setMarker] = useState(null)
  const [zones, setZones] = useState(null)
  const [zonesLoading, setZonesLoading] = useState(false)
  const [zonesError, setZonesError] = useState(null)

  const [mode, setMode] = useState(SPOT)
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [askError, setAskError] = useState(null)
  const [searchOnly, setSearchOnly] = useState(null)
  const [result, setResult] = useState(null)

  const [chunk, setChunk] = useState(null)
  const [chunkLoading, setChunkLoading] = useState(false)
  const [chunkError, setChunkError] = useState(null)

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((error) => setHealth({ status: 'unreachable', error: error.message }))
  }, [])

  const pickPoint = useCallback(async (lat, lon) => {
    setMarker({ lat, lon })
    setZones(null)
    setZonesError(null)
    setZonesLoading(true)
    try {
      setZones(await getZones(lat, lon))
    } catch (error) {
      setZonesError(error.message)
    } finally {
      setZonesLoading(false)
    }
  }, [])

  const toggleLayer = (name) =>
    setVisible((current) => ({ ...current, [name]: !current[name] }))

  async function submit(event) {
    event.preventDefault()
    const asked = question.trim()
    if (!asked) return
    if (mode === SPOT && !marker) {
      setAskError('Click a point on the map first, or switch to "Ask the agent".')
      return
    }

    setAsking(true)
    setAskError(null)
    setSearchOnly(null)
    setResult(null)
    try {
      const answer =
        mode === SPOT
          ? await postAsk({ question: asked, lat: marker.lat, lon: marker.lon })
          : await postAgent({ question: asked })
      setResult(answer)
    } catch (error) {
      if (error.isSearchOnly) {
        // No API key. Fall back to retrieval so the clauses are still shown.
        let clauses = error.detail?.results || []
        if (!clauses.length && mode === AGENT) {
          try {
            const found = await postSearch({ query: asked, k: 6 })
            clauses = found.results
          } catch {
            clauses = []
          }
        }
        setSearchOnly({ message: error.detail.message, results: clauses })
      } else {
        setAskError(error.message)
      }
    } finally {
      setAsking(false)
    }
  }

  async function openChunk(chunkId) {
    setChunk(null)
    setChunkError(null)
    setChunkLoading(true)
    try {
      setChunk(await getChunk(chunkId))
    } catch (error) {
      setChunkError(error.message)
    } finally {
      setChunkLoading(false)
    }
  }

  const closeDrawer = () => {
    setChunk(null)
    setChunkError(null)
    setChunkLoading(false)
  }

  const answersOff = health && health.llm_available === false
  const devMode = health?.dev_mode === true

  return (
    <div className="app">
      <header className="banner">
        <strong>ZoneWise</strong>
        <span>Not legal advice. Always check official DDA documents.</span>
        {devMode && (
          <span className="views" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={view === ASK_VIEW}
              className={view === ASK_VIEW ? 'mode on' : 'mode'}
              onClick={() => setView(ASK_VIEW)}
            >
              Ask
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={view === VERIFY_VIEW}
              className={view === VERIFY_VIEW ? 'mode on' : 'mode'}
              onClick={() => setView(VERIFY_VIEW)}
            >
              Verify
            </button>
          </span>
        )}
      </header>

      <p className="privacy-note">
        Questions are sent to a third-party AI provider (Groq); don&apos;t include personal
        information.
      </p>

      {devMode && view === VERIFY_VIEW ? (
        <main className="layout verify-layout">
          <VerifyPanel />
        </main>
      ) : (
      <main className="layout">
        <MapView
          marker={marker}
          onPick={pickPoint}
          visible={visible}
          onLayerError={setLayerError}
        />

        <section className="panel">
          {health?.status === 'unreachable' && (
            <p className="error">
              Cannot reach the ZoneWise server. Start it with{' '}
              <code>uv run python scripts/serve.py</code>.
            </p>
          )}
          {layerError && <p className="error">Some map layers did not load. {layerError}</p>}

          <h2>Where are you asking about?</h2>
          {!marker ? (
            <p className="muted">
              Click anywhere on the map to drop a pin.{' '}
              <button
                type="button"
                className="link"
                onClick={() => pickPoint(EXAMPLE_POINT.lat, EXAMPLE_POINT.lon)}
              >
                Or try {EXAMPLE_POINT.label}
              </button>
              .
            </p>
          ) : (
            <p className="coords">
              {marker.lat.toFixed(5)}, {marker.lon.toFixed(5)}
            </p>
          )}
          <ZoneChips zones={zones} loading={zonesLoading} error={zonesError} />

          <Legend visible={visible} onToggle={toggleLayer} />

          <h2>Ask a question</h2>
          <div className="modes" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={mode === SPOT}
              className={mode === SPOT ? 'mode on' : 'mode'}
              onClick={() => setMode(SPOT)}
            >
              Ask about this spot
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === AGENT}
              className={mode === AGENT ? 'mode on' : 'mode'}
              onClick={() => setMode(AGENT)}
            >
              Ask the agent
            </button>
          </div>

          <form onSubmit={submit}>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              rows={3}
              maxLength={1000}
              placeholder={
                mode === SPOT
                  ? 'How much of my plot can I build on?'
                  : 'What can I build near Dwarka Sector 21 metro station?'
              }
              aria-label="Your question"
            />
            <button type="submit" className="ask" disabled={asking}>
              {asking ? 'Working...' : mode === SPOT ? 'Ask about this spot' : 'Ask the agent'}
            </button>
          </form>

          {answersOff && (
            <p className="notice">
              <strong>Search-only mode.</strong> No Anthropic API key is configured, so
              questions return the relevant clauses to read rather than a written answer.
              Everything else &mdash; the map, the zones and clause search &mdash; works.
            </p>
          )}

          {askError && <p className="error">{askError}</p>}

          {searchOnly && (
            <section className="answer">
              <div className="notice">
                <h3>Search-only mode</h3>
                <p>{searchOnly.message}</p>
              </div>
              {searchOnly.results.length > 0 ? (
                <ul className="clause-list open">
                  {searchOnly.results.map((clause) => (
                    <li key={clause.chunk_id}>
                      <button
                        type="button"
                        className="link"
                        onClick={() => openChunk(clause.chunk_id)}
                      >
                        {clause.clause_id ? `Clause ${clause.clause_id}` : clause.chunk_id}{' '}
                        &mdash; pages {clause.page_start}-{clause.page_end}
                      </button>
                      <p className="snippet">{(clause.text || '').slice(0, 220)}...</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">No clauses were found for that question.</p>
              )}
            </section>
          )}

          {result && (
            <>
              {mode === AGENT && <ToolTrace trace={result.tool_trace} />}
              <AnswerPanel
                result={result}
                onOpenCitation={(citation) => openChunk(citation.chunk_id)}
                onOpenChunk={openChunk}
              />
            </>
          )}

          <footer className="foot">
            {health?.chunks ? (
              <span>
                {health.chunks} clauses indexed from the MPD-2047 gazette, the DDA FAQs, a
                Delhi High Court order.
              </span>
            ) : null}
          </footer>
        </section>
      </main>
      )}

      <ClauseDrawer
        chunk={chunk}
        loading={chunkLoading}
        error={chunkError}
        onClose={closeDrawer}
      />
    </div>
  )
}
