import { XCircle, Satellite, Globe2, Clock, Radio } from 'lucide-react';
import type { SatelliteProfile } from '../../types/orbitguard';

type Props = {
  profile: SatelliteProfile;
  onClose: () => void;
};

function InfoRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value === null || value === undefined || value === '') return null;
  return (
    <div className="sat-info-row">
      <span className="sat-info-label">{label}</span>
      <strong className="sat-info-value">{String(value)}</strong>
    </div>
  );
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="sat-section">
      <div className="sat-section-header">
        {icon}
        <span>{title}</span>
      </div>
      <div className="sat-section-body">{children}</div>
    </div>
  );
}

function OrbitRegimeBadge({ regime }: { regime: string | null }) {
  if (!regime) return null;
  const colorMap: Record<string, string> = {
    LEO: '#2dd4f0', MEO: '#a78bfa', GEO: '#fbbf24', 'GEO+': '#fb923c', HEO: '#f87171', SSO: '#6ee7a4',
  };
  const color = colorMap[regime] ?? '#94a3b8';
  return (
    <span className="orbit-regime-badge" style={{ borderColor: color, color }}>
      {regime}
    </span>
  );
}

export function SatelliteInfoPanel({ profile, onClose }: Props) {
  const { identity, orbital_state, current_position, launch_metadata, tracking_status } = profile;

  const formatNum = (v: number | null | undefined, decimals = 4) =>
    v !== null && v !== undefined ? v.toFixed(decimals) : null;

  const formatAlt = (v: number | null | undefined) =>
    v !== null && v !== undefined ? `${v.toFixed(1)} km` : null;

  const formatLat = (v: number | null | undefined) =>
    v !== null && v !== undefined ? `${v >= 0 ? '+' : ''}${v.toFixed(4)}°` : null;

  const formatLon = (v: number | null | undefined) =>
    v !== null && v !== undefined ? `${v >= 0 ? '+' : ''}${v.toFixed(4)}°` : null;

  const formatEpoch = (v: string | null | undefined) => {
    if (!v) return null;
    try { return new Date(v).toUTCString().replace(' GMT', ' UTC'); } catch { return v; }
  };

  const dataAgeStr = tracking_status.data_age_minutes !== null && tracking_status.data_age_minutes !== undefined
    ? tracking_status.data_age_minutes < 60
      ? `${Math.round(tracking_status.data_age_minutes)} min ago`
      : `${(tracking_status.data_age_minutes / 60).toFixed(1)} h ago`
    : null;

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="detail-drawer sat-detail-drawer" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="drawer-header">
          <div className="drawer-title-wrap">
            <Satellite size={18} className="drawer-icon-sat" />
            <div>
              <h3 className="drawer-sat-name">{identity.name}</h3>
              <div className="drawer-sat-sub">
                {identity.norad_id && <span>NORAD {identity.norad_id}</span>}
                {identity.cospar_id && <span> · {identity.cospar_id}</span>}
              </div>
            </div>
          </div>
          <button className="icon-button" onClick={onClose}><XCircle size={18} /></button>
        </div>

        <div className="sat-info-scroll">
          {/* IDENTITY */}
          <Section icon={<Satellite size={14} />} title="IDENTITY">
            <InfoRow label="Satellite name" value={identity.name} />
            <InfoRow label="NORAD Catalog ID" value={identity.norad_id} />
            <InfoRow label="COSPAR / Intl Designator" value={identity.cospar_id} />
            <InfoRow label="Object type" value={identity.object_type ?? 'Not specified'} />
          </Section>

          {/* LAUNCH INFORMATION */}
          <Section icon={<Globe2 size={14} />} title="LAUNCH INFORMATION">
            <InfoRow label="Launching Country" value={launch_metadata.country} />
            <InfoRow label="Launch Date" value={launch_metadata.launch_date} />
            <InfoRow label="Launch Site" value={launch_metadata.launch_site} />
            <InfoRow label="Launch Vehicle" value={launch_metadata.launch_vehicle ?? 'Not specified'} />
            <InfoRow label="Launch Year" value={launch_metadata.launch_year} />
            <InfoRow label="Launch sequence no." value={launch_metadata.launch_number} />
            <InfoRow label="Piece" value={launch_metadata.piece} />
            <div className="sat-info-note">{launch_metadata.data_note}</div>
          </Section>

          {/* ORBITAL INFORMATION */}
          <Section icon={<Globe2 size={14} />} title="ORBITAL INFORMATION">
            <div className="orbit-regime-row">
              <span className="sat-info-label">Regime</span>
              <OrbitRegimeBadge regime={orbital_state.orbit_regime} />
            </div>
            <InfoRow label="Period" value={formatAlt(orbital_state.period_minutes)?.replace(' km', ' min') ?? null} />
            <InfoRow label="Apogee" value={formatAlt(orbital_state.apogee_km)} />
            <InfoRow label="Perigee" value={formatAlt(orbital_state.perigee_km)} />
            <InfoRow label="Inclination" value={orbital_state.inclination_deg !== null ? `${formatNum(orbital_state.inclination_deg, 4)}°` : null} />
            <InfoRow label="Eccentricity" value={formatNum(orbital_state.eccentricity, 7)} />
            <InfoRow label="Mean motion" value={orbital_state.mean_motion_rev_day !== null ? `${formatNum(orbital_state.mean_motion_rev_day, 5)} rev/day` : null} />
            <InfoRow label="Epoch" value={formatEpoch(orbital_state.epoch)} />
          </Section>

          {/* CURRENT STATE */}
          {current_position && (
            <Section icon={<Radio size={14} />} title="CURRENT STATE">
              <InfoRow label="Latitude" value={formatLat(current_position.lat_deg)} />
              <InfoRow label="Longitude" value={formatLon(current_position.lon_deg)} />
              <InfoRow label="Altitude" value={formatAlt(current_position.alt_km)} />
              <InfoRow label="Velocity" value={`${current_position.velocity_km_s.toFixed(3)} km/s`} />
              <InfoRow label="Computed at" value={formatEpoch(current_position.timestamp)} />
            </Section>
          )}

          {/* TRACKING STATUS */}
          <Section icon={<Clock size={14} />} title="TRACKING STATUS">
            <div className="sat-info-row">
              <span className="sat-info-label">Data mode</span>
              <span className={`status-pill ${tracking_status.data_mode === 'LIVE' ? 'live' : 'offline'}`} style={{ fontSize: '0.7rem', padding: '2px 8px' }}>
                <span className="status-dot" />
                {tracking_status.data_mode}
              </span>
            </div>
            <InfoRow label="Source" value={tracking_status.source} />
            <InfoRow label="Last updated" value={dataAgeStr} />
            <InfoRow label="Data age" value={tracking_status.data_age_minutes !== null ? `${Math.round(tracking_status.data_age_minutes)} min` : null} />
          </Section>
        </div>
      </aside>
    </div>
  );
}
