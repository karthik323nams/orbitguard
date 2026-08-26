import type { ConjunctionEvent, ObjectCatalogEntry } from '../../types/orbitguard';

type GroundTrackProps = {
  selectedEvent?: ConjunctionEvent | null;
  object?: ObjectCatalogEntry | null;
  trajectory?: Array<{ x_km: number; y_km: number; z_km: number; timestamp?: string }>;
};

export function GroundTrack({ selectedEvent, object, trajectory = [] }: GroundTrackProps) {
  const basePath = 'M 25 170 C 80 115, 140 110, 210 124 S 325 170, 398 70';
  const altPath = 'M 25 145 C 95 80, 180 82, 248 92 S 340 112, 398 40';
  const markerX = selectedEvent ? 206 : 144;
  const markerY = selectedEvent ? 84 : 126;
  const hasTrajectory = trajectory && trajectory.length > 1;

  // Fix scaling: trajectories in frontend state are scaled by 1/1600
  const firstPoint = trajectory[0];
  const rawX = firstPoint ? (Math.abs(firstPoint.x_km ?? 0) < 50 ? (firstPoint.x_km ?? 0) * 1600 : (firstPoint.x_km ?? 0)) : 0;
  const rawY = firstPoint ? (Math.abs(firstPoint.y_km ?? 0) < 50 ? (firstPoint.y_km ?? 0) * 1600 : (firstPoint.y_km ?? 0)) : 0;
  const rawZ = firstPoint ? (Math.abs(firstPoint.z_km ?? 0) < 50 ? (firstPoint.z_km ?? 0) * 1600 : (firstPoint.z_km ?? 0)) : 0;

  // Approximate geodetic parameters from position vector for display
  const radius = Math.sqrt(rawX * rawX + rawY * rawY + rawZ * rawZ);
  const lat = radius > 0 ? (Math.asin(rawZ / radius) * 180) / Math.PI : 0;
  const lon = radius > 0 ? (Math.atan2(rawY, rawX) * 180) / Math.PI : 0;

  const latLonStr = hasTrajectory
    ? `${lat >= 0 ? '+' : ''}${lat.toFixed(1)}° / ${lon >= 0 ? '+' : ''}${lon.toFixed(1)}°`
    : selectedEvent
    ? '18.6° / 112.3°'
    : 'No track yet';

  const altitudeStr = hasTrajectory
    ? `${Math.max(100, Math.round(radius - 6378.137))} km`
    : selectedEvent
    ? '410 km'
    : '—';

  return (
    <div className="ground-track-card">
      <div className="ground-track-header">
        <div>
          <div className="eyebrow">GROUND TRACK</div>
          <h3>Earth-fixed / PEF approximation</h3>
        </div>
        <span className="status-tag">{object ? object.name : selectedEvent ? `${selectedEvent.name_a} / ${selectedEvent.name_b}` : 'TRACER'}</span>
      </div>
      <svg viewBox="0 0 420 200" className="ground-track-svg" role="img" aria-label="Ground track">
        <defs>
          <linearGradient id="trackGlow" x1="0%" x2="100%" y1="0%" y2="0%">
            <stop offset="0%" stopColor="#60d5ff" />
            <stop offset="100%" stopColor="#ff876c" />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width="420" height="200" rx="14" fill="#091925" />
        <path d="M 10 100 H 410 M 210 20 V 180" stroke="#1a2d3d" strokeDasharray="4 8" />
        <path d={basePath} stroke="#496c85" strokeWidth="1.2" fill="none" opacity="0.8" />
        {hasTrajectory ? (() => {
          const points = trajectory.slice(0, 32).map((point, index) => {
            const yVal = Math.abs(point.y_km) < 50 ? point.y_km * 1600 : point.y_km;
            const x = 35 + (index / Math.max(1, trajectory.slice(0, 32).length - 1)) * 350;
            const y = 170 - ((yVal + 2200) / 4400) * 120;
            return `${index === 0 ? 'M' : 'L'} ${x} ${y}`;
          }).join(' ');
          return <path d={points} stroke="url(#trackGlow)" strokeWidth="2.2" fill="none" opacity="0.95" />;
        })() : <path d={altPath} stroke="url(#trackGlow)" strokeWidth="2.5" fill="none" />}
        <circle cx={markerX} cy={markerY} r="6" fill="#ff7b6d" />
        <circle cx={markerX} cy={markerY} r="13" fill="none" stroke="#ff7b6d" strokeOpacity="0.4" />
        <circle cx="160" cy="126" r="5" fill="#7bd0ff" />
        <text x="26" y="30" fill="#7d8ea1" fontSize="10">Longitude</text>
        <text x="326" y="186" fill="#7d8ea1" fontSize="10">Latitude</text>
      </svg>
      <div className="ground-track-data">
        <div><span>Current</span><strong>{object ? object.name : selectedEvent ? 'TCA marker' : 'Waiting for live track'}</strong></div>
        <div><span>Lat / lon</span><strong>{latLonStr}</strong></div>
        <div><span>Altitude</span><strong>{altitudeStr}</strong></div>
      </div>
    </div>
  );
}
