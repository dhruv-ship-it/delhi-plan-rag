// What the agent actually did, collapsed by default. Worth showing because the steps
// are the interesting part: it found the place, looked up the zones, then searched with
// those coordinates, and each of those is a decision the model made rather than a fixed
// pipeline.

const TOOL_LABELS = {
  locate_place: 'Found the place',
  get_zones: 'Looked up the zones',
  search_clauses: 'Searched the documents',
}

export default function ToolTrace({ trace }) {
  if (!trace?.length) return null

  return (
    <details className="trace">
      <summary>How the agent worked this out ({trace.length} steps)</summary>
      <ol>
        {trace.map((step, index) => (
          <li key={index}>
            <strong>{TOOL_LABELS[step.tool] || step.tool}</strong>
            <code className="trace-input">{JSON.stringify(step.input)}</code>
            <span className="trace-summary">{step.summary}</span>
          </li>
        ))}
      </ol>
    </details>
  )
}
