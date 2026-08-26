import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Bell,
  Database,
  Globe2,
  LayoutDashboard,
  Radar,
  RefreshCw,
  Search,
  Satellite,
  SlidersHorizontal,
  XCircle,
} from 'lucide-react';

import { OrbitScene } from './components/visualization/OrbitScene';
import { GroundTrack } from './components/visualization/GroundTrack';
import { SatelliteInfoPanel } from './components/objects/SatelliteInfoPanel';
import { api } from './lib/api';
import type {
  AnalyticsSummary,
  ConjunctionEvent,
  FullOrbitResponse,
  ObjectCatalogEntry,
  RiskBand,
  SatelliteProfile,
} from './types/orbitguard';


const emptyAnalytics: AnalyticsSummary = {
  scan_runs: 0,
  stored_observations: 0,
  mean_risk_score: 0,
  minimum_miss_distance_km: null,
  risk_distribution: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 },
  trend_distribution: { NEW: 0, WORSENING: 0, STABLE: 0, IMPROVING: 0 },
  top_pairs: [],
};

const NAV_ITEMS = ['overview', 'conjunctions', 'objects', 'alerts', 'analytics', 'visualization'] as const;
type View = (typeof NAV_ITEMS)[number];
type DataMode = 'LIVE' | 'CACHED' | 'OFFLINE';
type SortMode = 'risk' | 'miss' | 'tca' | 'velocity';
type RiskFilter = 'ALL' | RiskBand;

type ScenePoint = { x_km: number; y_km: number; z_km: number; timestamp?: string };
type SceneTrajectory = Record<string, ScenePoint[]>;

const normalizeTrajectoryPoints = (trajectory: { points?: Array<{ timestamp?: string; position_km?: [number, number, number] | number[]; velocity_km_s?: [number, number, number] | number[] }> } | null | undefined): ScenePoint[] => {
  if (!trajectory || !Array.isArray(trajectory.points)) {
    return [];
  }

  const points: ScenePoint[] = [];

  for (const point of trajectory.points) {
    const position = Array.isArray(point.position_km) ? point.position_km : [0, 0, 0];
    if (!Array.isArray(position) || position.length < 3) {
      continue;
    }

    const [x, y, z] = position as [number, number, number];
    points.push({
      x_km: Number(x) / 1600,
      y_km: Number(y) / 1600,
      z_km: Number(z) / 1600,
      timestamp: point.timestamp,
    });
  }

  return points;
};

const riskClass = (band: string) => String(band).toLowerCase();

const normalizeRiskBand = (value?: string): RiskBand => {
  const normalized = String(value || 'LOW').toUpperCase();
  if (normalized === 'CRITICAL' || normalized === 'HIGH' || normalized === 'MEDIUM' || normalized === 'LOW') {
    return normalized as RiskBand;
  }
  return 'LOW';
};

const normalizeObject = (row: Record<string, any>): ObjectCatalogEntry => {
  const catalogNumber = String(row.catalog_number ?? row.norad_id ?? row.object_id ?? '');
  return {
    catalog_number: catalogNumber,
    name: row.name ?? row.object_name ?? `OBJECT ${catalogNumber}`,
    object_id: row.object_id ? String(row.object_id) : row.norad_id ? String(row.norad_id) : undefined,
    object_type: row.object_type ?? row.objectType,
    source_group: row.source_group ?? row.group ?? 'tracked',
    epoch: row.epoch ?? row.fetched_at ?? row.last_successful_fetch,
    data_age_minutes: typeof row.data_age_minutes === 'number' ? row.data_age_minutes : undefined,
    status: row.status ?? (row.cache_fresh ? 'ACTIVE' : 'TRACKED'),
  };
};

