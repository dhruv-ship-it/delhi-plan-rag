// What get_zones returned, as chips. The four policy zones are the ones that change
// which rules apply, so they are highlighted; the planning zone and the two extra
// layers are shown plainly.

const POLICY_CHIPS = [
  { key: 'tod', label: 'Inside TOD zone' },
  { key: 'hdc', label: 'Inside high density corridor' },
  { key: 'land_pooling', label: 'Inside land pooling area' },
  { key: 'zone_o', label: 'Inside Zone O (Yamuna floodplain)' },
]

const EXTRA_CHIPS = [
  { key: 'regional_park', label: 'Regional park' },
  { key: 'lda', label: 'Low density area' },
]

export default function ZoneChips({ zones, loading, error }) {
  if (loading) return <p className="muted">Looking up this point...</p>
  if (error) return <p className="error">{error}</p>
  if (!zones) return null

  if (!zones.inside_delhi) {
    return (
      <div className="chips">
        <span className="chip chip-out">Outside Delhi</span>
        <p className="muted">
          The Master Plan for Delhi 2047 does not apply here, so there is nothing to look up.
        </p>
      </div>
    )
  }

  const policies = POLICY_CHIPS.filter((chip) => zones[chip.key])
  const extras = EXTRA_CHIPS.filter((chip) => zones[chip.key])

  return (
    <div className="chips">
      <span className="chip chip-zone">
        {zones.planning_zone ? `Planning zone ${zones.planning_zone}` : 'Planning zone unknown'}
      </span>
      {policies.map((chip) => (
        <span key={chip.key} className="chip chip-policy">
          {chip.label}
          {chip.key === 'land_pooling' && zones.land_pooling_zone
            ? ` ${zones.land_pooling_zone}`
            : ''}
        </span>
      ))}
      {extras.map((chip) => (
        <span key={chip.key} className="chip">
          {chip.label}
        </span>
      ))}
      {policies.length === 0 && (
        <span className="chip chip-plain">In none of the four policy zones</span>
      )}
      {!zones.planning_zone && (
        <p className="muted">
          DDA&rsquo;s zone layer has 16 of the 17 planning zones; zone A (the Walled City)
          is missing from it, so a point there shows no zone letter.
        </p>
      )}
    </div>
  )
}
