import { api } from './api';
import type { AnalyticsSummary, ConjunctionEvent, HealthStatus, HistoryResponse, ObjectCatalogEntry } from '../types/orbitguard';

export type Repository = {
  getHealth: () => Promise<HealthStatus>;
  getCatalog: (group?: string, limit?: number) => Promise<ObjectCatalogEntry[]>;
  getEvents: (params?: Record<string, string | number>) => Promise<ConjunctionEvent[]>;
  getAnalytics: () => Promise<AnalyticsSummary>;
  getHistory: (catalogA: string | number, catalogB: string | number, limit?: number) => Promise<HistoryResponse>;
  refresh: () => Promise<{ status: string; message?: string }>;
};

export const liveRepository: Repository = {
  getHealth: api.getHealth,
  getCatalog: async (group = 'active', limit = 200) => {
    const result = await api.getCache(group, limit);
    return result.objects.map((row) => ({
      catalog_number: String(row.catalog_number),
      name: row.name,
      object_id: row.object_id,
      source_group: row.source_group,
      epoch: row.epoch,
      data_age_minutes: row.data_age_minutes,
      status: 'ACTIVE',
    }));
  },
  getEvents: async (params = {}) => {
    const result = await api.scanConjunctions(params as Record<string, string | number>);
    return result.events ?? [];
  },
  getAnalytics: async () => {
    const result = await api.getAnalytics();
    return result;
  },
  getHistory: async (catalogA, catalogB, limit = 30) => api.getHistory(String(catalogA), String(catalogB), limit),
  refresh: async () => {
    const result = await api.refreshCache('active', 500);
    return { status: result.status ?? 'ok', message: result.note || 'Live data refreshed.' };
  },
};
