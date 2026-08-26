export type RiskBand = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type RiskBreakdown = {
  miss_distance_score: number;
  imminence_score: number;
  relative_speed_score: number;
  freshness_score: number;
  reasons: string[];
  uncertainty_status: string;
};

export type ConjunctionEvent = {
  id?: string;
  catalog_a: string;
  name_a: string;
  catalog_b: string;
  name_b: string;
  tca: string;
  miss_distance_km: number;
  relative_velocity_km_s: number;
  risk_score: number;
  risk_band: RiskBand;
  risk_level?: string;
  priority_score?: number;
  time_to_tca_minutes: number;
  trend: "NEW" | "WORSENING" | "STABLE" | "IMPROVING";
  data_age_minutes: number;
  risk_breakdown: RiskBreakdown;
  object_a?: { norad_id: number; name: string };
  object_b?: { norad_id: number; name: string };
};

export type ObjectCatalogEntry = {
  catalog_number: string;
  name: string;
  object_id?: string;
  object_type?: string;
  source_group?: string;
  epoch?: string;
  data_age_minutes?: number;
  status?: string;
};

export type HistoryObservation = {
  observation_id: number;
  run_id: number;
  observed_at: string;
  tca: string;
  miss_distance_km: number;
  relative_speed_km_s: number;
  risk_score: number;
  risk_band: RiskBand;
};

export type HistoryResponse = {
  catalog_a: number;
  catalog_b: number;
  trend: "NEW" | "WORSENING" | "STABLE" | "IMPROVING";
  observation_count: number;
  observations: HistoryObservation[];
};

export type AnalyticsSummary = {
  scan_runs: number;
  stored_observations: number;
  mean_risk_score: number;
  minimum_miss_distance_km: number | null;
  risk_distribution: Record<string, number>;
  trend_distribution: Record<string, number>;
  top_pairs: Array<{
    object_a: string;
    object_b: string;
    count: number;
    latest_risk: number;
    latest_miss_distance_km: number;
  }>;
};

export type HealthStatus = {
  status: string;
  service: string;
  version: string;
  data_mode: "live" | "cached" | "offline" | string;
};

export type DataStatus = {
  mode: "LIVE" | "CACHED" | "OFFLINE" | string;
  source: string;
  object_count: number;
  last_successful_fetch?: string | null;
  cache_age_seconds?: number | null;
  cache_fresh: boolean;
  stale: boolean;
  group: string;
};

export type ObjectListResponse = {
  group: string;
  count: number;
  objects: Array<{
    catalog_number: number | string;
    norad_id?: number | string;
    name: string;
    object_name?: string;
    object_id?: string;
    source_group?: string;
    epoch?: string;
    fetched_at?: string;
    last_successful_fetch?: string;
    raw_omm?: Record<string, unknown>;
    cache_fresh?: boolean;
    data_age_minutes?: number;
  }>;
};

export type ObjectDetailResponse = {
  catalog_number: number;
  norad_id: number;
  name: string;
  source_group: string;
  epoch?: string;
  fetched_at?: string;
  last_successful_fetch?: string;
  raw_omm?: Record<string, unknown>;
};

export type ObjectTrajectoryPoint = {
  timestamp: string;
  position_km: [number, number, number];
  velocity_km_s: [number, number, number];
};

export type ObjectTrajectoryResponse = {
  catalog_number: number;
  norad_id: number;
  name: string;
  start: string;
  duration_minutes: number;
  step_seconds: number;
  points: ObjectTrajectoryPoint[];
};

export type ConjunctionScanResponse = {
  status?: string;
  scan_id?: number;
  objects_scanned?: number;
  objects_screened?: number;
  pairs_checked?: number;
  candidate_pairs?: number;
  threshold_km?: number;
  duration_minutes?: number;
  step_seconds?: number;
  conjunctions?: ConjunctionEvent[];
  events?: ConjunctionEvent[];
  propagation_failures?: Array<{ catalog_number: number; name: string; error: string }>;
};

export type TrajectoryPoint = {
  timestamp: string;
  x_km?: number;
  y_km?: number;
  z_km?: number;
  lat_deg?: number;
  lon_deg?: number;
  alt_km?: number;
  ecef_x_km?: number;
  ecef_y_km?: number;
  ecef_z_km?: number;
};

export type VisualizationResponse = {
  frame: string;
  tca?: string;
  miss_distance_km?: number;
  relative_velocity_km_s?: number;
  trajectory_a?: TrajectoryPoint[];
  trajectory_b?: TrajectoryPoint[];
  tca_position_a?: { x_km: number; y_km: number; z_km: number };
  tca_position_b?: { x_km: number; y_km: number; z_km: number };
};

// ---------------------------------------------------------------------------
// Full orbit types (new)
// ---------------------------------------------------------------------------

export type FullOrbitPoint = {
  timestamp: string;
  x_km: number;
  y_km: number;
  z_km: number;
  vx_km_s: number;
  vy_km_s: number;
  vz_km_s: number;
};

export type FullOrbitCurrentPosition = {
  timestamp: string;
  x_km: number;
  y_km: number;
  z_km: number;
  lat_deg: number;
  lon_deg: number;
  alt_km: number;
  velocity_km_s: number;
};

export type FullOrbitResponse = {
  catalog_number: number;
  norad_id: number;
  name: string;
  frame: string;
  orbital_period_minutes: number;
  step_seconds: number;
  orbit_start: string;
  orbit_end: string;
  current_position: FullOrbitCurrentPosition | null;
  points: FullOrbitPoint[];
};

// ---------------------------------------------------------------------------
// Satellite profile types (new)
// ---------------------------------------------------------------------------

export type SatelliteIdentity = {
  name: string;
  norad_id: number;
  cospar_id: string | null;
  object_type: string | null;
};

export type OrbitalState = {
  epoch: string | null;
  mean_motion_rev_day: number | null;
  eccentricity: number | null;
  inclination_deg: number | null;
  ra_of_asc_node_deg: number | null;
  arg_of_pericenter_deg: number | null;
  period_minutes: number | null;
  apogee_km: number | null;
  perigee_km: number | null;
  orbit_regime: string | null;
};

export type SatelliteCurrentPosition = {
  timestamp: string;
  lat_deg: number;
  lon_deg: number;
  alt_km: number;
  velocity_km_s: number;
  teme_x_km: number;
  teme_y_km: number;
  teme_z_km: number;
};

export type LaunchMetadata = {
  cospar_id: string | null;
  launch_year: number | null;
  launch_number: number | null;
  piece: string | null;
  country: string | null;
  launch_date: string | null;
  launch_site: string | null;
  launch_vehicle: string | null;
  data_note: string;
};


export type TrackingStatus = {
  data_mode: "LIVE" | "CACHED" | string;
  last_updated: string | null;
  data_age_minutes: number | null;
  source: string;
};

export type SatelliteProfile = {
  identity: SatelliteIdentity;
  orbital_state: OrbitalState;
  current_position: SatelliteCurrentPosition | null;
  launch_metadata: LaunchMetadata;
  tracking_status: TrackingStatus;
};

