// Every call to the ZoneWise backend goes through this file, so there is one place
// that knows the URLs and one shape of error for the interface to handle.
//
// The important case is a 503 from /api/ask or /api/agent: that is not a failure, it is
// "no API key is configured yet, and here are the clauses anyway". The thrown error
// carries the body so the interface can switch into search-only mode and still show
// them (see app/api.py and D-050).

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }

  // True when the backend has no API key: the question was understood, the clauses were
  // retrieved, but no answer can be written.
  get isSearchOnly() {
    return this.status === 503 && this.detail?.error === 'no_llm'
  }

  get isRateLimited() {
    return this.status === 429
  }
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(path, options)
  } catch {
    throw new ApiError(
      'Could not reach the ZoneWise server. Is it running on port 8000?',
      0,
      null,
    )
  }

  let body = null
  try {
    body = await response.json()
  } catch {
    body = null
  }

  if (!response.ok) {
    const detail = body?.detail ?? null
    const message =
      (typeof detail === 'string' ? detail : detail?.message) ||
      `Request failed (${response.status})`
    throw new ApiError(message, response.status, typeof detail === 'object' ? detail : null)
  }
  return body
}

export const getHealth = () => request('/api/health')

export const getZones = (lat, lon) =>
  request(`/api/zones?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`)

export const getLayer = (name) => request(`/api/layers/${name}`)

export const getChunk = (chunkId) => request(`/api/chunks/${chunkId}`)

const postJson = (path, payload) =>
  request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

export const postSearch = (payload) => postJson('/api/search', payload)
export const postAsk = (payload) => postJson('/api/ask', payload)
export const postAgent = (payload) => postJson('/api/agent', payload)

// The question verification screen. Every one of these is a 404 unless the backend was
// started with ZONEWISE_DEV=1, which is why the interface asks /api/health first and
// only shows the Verify tab when dev_mode is true (see app/api.py and D-075).
export const getDevQuestions = () => request('/api/dev/eval/questions')

export const getDevQuestion = (id) =>
  request(`/api/dev/eval/questions/${encodeURIComponent(id)}`)

export const postDevLeakage = (id, question) =>
  postJson(`/api/dev/eval/questions/${encodeURIComponent(id)}/leakage`, { question })

export const postDevDecision = (id, decision) =>
  postJson(`/api/dev/eval/questions/${encodeURIComponent(id)}/decision`, decision)
