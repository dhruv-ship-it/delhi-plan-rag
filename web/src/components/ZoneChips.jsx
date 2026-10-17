// What get_zones returned, as chips. All six policy zones change which rules apply, so
// all six are highlighted; the planning zone is shown plainly beside them.
//
// Two of the six carry a note, because they behave differently in search: Zone O and
// the Ridge have no policy section of their own in MPD-2047, so they can raise a
// clause up the results and widen the query, but they can never remove a clause the
// way a TOD or LDA point does (D-037, D-069).

const POLICY_CHIPS = [
  { key: 'tod', label: 'Inside TOD zone' },
  { key: 'hdc', label: 'Inside high density corridor' },
  { key: 'land_pooling', label: 'Inside land pooling area' },
  { key: 'zone_o', label: 'Inside Zone O (Yamuna floodplain)', boostOnly: true },
  { key: 'regional_park', label: 'Inside regional park / the Ridge', boostOnly: true },
  { key: 'lda', label: 'Inside low density area' },
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
  const boostOnly = policies.filter((chip) => chip.boostOnly)

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
      {policies.length === 0 && (
        <span className="chip chip-plain">In none of the six policy zones</span>
      )}
      {boostOnly.length > 0 && (
        <p className="muted">
          MPD&ndash;2047 has no policy section of its own for{' '}
          {boostOnly.map((chip) => (chip.key === 'zone_o' ? 'Zone O' : 'the Ridge')).join(' or ')},
          so clauses that mention it are ranked higher here, but no clause is ruled out.
        </p>
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