const normalizeEvent = (event: Record<string, any>): ConjunctionEvent => {
  const catalogA = String(event.catalog_a ?? event.object_a?.norad_id ?? event.catalog_a ?? event.catalogA ?? '');
  const catalogB = String(event.catalog_b ?? event.object_b?.norad_id ?? event.catalog_b ?? event.catalogB ?? '');
  const nameA = event.name_a ?? event.object_a?.name ?? `OBJECT ${catalogA}`;
  const nameB = event.name_b ?? event.object_b?.name ?? `OBJECT ${catalogB}`;
  const riskBand = normalizeRiskBand(event.risk_band ?? event.risk_level ?? event.priority_band);

  return {
    id: event.id ?? `${catalogA}-${catalogB}`,
    catalog_a: catalogA,
    name_a: nameA,
    catalog_b: catalogB,
    name_b: nameB,
    tca: event.tca ?? event.closest_approach ?? new Date().toISOString(),
    miss_distance_km: Number(event.miss_distance_km ?? event.miss_distance ?? 0),
    relative_velocity_km_s: Number(event.relative_velocity_km_s ?? event.relative_speed_km_s ?? 0),
    risk_score: Number(event.risk_score ?? event.priority_score ?? event.score ?? 0),
    risk_band: riskBand,
    risk_level: event.risk_level ?? riskBand,
    priority_score: Number(event.priority_score ?? event.risk_score ?? event.score ?? 0),
    time_to_tca_minutes: Number(event.time_to_tca_minutes ?? event.time_to_tca ?? 0),
    trend: (event.trend ?? 'NEW').toUpperCase() as ConjunctionEvent['trend'],
    data_age_minutes: Number(event.data_age_minutes ?? 0),
    risk_breakdown: {
      miss_distance_score: Number(event.risk_breakdown?.miss_distance_score ?? event.miss_distance_score ?? 0),
      imminence_score: Number(event.risk_breakdown?.imminence_score ?? event.imminence_score ?? 0),
      relative_speed_score: Number(event.risk_breakdown?.relative_speed_score ?? event.relative_speed_score ?? 0),
      freshness_score: Number(event.risk_breakdown?.freshness_score ?? event.freshness_score ?? 0),
      reasons: Array.isArray(event.risk_breakdown?.reasons) ? event.risk_breakdown.reasons : ['Live backend prioritization score.'],
      uncertainty_status: event.risk_breakdown?.uncertainty_status ?? 'Prototype prioritization score; not operational collision probability.',
    },
    object_a: event.object_a,
    object_b: event.object_b,
  };
};

const formatTCA = (value: string) => {
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return `${dt.toLocaleString('en-US', { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })} UTC`;
};

const formatCountdown = (minutes: number) => {
  if (minutes < 60) return `${Math.round(minutes)} min`;
  const hours = minutes / 60;
  return `${hours.toFixed(hours >= 10 ? 0 : 1)} h`;
};

const countByBand = (events: ConjunctionEvent[], band: RiskBand) => events.filter((event) => event.risk_band === band).length;

function StatusPill({ mode }: { mode: DataMode }) {
  const isLive = mode === 'LIVE' || mode === 'CACHED';
  return (
    <div className={`status-pill ${isLive ? 'live' : 'offline'}`}>
      <span className="status-dot" />
      {isLive ? (mode === 'CACHED' ? 'CACHE MODE' : 'LIVE API') : 'OFFLINE'}
    </div>
  );
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-detail">{detail}</div>
    </div>
  );
}

