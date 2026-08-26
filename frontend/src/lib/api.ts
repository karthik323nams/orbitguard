import type {
  AnalyticsSummary,
  ConjunctionEvent,
  ConjunctionScanResponse,
  DataStatus,
  FullOrbitResponse,
  HealthStatus,
  HistoryResponse,
  ObjectDetailResponse,
  ObjectListResponse,
  ObjectTrajectoryResponse,
  SatelliteProfile,
} from '../types/orbitguard';

const normalizeBase = (value: string) => (value || 'http://127.0.0.1:8000').replace(/\/+$/, '');
export const API_BASE = normalizeBase(import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000');

async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 12000);

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(init.headers || {}),
      },
    });

    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      const message = detail && typeof detail.detail === 'string' ? detail.detail : `${response.status} ${response.statusText}`;
      throw new Error(message);
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('Request timed out');
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

const buildQuery = (params: Record<string, string | number | boolean | undefined>) => {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, String(value));
    }
  }
  const raw = query.toString();
  return raw ? `?${raw}` : '';
};

export const api = {
  getHealth: () => apiRequest<HealthStatus>('/health'),
  getDataStatus: () => apiRequest<DataStatus>('/data/status'),
  getObjects: () => apiRequest<ObjectListResponse>('/objects'),
  getObject: (noradId: string | number) => apiRequest<ObjectDetailResponse>(`/objects/${noradId}`),
  getTrajectory: (noradId: string | number, durationMinutes = 90, stepSeconds = 60) => apiRequest<ObjectTrajectoryResponse>(`/objects/${noradId}/trajectory?duration_minutes=${durationMinutes}&step_seconds=${stepSeconds}`),
  getCache: (group = 'tracked', limit = 200) => apiRequest<{ group: string; count: number; objects: Array<{ catalog_number: string; name: string; object_id?: string; source_group?: string; epoch?: string; data_age_minutes?: number; raw_omm?: Record<string, unknown> }> }>(`/data/cache?group=${encodeURIComponent(group)}&limit=${limit}`),
  refreshCache: (group = 'tracked', maxObjects = 500) => apiRequest<{ status: string; note?: string; records_fetched?: number; records_stored?: number; refreshed_at?: string; next_allowed_refresh_at?: string }>(`/data/refresh?group=${encodeURIComponent(group)}&max_objects=${maxObjects}`),
  scanConjunctions: (params: Record<string, string | number | boolean | undefined> = {}) => apiRequest<ConjunctionScanResponse>(`/conjunctions/scan${buildQuery(params)}`),
  getHistory: (catalogA: string, catalogB: string, limit = 30) => apiRequest<HistoryResponse>(`/conjunctions/history?catalog_a=${catalogA}&catalog_b=${catalogB}&limit=${limit}`),
  getAnalytics: () => apiRequest<AnalyticsSummary>('/conjunctions/history/analytics'),
  getVisualization: (catalogA: string | number, catalogB: string | number, duration = 30, step = 30) => apiRequest<{ frame: string; tca?: string; miss_distance_km?: number; relative_velocity_km_s?: number; trajectory_a?: Array<Record<string, number | string>>; trajectory_b?: Array<Record<string, number | string>>; tca_position_a?: Record<string, number>; tca_position_b?: Record<string, number> }>(`/conjunctions/visualization?catalog_a=${catalogA}&catalog_b=${catalogB}&duration_minutes=${duration}&step_seconds=${step}`),
  getFullOrbit: (noradId: string | number, stepSeconds?: number) =>
    apiRequest<FullOrbitResponse>(
      `/objects/${noradId}/full-orbit${stepSeconds !== undefined ? `?step_seconds=${stepSeconds}` : ''}`
    ),
  getSatelliteProfile: (noradId: string | number) =>
    apiRequest<SatelliteProfile>(`/objects/${noradId}/profile`),
};

export type CacheRow = { catalog_number: string; name: string; object_id?: string; source_group?: string; epoch?: string; data_age_minutes?: number; raw_omm?: Record<string, unknown> };
export type CatalogResult = Array<{ catalog_number: string; name: string; object_id?: string; source_group?: string; epoch?: string; data_age_minutes?: number; status?: string }>;
export type ApiError = { message: string; status?: number };

export type Event = ConjunctionEvent;
export type Trajectory = {
  name: string;
  catalog_number: string;
  frame: string;
  step_seconds: number;
  points: Array<{
    timestamp?: string;
    ecef_km?: { x: number; y: number; z: number };
    position_km?: { x: number; y: number; z: number };
    x_km?: number;
    y_km?: number;
    z_km?: number;
  }>;
};
