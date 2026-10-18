import L from 'leaflet'

// Leaflet's default marker icon is loaded from a path relative to the stylesheet, which
// a bundler rewrites and then cannot find. Pointing it at the CDN copies keeps the
// marker visible in the dev server and in the built bundle alike.
//
// It lives in its own module because two maps now use it: the main map in MapView and
// the small one on the verification screen.
export const markerIcon = new L.Icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})
