import type { AnalyticsSummary, ConjunctionEvent, ObjectCatalogEntry } from '../types/orbitguard';

export const demoCatalog: ObjectCatalogEntry[] = [
  { catalog_number: '25544', name: 'ISS (ZARYA)', source_group: 'active', object_type: 'space station', epoch: '2026-08-20T02:12:27Z', data_age_minutes: 18, status: 'ACTIVE' },
  { catalog_number: '123456', name: 'DEBRIS OBJECT 123456', source_group: 'active', object_type: 'debris', epoch: '2026-08-19T18:45:10Z', data_age_minutes: 41, status: 'TRACKED' },
  { catalog_number: '24793', name: 'CASSIOPE', source_group: 'active', object_type: 'satellite', epoch: '2026-08-20T00:07:30Z', data_age_minutes: 31, status: 'ACTIVE' },
  { catalog_number: '42712', name: 'FENGYUN 1C DEB', source_group: 'active', object_type: 'debris', epoch: '2026-08-20T01:08:00Z', data_age_minutes: 21, status: 'MONITORED' },
  { catalog_number: '28678', name: 'NOAA 18', source_group: 'active', object_type: 'weather', epoch: '2026-08-19T22:44:00Z', data_age_minutes: 52, status: 'ACTIVE' },
  { catalog_number: '22335', name: 'COSMOS 2251 DEB', source_group: 'active', object_type: 'debris', epoch: '2026-08-19T21:11:00Z', data_age_minutes: 70, status: 'TRACKED' },
  { catalog_number: '43226', name: 'ONEWEB-0421', source_group: 'active', object_type: 'constellation', epoch: '2026-08-20T02:49:00Z', data_age_minutes: 14, status: 'ACTIVE' },
  { catalog_number: '47888', name: 'STARLINK-3832', source_group: 'active', object_type: 'constellation', epoch: '2026-08-20T02:15:20Z', data_age_minutes: 27, status: 'ACTIVE' },
  { catalog_number: '40100', name: 'SENTINEL-1A', source_group: 'active', object_type: 'earth observation', epoch: '2026-08-20T03:02:10Z', data_age_minutes: 12, status: 'ACTIVE' },
  { catalog_number: '41338', name: 'HST', source_group: 'active', object_type: 'science', epoch: '2026-08-20T00:48:44Z', data_age_minutes: 24, status: 'ACTIVE' },
  { catalog_number: '44276', name: 'SL-14 R/B', source_group: 'active', object_type: 'rocket body', epoch: '2026-08-20T01:42:30Z', data_age_minutes: 16, status: 'MONITORED' },
  { catalog_number: '17759', name: 'AEROCUBE', source_group: 'active', object_type: 'cube sat', epoch: '2026-08-19T23:32:00Z', data_age_minutes: 38, status: 'ACTIVE' },
];

export const demoHistory: Record<string, any[]> = {
  '25544-123456': [
    { observation_id: 1, run_id: 10, observed_at: '2026-08-20T00:00:00Z', tca: '2026-08-20T01:20:00Z', miss_distance_km: 6.3, relative_speed_km_s: 12.7, risk_score: 69.2, risk_band: 'HIGH' },
    { observation_id: 2, run_id: 11, observed_at: '2026-08-20T00:30:00Z', tca: '2026-08-20T01:20:00Z', miss_distance_km: 4.8, relative_speed_km_s: 13.0, risk_score: 77.1, risk_band: 'HIGH' },
    { observation_id: 3, run_id: 12, observed_at: '2026-08-20T01:00:00Z', tca: '2026-08-20T01:20:00Z', miss_distance_km: 3.4, relative_speed_km_s: 13.5, risk_score: 90.7, risk_band: 'CRITICAL' },
  ],
  '42712-47888': [
    { observation_id: 4, run_id: 13, observed_at: '2026-08-19T23:00:00Z', tca: '2026-08-20T02:42:00Z', miss_distance_km: 18.7, relative_speed_km_s: 8.2, risk_score: 48.3, risk_band: 'MEDIUM' },
    { observation_id: 5, run_id: 14, observed_at: '2026-08-20T00:10:00Z', tca: '2026-08-20T02:42:00Z', miss_distance_km: 16.4, relative_speed_km_s: 8.1, risk_score: 50.8, risk_band: 'HIGH' },
  ],
  '22335-44276': [
    { observation_id: 6, run_id: 15, observed_at: '2026-08-19T21:00:00Z', tca: '2026-08-20T04:15:00Z', miss_distance_km: 27.6, relative_speed_km_s: 6.8, risk_score: 31.5, risk_band: 'MEDIUM' },
    { observation_id: 7, run_id: 16, observed_at: '2026-08-19T23:50:00Z', tca: '2026-08-20T04:15:00Z', miss_distance_km: 22.1, relative_speed_km_s: 7.0, risk_score: 34.7, risk_band: 'MEDIUM' },
    { observation_id: 8, run_id: 17, observed_at: '2026-08-20T01:35:00Z', tca: '2026-08-20T04:15:00Z', miss_distance_km: 26.4, relative_speed_km_s: 6.4, risk_score: 29.2, risk_band: 'MEDIUM' },
  ],
};