function App() {
  const [view, setView] = useState<View>('overview');
  const [mode, setMode] = useState<DataMode>('OFFLINE');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [objects, setObjects] = useState<ObjectCatalogEntry[]>([]);
  const [events, setEvents] = useState<ConjunctionEvent[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsSummary>(emptyAnalytics);
  const [trajectories, setTrajectories] = useState<SceneTrajectory>({});
  const [query, setQuery] = useState('');
  const [riskFilter, setRiskFilter] = useState<RiskFilter>('ALL');
  const [sortMode, setSortMode] = useState<SortMode>('risk');
  const [upcomingOnly, setUpcomingOnly] = useState(true);
  const [selectedEvent, setSelectedEvent] = useState<ConjunctionEvent | null>(null);
  const [selectedObject, setSelectedObject] = useState<ObjectCatalogEntry | null>(null);
  const [acknowledged, setAcknowledged] = useState<Record<string, boolean>>({});
  // NEW: full-orbit and satellite profile state
  const [selectedOrbit, setSelectedOrbit] = useState<FullOrbitResponse | null>(null);
  const [selectedObjectProfile, setSelectedObjectProfile] = useState<SatelliteProfile | null>(null);
  const [showSatellitePanel, setShowSatellitePanel] = useState(false);
  const [conjunctionData, setConjunctionData] = useState<any | null>(null);


  const loadFullOrbitForObject = useCallback(async (catalogNumber: string | number | undefined) => {
    const key = catalogNumber === undefined || catalogNumber === null || catalogNumber === '' ? null : String(catalogNumber);
    if (!key) {
      setSelectedOrbit(null);
      setSelectedObjectProfile(null);
      return;
    }

    // Clear the previous orbit immediately when switching satellites
    setSelectedOrbit(null);
    setSelectedObjectProfile(null);

    try {
      // Fetch full orbit and satellite profile in parallel
      const [orbitResult, profileResult] = await Promise.allSettled([
        api.getFullOrbit(key),
        api.getSatelliteProfile(key),
      ]);

      if (orbitResult.status === 'fulfilled') {
        const orbit = orbitResult.value;
        setSelectedOrbit(orbit);
        // Also populate the trajectory map for GroundTrack compatibility
        if (orbit.points && orbit.points.length > 1) {
          const scenePoints = orbit.points.map((pt) => ({
            x_km: pt.x_km / 1600,
            y_km: pt.y_km / 1600,
            z_km: pt.z_km / 1600,
            timestamp: pt.timestamp,
          }));
          setTrajectories((prev) => ({ ...prev, [key]: scenePoints }));
        }
      }

      if (profileResult.status === 'fulfilled') {
        setSelectedObjectProfile(profileResult.value);
      }
    } catch {
      // Silently handle errors — the old trajectory fallback still works
      setSelectedOrbit(null);
      setSelectedObjectProfile(null);
    }
  }, []);

  // Keep the legacy short-trajectory loader for the overview multi-object preview
  const loadTrajectoryForObject = async (catalogNumber: string | number | undefined) => {
    const key = catalogNumber === undefined || catalogNumber === null || catalogNumber === '' ? null : String(catalogNumber);
    if (!key) return null;

    try {
      const trajectory = await api.getTrajectory(key, 5, 60);
      const points = normalizeTrajectoryPoints(trajectory);
      setTrajectories((previous) => {
        const next = { ...previous };
        if (points.length > 1) { next[key] = points; } else { delete next[key]; }
        return next;
      });
      return points;
    } catch {
      setTrajectories((previous) => {
        const next = { ...previous };
        delete next[key];
        return next;
      });

      return null;
    }
  };

  const loadData = async () => {
    setLoading(true);
    setError(null);

    try {
      const health = await api.getHealth().catch(() => null);
      const status = await api.getDataStatus().catch(() => null);
      const cloudDataAvailable = Boolean(health) || Boolean(status);
      const liveMode = Boolean(health && (health.data_mode === 'live' || health.data_mode === 'cached')) || Boolean(status && (status.mode === 'LIVE' || status.mode === 'CACHED'));

      if (!cloudDataAvailable || !liveMode) {
        setMode('OFFLINE');
        setObjects([]);
        setEvents([]);
        setAnalytics(emptyAnalytics);
        setTrajectories({});
        setSelectedEvent(null);
        setSelectedObject(null);
        return;
      }

      const [objectResponse, scanResult, analyticsSummary] = await Promise.all([
        api.getObjects().catch(() => ({ group: 'tracked', count: 0, objects: [] })),
        api.scanConjunctions({ group: 'tracked', duration_minutes: 90, step_seconds: 60, screening_distance_km: 20, max_objects: 250, max_events: 25 }).catch(() => ({ events: [] as ConjunctionEvent[] })),
        api.getAnalytics().catch(() => emptyAnalytics),
      ]);

      const catalog = (objectResponse.objects ?? []).map(normalizeObject);
      const rawEvents = (scanResult as any).events ?? (scanResult as any).conjunctions ?? [];
      const eventList = rawEvents.map(normalizeEvent);

      const nextTrajectories: SceneTrajectory = {};
      const previewObjects = catalog.slice(0, Math.min(catalog.length, 12));
      const trajectoryResults = await Promise.all(
        previewObjects.map(async (objectRow) => {
          try {
            const trajectory = await api.getTrajectory(objectRow.catalog_number, 5, 60);
            const points = normalizeTrajectoryPoints(trajectory);
            if (points.length > 1) {
              nextTrajectories[objectRow.catalog_number] = points;
            }
          } catch {
            // Ignore preview trajectory failures and keep the selected object path live.
          }
        }),
      );

      setObjects(catalog);
      setEvents(eventList);
      setAnalytics(analyticsSummary ?? emptyAnalytics);
      setTrajectories(nextTrajectories);
      setMode(status?.mode === 'CACHED' ? 'CACHED' : 'LIVE');
      setSelectedEvent((previous) => previous ?? eventList[0] ?? null);
      setSelectedObject((previous) => previous ?? catalog[0] ?? null);
    } catch (err) {
      setMode('OFFLINE');
      setObjects([]);
      setEvents([]);
      setAnalytics(emptyAnalytics);
      setTrajectories({});
      setSelectedEvent(null);
      setSelectedObject(null);
      setSelectedOrbit(null);
      setSelectedObjectProfile(null);
      setShowSatellitePanel(false);
      setError(err instanceof Error ? err.message : 'Unable to load Astrail data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  // When selectedObject changes, load its full orbit + profile
  useEffect(() => {
    if (!selectedObject) {
      return;
    }
    const key = String(selectedObject.catalog_number ?? selectedObject.object_id ?? '');
    if (!key) return;
    void loadFullOrbitForObject(key);
  }, [selectedObject, loadFullOrbitForObject]);

  // When selectedEvent changes, load real conjunction visualization data
  useEffect(() => {
    if (!selectedEvent) {
      setConjunctionData(null);
      return;
    }
    const loadConjunctionData = async () => {
      try {
        const data = await api.getVisualization(selectedEvent.catalog_a, selectedEvent.catalog_b);
        setConjunctionData(data);
      } catch {
        setConjunctionData(null);
      }
    };
    void loadConjunctionData();
  }, [selectedEvent]);


  const filteredEvents = useMemo(() => {
    const text = query.trim().toLowerCase();
    let results = [...events];

    if (text) {
      results = results.filter((event) => `${event.name_a} ${event.name_b} ${event.catalog_a} ${event.catalog_b}`.toLowerCase().includes(text));
    }
    if (riskFilter !== 'ALL') {
      results = results.filter((event) => event.risk_band === riskFilter);
    }
    if (upcomingOnly) {
      results = results.filter((event) => event.time_to_tca_minutes >= 0);
    }

    results.sort((a, b) => {
      switch (sortMode) {
        case 'miss':
          return a.miss_distance_km - b.miss_distance_km;
        case 'tca':
          return new Date(a.tca).getTime() - new Date(b.tca).getTime();
        case 'velocity':
          return b.relative_velocity_km_s - a.relative_velocity_km_s;
        default:
          return b.risk_score - a.risk_score;
      }
    });

    return results;
  }, [events, query, riskFilter, sortMode, upcomingOnly]);

  const visibleObjects = useMemo(() => {
    const text = query.trim().toLowerCase();
    return objects.filter((record) => `${record.name} ${record.catalog_number}`.toLowerCase().includes(text));
  }, [objects, query]);

  const priorityEvents = useMemo(() => [...events].sort((a, b) => b.risk_score - a.risk_score).slice(0, 5), [events]);
  const criticalCount = countByBand(events, 'CRITICAL');
  const highCount = countByBand(events, 'HIGH');
  const mediumCount = countByBand(events, 'MEDIUM');
  const lowCount = countByBand(events, 'LOW');
  const alertEvents = priorityEvents.filter((event) => !acknowledged[`${event.catalog_a}-${event.catalog_b}`]);

  const selectEvent = (event: ConjunctionEvent) => {
    setSelectedEvent(event);
    setView('conjunctions');
  };

  const selectObject = (object: ObjectCatalogEntry) => {
    setSelectedEvent(null);
    // Clear orbit immediately before loading the new one
    setSelectedOrbit(null);
    setSelectedObjectProfile(null);
    setSelectedObject(object);
    setView('visualization');
    setShowSatellitePanel(true);
    void loadFullOrbitForObject(object.catalog_number);
  };


  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-icon"><Radar size={20} /></div>
          <div>
            <div className="brand-name">ASTRAIL</div>
            <div className="brand-subtitle">SPACE SAFETY / PS-04</div>
          </div>
        </div>

        <nav className="nav-list">
          {NAV_ITEMS.map((item) => (
            <button key={item} className={`nav-item ${view === item ? 'active' : ''}`} onClick={() => setView(item)}>
              {item === 'overview' && <LayoutDashboard size={16} />}
              {item === 'conjunctions' && <AlertTriangle size={16} />}
              {item === 'objects' && <Satellite size={16} />}
              {item === 'alerts' && <Bell size={16} />}
              {item === 'analytics' && <SlidersHorizontal size={16} />}
              {item === 'visualization' && <Globe2 size={16} />}
              <span>{item === 'overview' ? 'Overview' : item === 'conjunctions' ? 'Conjunctions' : item === 'objects' ? 'Objects' : item === 'alerts' ? 'Alerts' : item === 'analytics' ? 'Analytics' : 'Visualization'}</span>
            </button>
          ))}
        </nav>

        <div className="system-box">
          <div className="sys-label">SYSTEM STATUS</div>
          <div className="sys-row"><span>Feed</span><strong>{mode}</strong></div>
          <div className="sys-row"><span>Propagation</span><strong>SGP4</strong></div>
          <div className="sys-row"><span>Risk engine</span><strong>EXPLAINABLE</strong></div>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <div className="eyebrow">SPACE SITUATIONAL AWARENESS</div>
            <h1>{view === 'overview' ? 'Mission Control' : view === 'conjunctions' ? 'Conjunction Events' : view === 'objects' ? 'Object Catalog' : view === 'alerts' ? 'Alert Center' : view === 'analytics' ? 'Historical Analytics' : 'Orbital Visualization'}</h1>
          </div>
          <div className="header-actions">
            <StatusPill mode={mode} />
            <div className="data-indicator">
              <Database size={14} />
              <span>{mode === 'LIVE' ? 'CelesTrak live feed' : mode === 'CACHED' ? 'CelesTrak cache / fresh' : 'Backend unavailable'}</span>
            </div>
            <button className="primary-button" onClick={() => void loadData()} disabled={loading}>
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
              {loading ? 'Refreshing' : 'Refresh'}
            </button>
          </div>
        </header>

        {error && <div className="error-banner">{error}</div>}

        {view === 'overview' && (
          <>
            <section className="metrics-grid">
              <MetricCard label="TRACKED OBJECTS" value={String(objects.length)} detail={mode === 'LIVE' ? 'from live cache' : mode === 'CACHED' ? 'from CelesTrak cache' : 'backend unavailable'} />
              <MetricCard label="ACTIVE CONJUNCTIONS" value={String(events.length)} detail="next 90-minute horizon" />
              <MetricCard label="HIGH RISK" value={`${criticalCount + highCount}`} detail="prioritized events" />
              <MetricCard label="CRITICAL" value={String(criticalCount)} detail="need immediate review" />
            </section>

            <section className="hero-grid">
              <div className="panel panel-visual">
                <div className="panel-header">
                  <div>
                    <div className="eyebrow">3D ORBITAL VIEW</div>
                    <h2>{selectedEvent ? 'Focus: conjunction encounter' : 'Fleet context'}</h2>
                  </div>
                  <span className="status-subtle">visualized at mission-control scale</span>
                </div>
                <OrbitScene selectedEvent={selectedEvent} selectedObject={selectedObject} objects={objects} trajectories={trajectories} selectedOrbit={selectedOrbit} conjunctionData={conjunctionData} mode={mode} />
              </div>

              <div className="panel">
                <div className="panel-header">
                  <div>
                    <div className="eyebrow">PRIORITY ALERTS</div>
                    <h2>Highest-risk events</h2>
                  </div>
                  <button className="text-button" onClick={() => setView('conjunctions')}>View all</button>
                </div>
                <div className="alert-stack">
                  {priorityEvents.length === 0 ? (
                    <div className="empty-state">No active conjunctions detected</div>
                  ) : priorityEvents.map((event) => (
                    <button key={`${event.catalog_a}-${event.catalog_b}`} className="alert-row" onClick={() => setSelectedEvent(event)}>
                      <div className={`risk-badge ${riskClass(event.risk_band)}`}>{event.risk_band}</div>
                      <div className="alert-pair">
                        <strong>{event.name_a}</strong>
                        <span>vs {event.name_b}</span>
                      </div>
                      <div className="alert-meta">
                        <span>{event.miss_distance_km.toFixed(1)} km</span>
                        <span>{formatTCA(event.tca)}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </section>

            <section className="bottom-grid">
              <div className="panel">
                <div className="panel-header compact">
                  <div>
                    <div className="eyebrow">CONJUNCTION MONITOR</div>
                    <h2>Upcoming close approaches</h2>
                  </div>
                  <button className="text-button" onClick={() => setView('conjunctions')}>Expand</button>
                </div>
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Object pair</th>
                        <th>TCA</th>
                        <th>Miss</th>
                        <th>Vel.</th>
                        <th>Risk</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredEvents.slice(0, 6).map((event) => (
                        <tr key={`${event.catalog_a}-${event.catalog_b}`} onClick={() => setSelectedEvent(event)}>
                          <td>{event.name_a} / {event.name_b}</td>
                          <td>{formatTCA(event.tca)}</td>
                          <td>{event.miss_distance_km.toFixed(1)} km</td>
                          <td>{event.relative_velocity_km_s.toFixed(1)} km/s</td>
                          <td><span className={`risk-badge ${riskClass(event.risk_band)}`}>{event.risk_band}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="panel panel-analytics">
                <div className="panel-header compact">
                  <div>
                    <div className="eyebrow">ANALYTICS</div>
                    <h2>Risk distribution</h2>
                  </div>
                  <button className="text-button" onClick={() => setView('analytics')}>Open</button>
                </div>
                <div className="distribution-bars">
                  <div className="bar-group"><label>Critical</label><div className="bar"><i style={{ width: `${Math.min(100, (criticalCount / Math.max(1, events.length)) * 100)}%` }} /></div><strong>{criticalCount}</strong></div>
                  <div className="bar-group"><label>High</label><div className="bar"><i style={{ width: `${Math.min(100, (highCount / Math.max(1, events.length)) * 100)}%` }} /></div><strong>{highCount}</strong></div>
                  <div className="bar-group"><label>Medium</label><div className="bar"><i style={{ width: `${Math.min(100, (mediumCount / Math.max(1, events.length)) * 100)}%` }} /></div><strong>{mediumCount}</strong></div>
                  <div className="bar-group"><label>Low</label><div className="bar"><i style={{ width: `${Math.min(100, (lowCount / Math.max(1, events.length)) * 100)}%` }} /></div><strong>{lowCount}</strong></div>
                </div>
                <div className="panel-footnote">
                  Explainable Prototype Risk Index is a prioritization score, not operational collision probability.
                </div>
              </div>
            </section>
          </>
        )}

        {view === 'conjunctions' && (
          <section className="panel">
            <div className="panel-header compact wrap">
              <div>
                <div className="eyebrow">ALL DETECTED EVENTS</div>
                <h2>Conjunction table</h2>
              </div>
              <div className="table-controls">
                <div className="search-box">
                  <Search size={14} />
                  <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search pair or ID" />
                </div>
                <select value={riskFilter} onChange={(event) => setRiskFilter(event.target.value as RiskFilter)}>
                  <option value="ALL">ALL</option>
                  <option value="CRITICAL">CRITICAL</option>
                  <option value="HIGH">HIGH</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="LOW">LOW</option>
                </select>
                <select value={sortMode} onChange={(event) => setSortMode(event.target.value as SortMode)}>
                  <option value="risk">Sort by risk</option>
                  <option value="miss">Sort by miss distance</option>
                  <option value="tca">Sort by TCA</option>
                  <option value="velocity">Sort by velocity</option>
                </select>
                <label className="toggle"><input type="checkbox" checked={upcomingOnly} onChange={(event) => setUpcomingOnly(event.target.checked)} /> Upcoming only</label>
              </div>
            </div>
            <div className="table-wrap large">
              {filteredEvents.length === 0 ? (
                <div className="empty-state">No conjunctions detected</div>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Risk band</th>
                      <th>Risk index</th>
                      <th>Object A</th>
                      <th>Object B</th>
                      <th>TCA</th>
                      <th>Time to TCA</th>
                      <th>Miss dist.</th>
                      <th>Vel.</th>
                      <th>Trend</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredEvents.map((event) => (
                      <tr key={`${event.catalog_a}-${event.catalog_b}`} onClick={() => setSelectedEvent(event)}>
                        <td><span className={`risk-badge ${riskClass(event.risk_band)}`}>{event.risk_band}</span></td>
                        <td>{event.risk_score.toFixed(1)}</td>
                        <td>{event.name_a}</td>
                        <td>{event.name_b}</td>
                        <td>{formatTCA(event.tca)}</td>
                        <td>{formatCountdown(event.time_to_tca_minutes)}</td>
                        <td>{event.miss_distance_km.toFixed(1)} km</td>
                        <td>{event.relative_velocity_km_s.toFixed(1)} km/s</td>
                        <td>{event.trend}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>
        )}

        {view === 'objects' && (
          <section className="panel">
            <div className="panel-header compact wrap">
              <div>
                <div className="eyebrow">OBJECT CATALOG</div>
                <h2>Tracked objects</h2>
              </div>
              <div className="search-box inline">
                <Search size={14} />
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search object name or catalog number" />
              </div>
            </div>
            <div className="catalog-grid">
              {visibleObjects.length === 0 ? (
                <div className="empty-state">No tracked objects available</div>
              ) : visibleObjects.map((object) => (
                <button
                  key={object.catalog_number}
                  className={`catalog-card ${selectedObject?.catalog_number === object.catalog_number ? 'selected' : ''}`}
                  onClick={() => selectObject(object)}
                >
                  <div className="catalog-icon"><Satellite size={16} /></div>
                  <div style={{ flex: 1 }}>
                    <div className="catalog-name">{object.name}</div>
                    <div className="catalog-meta">NORAD {object.catalog_number}</div>
                    <div className="catalog-meta">{object.source_group || 'tracked'} · {object.status || 'ACTIVE'}</div>
                  </div>
                  {selectedObject?.catalog_number === object.catalog_number && selectedObjectProfile?.orbital_state.orbit_regime && (
                    <span className="orbit-regime-mini">{selectedObjectProfile.orbital_state.orbit_regime}</span>
                  )}
                </button>
              ))}
            </div>
          </section>
        )}

        {view === 'alerts' && (
          <section className="panel">
            <div className="panel-header compact wrap">
              <div>
                <div className="eyebrow">ALERT CENTER</div>
                <h2>High and critical events</h2>
              </div>
              <div className="filter-inline">
                <button className="text-button" onClick={() => setRiskFilter('CRITICAL')}>CRITICAL</button>
                <button className="text-button" onClick={() => setRiskFilter('HIGH')}>HIGH</button>
              </div>
            </div>
            <div className="alert-list">
              {alertEvents.map((event) => (
                <div key={`${event.catalog_a}-${event.catalog_b}`} className="alert-item">
                  <div className="alert-header">
                    <span className={`risk-badge ${riskClass(event.risk_band)}`}>{event.risk_band}</span>
                    {event.trend === 'WORSENING' && <span className="new-badge">NEW</span>}
                  </div>
                  <h3>{event.name_a} / {event.name_b}</h3>
                  <div className="alert-detail-grid">
                    <div><span>TCA</span><strong>{formatTCA(event.tca)}</strong></div>
                    <div><span>Miss</span><strong>{event.miss_distance_km.toFixed(1)} km</strong></div>
                    <div><span>Risk</span><strong>{event.risk_score.toFixed(1)}</strong></div>
                    <div><span>Trend</span><strong>{event.trend}</strong></div>
                  </div>
                  <div className="alert-actions">
                    <button className="secondary-button" onClick={() => setSelectedEvent(event)}>Open</button>
                    <button className="secondary-button" onClick={() => setAcknowledged((prev) => ({ ...prev, [`${event.catalog_a}-${event.catalog_b}`]: true }))}>Acknowledge</button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {view === 'analytics' && (
          <section className="analytics-grid">
            <div className="panel">
              <div className="panel-header compact">
                <div>
                  <div className="eyebrow">HISTORICAL RISK</div>
                  <h2>System summary</h2>
                </div>
              </div>
              <div className="analytics-kpis">
                <div><span>Scan runs</span><strong>{analytics.scan_runs}</strong></div>
                <div><span>Stored obs.</span><strong>{analytics.stored_observations}</strong></div>
                <div><span>Mean risk</span><strong>{analytics.mean_risk_score.toFixed(1)}</strong></div>
                <div><span>Min miss</span><strong>{analytics.minimum_miss_distance_km ? `${analytics.minimum_miss_distance_km.toFixed(1)} km` : '—'}</strong></div>
              </div>
              <div className="distribution-grid">
                {Object.entries(analytics.risk_distribution).length === 0 ? (
                  <div className="empty-state">No analytics data available</div>
                ) : Object.entries(analytics.risk_distribution).map(([band, count]) => (
                  <div key={band} className={`mini-stat ${riskClass(band)}`}>
                    <strong>{count}</strong>
                    <span>{band}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="panel">
              <div className="panel-header compact">
                <div>
                  <div className="eyebrow">TREND MIX</div>
                  <h2>Observation trend</h2>
                </div>
              </div>
              <div className="analytics-kpis">
                {Object.entries(analytics.trend_distribution).length === 0 ? (
                  <div className="empty-state">No trend data available</div>
                ) : Object.entries(analytics.trend_distribution).map(([name, count]) => (
                  <div key={name}><span>{name}</span><strong>{count}</strong></div>
                ))}
              </div>
            </div>

            <div className="panel full-span">
              <div className="panel-header compact">
                <div>
                  <div className="eyebrow">TOP RECENT PAIRS</div>
                  <h2>Recurring conjunctions</h2>
                </div>
              </div>
              <div className="pair-list">
                {analytics.top_pairs.length === 0 ? (
                  <div className="empty-state">No recurring conjunction pairs</div>
                ) : analytics.top_pairs.map((pair) => (
                  <div key={`${pair.object_a}-${pair.object_b}`} className="pair-row">
                    <span>{pair.object_a} × {pair.object_b}</span>
                    <strong>{pair.latest_risk.toFixed(1)}</strong>
                    <small>{pair.latest_miss_distance_km.toFixed(1)} km / {pair.count} obs.</small>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {view === 'visualization' && (
          <section className="visualization-grid">
            <div className="panel">
              <div className="panel-header compact">
                <div>
                  <div className="eyebrow">ORBITAL VISUALIZATION</div>
                  <h2>{selectedObject ? selectedObject.name : '3D Earth & orbit tracks'}</h2>
                </div>
                <StatusPill mode={mode} />
              </div>
              <OrbitScene selectedEvent={selectedEvent} selectedObject={selectedObject} objects={objects} trajectories={trajectories} selectedOrbit={selectedOrbit} conjunctionData={conjunctionData} mode={mode} />
            </div>
            <div className="panel">
              <GroundTrack selectedEvent={selectedEvent} object={selectedObject} trajectory={selectedObject ? trajectories[selectedObject.catalog_number] ?? [] : []} />
            </div>
          </section>
        )}
      </main>

      {/* Satellite profile drawer — shown when an object is selected and showSatellitePanel is true */}
      {showSatellitePanel && selectedObjectProfile && (
        <SatelliteInfoPanel
          profile={selectedObjectProfile}
          onClose={() => setShowSatellitePanel(false)}
        />
      )}

      {selectedEvent && (
        <div className="drawer-backdrop" onClick={() => setSelectedEvent(null)}>
          <aside className="detail-drawer" onClick={(event) => event.stopPropagation()}>
            <div className="drawer-header">
              <div className="drawer-title-wrap">
                <div className={`risk-badge ${riskClass(selectedEvent.risk_band)}`}>{selectedEvent.risk_band}</div>
                <h3>Conjunction detail</h3>
              </div>
              <button className="icon-button" onClick={() => setSelectedEvent(null)}><XCircle size={18} /></button>
            </div>

            <div className="drawer-pair">
              <div><span>Object A</span><strong>{selectedEvent.name_a}</strong></div>
              <div className="pair-separator">×</div>
              <div><span>Object B</span><strong>{selectedEvent.name_b}</strong></div>
            </div>

            <div className="detail-grid">
              <div><span>TCA</span><strong>{formatTCA(selectedEvent.tca)}</strong></div>
              <div><span>Countdown</span><strong>{formatCountdown(selectedEvent.time_to_tca_minutes)}</strong></div>
              <div><span>Miss distance</span><strong>{selectedEvent.miss_distance_km.toFixed(2)} km</strong></div>
              <div><span>Relative velocity</span><strong>{selectedEvent.relative_velocity_km_s.toFixed(2)} km/s</strong></div>
              <div><span>Risk index</span><strong>{selectedEvent.risk_score.toFixed(1)} / 100</strong></div>
              <div><span>Trend</span><strong>{selectedEvent.trend}</strong></div>
            </div>

            <div className="breakdown-panel">
              <div className="eyebrow">RISK BREAKDOWN</div>
              <div className="score-summary">
                <span>Explainable Prototype Risk Index</span>
                <strong>{selectedEvent.risk_score.toFixed(1)}</strong>
              </div>
              <div className="score-row">
                <label>Miss distance</label>
                <div className="score-bar"><i style={{ width: `${selectedEvent.risk_breakdown.miss_distance_score}%` }} /></div>
                <strong>{selectedEvent.risk_breakdown.miss_distance_score.toFixed(0)}</strong>
              </div>
              <div className="score-row">
                <label>TCA imminence</label>
                <div className="score-bar"><i style={{ width: `${selectedEvent.risk_breakdown.imminence_score}%` }} /></div>
                <strong>{selectedEvent.risk_breakdown.imminence_score.toFixed(0)}</strong>
              </div>
              <div className="score-row">
                <label>Relative speed</label>
                <div className="score-bar"><i style={{ width: `${selectedEvent.risk_breakdown.relative_speed_score}%` }} /></div>
                <strong>{selectedEvent.risk_breakdown.relative_speed_score.toFixed(0)}</strong>
              </div>
              <div className="score-row">
                <label>Data freshness</label>
                <div className="score-bar"><i style={{ width: `${selectedEvent.risk_breakdown.freshness_score}%` }} /></div>
                <strong>{selectedEvent.risk_breakdown.freshness_score.toFixed(0)}</strong>
              </div>
              <ul className="reason-list">
                {selectedEvent.risk_breakdown.reasons.map((reason) => <li key={reason}>{reason}</li>)}
              </ul>
              <div className="disclaimer-box">Prototype prioritization score; not an operational probability of collision.</div>
            </div>

            <div className="historic-mini">
              <div className="eyebrow">HISTORIC TREND</div>
              <div className="historic-row">
                <span>No stored history yet</span>
              </div>
            </div>

            <button className="primary-button full-width" onClick={() => setView('visualization')}>Open 3D encounter</button>
          </aside>
        </div>
      )}
    </div>
  );
}

export default App;

