import { getLocale } from '../lib/i18n';
import type { Statistics } from '../types';
export type { Metrics, Statistics } from '../types';
import { statisticsCsv } from '../lib/reportCsv';
import { useQuery } from '@tanstack/react-query';
import { request } from './useWorkspace';
export function useAnalytics(enabled: boolean, period: string, serviceId = '', collectionId = '') {
    return useQuery({ queryKey: ['statistics', period, serviceId, collectionId], queryFn: ({ signal }) => request<Statistics>('/statistics?period=' + period + (serviceId ? '&service_id=' + encodeURIComponent(serviceId) : '') + (collectionId ? '&collection_id=' + encodeURIComponent(collectionId) : ''), 'GET', undefined, signal), enabled, retry: false, refetchInterval: enabled ? 10000 : false, refetchOnWindowFocus: true });
}
export const numberLabel = (value: number | null | undefined, suffix = '') => value === null || value === undefined ? '—' : new Intl.NumberFormat(getLocale(), { maximumFractionDigits: 2 }).format(value) + suffix;
export function downloadStatistics(data: Statistics) {
    const blob = new Blob([statisticsCsv(data)], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = "api-sentinel-report-" + data.period + '.csv';
    a.click();
    URL.revokeObjectURL(url);
}
