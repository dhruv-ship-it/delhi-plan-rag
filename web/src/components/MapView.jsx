import { useEffect, useState } from 'react'
import { GeoJSON, MapContainer, Marker, TileLayer, Tooltip, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import { getLayer } from '../api.js'
import { DELHI_CENTRE, DELHI_ZOOM, LAYERS } from '../layers.js'

// Leaflet's default marker icon is loaded from a relative path that breaks under a
// bundler. Pointing it at the CDN copies keeps the marker visible in dev and in build.
const markerIcon = new L.Icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})

function ClickHandler({ onPick }) {
  useMapEvents({
    click(event) {
      onPick(event.latlng.lat, event.latlng.lng)
    },
  })
  return null
}

export default function MapView({ marker, onPick, visible, onLayerError }) {
  const [layers, setLayers] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      const loaded = {}
      const failed = []
      for (const layer of LAYERS) {
        try {
          loaded[layer.name] = await getLayer(layer.name)
        } catch (error) {
          failed.push(`${layer.label}: ${error.message}`)
        }
      }
      if (cancelled) return
      setLayers(loaded)
      setLoading(false)
      if (failed.length) onLayerError(failed.join('; '))
    }
    load()
    return () => {
      cancelled = true
    }
  }, [onLayerError])

  return (
    <div className="map-wrap">
      {loading && (
        <div className="map-loading" role="status">
          Loading map layers...
        </div>
      )}
      <MapContainer center={DELHI_CENTRE} zoom={DELHI_ZOOM} className="map" scrollWheelZoom>
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          maxZoom={18}
        />
        <ClickHandler onPick={onPick} />

        {LAYERS.filter((layer) => visible[layer.name] && layers[layer.name]).map((layer) => (
          <GeoJSON
            key={layer.name}
            data={layers[layer.name]}
            style={{
              color: layer.colour,
              weight: layer.weight,
              fillOpacity: layer.fill ? 0.18 : 0,
              fillColor: layer.colour,
            }}
            onEachFeature={(feature, leafletLayer) => {
              const zone = feature.properties?.zone_name
              if (layer.labelled && zone) {
                leafletLayer.bindTooltip(`Zone ${zone}`, {
                  permanent: false,
                  direction: 'center',
                  className: 'zone-tooltip',
                })
              }
            }}
          />
        ))}

        {marker && (
          <Marker position={[marker.lat, marker.lon]} icon={markerIcon}>
            <Tooltip direction="top" offset={[0, -36]}>
              {marker.lat.toFixed(5)}, {marker.lon.toFixed(5)}
            </Tooltip>
          </Marker>
        )}
      </MapContainer>
    </div>
  )
}
