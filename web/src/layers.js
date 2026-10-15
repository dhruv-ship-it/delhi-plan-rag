// The five map layers the interface draws, in the order they are stacked and listed.
// Names must match SERVABLE_LAYERS in app/api.py.
//
// The NCT boundary is an outline only (no fill), because it covers the whole map and a
// fill would tint everything. Planning zones sit underneath the policy layers, since a
// point is always in exactly one planning zone but may be in several policy zones.

export const LAYERS = [
  {
    name: 'nctd_boundary',
    label: 'Delhi boundary',
    colour: '#334155',
    fill: false,
    weight: 2,
    defaultOn: true,
  },
  {
    name: 'planning_zones',
    label: 'Planning zones',
    colour: '#94a3b8',
    fill: true,
    weight: 1,
    defaultOn: true,
    labelled: true,
  },
  {
    name: 'tod_zone',
    label: 'TOD zone',
    colour: '#2563eb',
    fill: true,
    weight: 1,
    defaultOn: true,
  },
  {
    name: 'high_density_corridor',
    label: 'High density corridor',
    colour: '#ea580c',
    fill: true,
    weight: 1,
    defaultOn: true,
  },
  {
    name: 'land_pooling_area',
    label: 'Land pooling area',
    colour: '#16a34a',
    fill: true,
    weight: 1,
    defaultOn: true,
  },
]

// Centred on Delhi, zoomed to fit the whole territory on a laptop screen.
export const DELHI_CENTRE = [28.64, 77.1]
export const DELHI_ZOOM = 10

// Shown as an example in the agent box and used by the "try this" link.
export const EXAMPLE_POINT = { lat: 28.6328, lon: 77.2197, label: 'Rajiv Chowk' }
