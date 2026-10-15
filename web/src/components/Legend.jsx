import { LAYERS } from '../layers.js'

// The legend doubles as the layer switch: each row is a checkbox and a colour swatch,
// so there is one control rather than a legend beside a separate list of toggles.
export default function Legend({ visible, onToggle }) {
  return (
    <fieldset className="legend">
      <legend className="legend-title">Map layers</legend>
      {LAYERS.map((layer) => (
        <label key={layer.name} className="legend-row">
          <input
            type="checkbox"
            checked={!!visible[layer.name]}
            onChange={() => onToggle(layer.name)}
          />
          <span
            className="swatch"
            style={{
              borderColor: layer.colour,
              background: layer.fill ? `${layer.colour}30` : 'transparent',
            }}
            aria-hidden="true"
          />
          <span>{layer.label}</span>
        </label>
      ))}
    </fieldset>
  )
}