export const demoEvents: ConjunctionEvent[] = [
  { catalog_a: '25544', name_a: 'ISS (ZARYA)', catalog_b: '123456', name_b: 'DEBRIS OBJECT 123456', tca: '2026-08-20T01:20:00Z', miss_distance_km: 3.42, relative_velocity_km_s: 13.2, risk_score: 92.4, risk_band: 'CRITICAL', time_to_tca_minutes: 18, trend: 'WORSENING', data_age_minutes: 26, risk_breakdown: { miss_distance_score: 94, imminence_score: 76, relative_speed_score: 89, freshness_score: 81, reasons: ['Very small predicted miss distance', 'Closest approach is imminent', 'High relative encounter speed'], uncertainty_status: 'Prototype prioritization score; not an operational probability of collision.' } },
  { catalog_a: '42712', name_a: 'FENGYUN 1C DEB', catalog_b: '47888', name_b: 'STARLINK-3832', tca: '2026-08-20T02:42:00Z', miss_distance_km: 7.8, relative_velocity_km_s: 9.7, risk_score: 76.1, risk_band: 'HIGH', time_to_tca_minutes: 98, trend: 'WORSENING', data_age_minutes: 28, risk_breakdown: { miss_distance_score: 84, imminence_score: 64, relative_speed_score: 70, freshness_score: 76, reasons: ['Close predicted approach', 'TCA is within the next two hours', 'Moderate relative velocity'], uncertainty_status: 'Prototype prioritization score; not an operational probability of collision.' } },
  { catalog_a: '22335', name_a: 'COSMOS 2251 DEB', catalog_b: '44276', name_b: 'SL-14 R/B', tca: '2026-08-20T04:15:00Z', miss_distance_km: 18.6, relative_velocity_km_s: 6.9, risk_score: 55.8, risk_band: 'HIGH', time_to_tca_minutes: 169, trend: 'STABLE', data_age_minutes: 33, risk_breakdown: { miss_distance_score: 70, imminence_score: 49, relative_speed_score: 54, freshness_score: 69, reasons: ['Approach remains within the watch regime', 'TCA is a few hours away', 'Encounter speed remains moderate'], uncertainty_status: 'Prototype prioritization score; not an operational probability of collision.' } },
  { catalog_a: '24793', name_a: 'CASSIOPE', catalog_b: '123456', name_b: 'DEBRIS OBJECT 123456', tca: '2026-08-20T05:35:00Z', miss_distance_km: 23.4, relative_velocity_km_s: 5.7, risk_score: 43.2, risk_band: 'MEDIUM', time_to_tca_minutes: 331, trend: 'STABLE', data_age_minutes: 52, risk_breakdown: { miss_distance_score: 60, imminence_score: 43, relative_speed_score: 50, freshness_score: 54, reasons: ['Monitor for drift over the next several hours', 'TCA is not immediate', 'Relative velocity is moderate'], uncertainty_status: 'Prototype prioritization score; not an operational probability of collision.' } },
  { catalog_a: '40100', name_a: 'SENTINEL-1A', catalog_b: '43226', name_b: 'ONEWEB-0421', tca: '2026-08-20T07:10:00Z', miss_distance_km: 32.1, relative_velocity_km_s: 4.8, risk_score: 31.4, risk_band: 'MEDIUM', time_to_tca_minutes: 514, trend: 'IMPROVING', data_age_minutes: 21, risk_breakdown: { miss_distance_score: 49, imminence_score: 30, relative_speed_score: 37, freshness_score: 75, reasons: ['Miss distance is larger than the watch threshold', 'TCA is not immediate', 'Relative velocity remains modest'], uncertainty_status: 'Prototype prioritization score; not an operational probability of collision.' } },
  { catalog_a: '28678', name_a: 'NOAA 18', catalog_b: '41338', name_b: 'HST', tca: '2026-08-20T08:10:00Z', miss_distance_km: 41.3, relative_velocity_km_s: 4.9, risk_score: 24.6, risk_band: 'LOW', time_to_tca_minutes: 610, trend: 'NEW', data_age_minutes: 72, risk_breakdown: { miss_distance_score: 36, imminence_score: 21, relative_speed_score: 31, freshness_score: 38, reasons: ['Lower-priority proximity event', 'TCA is many hours away', 'Relative velocity is not elevated'], uncertainty_status: 'Prototype prioritization score; not an operational probability of collision.' } },
  { catalog_a: '17759', name_a: 'AEROCUBE', catalog_b: '44276', name_b: 'SL-14 R/B', tca: '2026-08-21T00:40:00Z', miss_distance_km: 51.0, relative_velocity_km_s: 10.8, risk_score: 47.8, risk_band: 'MEDIUM', time_to_tca_minutes: 1220, trend: 'STABLE', data_age_minutes: 45, risk_breakdown: { miss_distance_score: 55, imminence_score: 18, relative_speed_score: 64, freshness_score: 59, reasons: ['Potentially actionable over longer horizon', 'Relative speed is elevated', 'Miss distance is still moderate'], uncertainty_status: 'Prototype prioritization score; not an operational probability of collision.' } },
  { catalog_a: '43226', name_a: 'ONEWEB-0421', catalog_b: '47888', name_b: 'STARLINK-3832', tca: '2026-08-20T09:55:00Z', miss_distance_km: 14.1, relative_velocity_km_s: 11.3, risk_score: 63.2, risk_band: 'HIGH', time_to_tca_minutes: 760, trend: 'WORSENING', data_age_minutes: 22, risk_breakdown: { miss_distance_score: 80, imminence_score: 55, relative_speed_score: 72, freshness_score: 80, reasons: ['Close approach in the next 12 hours', 'Encounter speed is elevated', 'Miss distance is within the watch band'], uncertainty_status: 'Prototype prioritization score; not an operational probability of collision.' } },
];

export const demoAnalytics: AnalyticsSummary = {
  scan_runs: 12,
  stored_observations: 184,
  mean_risk_score: 43.2,
  minimum_miss_distance_km: 2.8,
  risk_distribution: { CRITICAL: 2, HIGH: 17, MEDIUM: 64, LOW: 101 },
  trend_distribution: { NEW: 12, WORSENING: 9, STABLE: 118, IMPROVING: 45 },
  top_pairs: [
    { object_a: 'ISS (ZARYA)', object_b: 'DEBRIS OBJECT 123456', count: 14, latest_risk: 92.4, latest_miss_distance_km: 3.42 },
    { object_a: 'FENGYUN 1C DEB', object_b: 'STARLINK-3832', count: 11, latest_risk: 76.1, latest_miss_distance_km: 7.8 },
    { object_a: 'ONEWEB-0421', object_b: 'STARLINK-3832', count: 9, latest_risk: 63.2, latest_miss_distance_km: 14.1 },
  ],
};
