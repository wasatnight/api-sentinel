import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Service, Status, Store } from '../types';
type CollectionRecord = {
    id: string;
    name: string;
    created_at: string;
};
type ApiService = {
    id: string;
    name: string;
    url: string;
    method: string;
    interval_seconds: number;
    timeout_seconds: number;
    collection_id: string;
    status: string;
    created_at: string;
    last_checked_at: string | null;
    last_latency_ms: number | null;
    enabled: boolean;
    expected_status_min: number;
    expected_status_max: number;
    next_check_at: string | null;
};
type Configuration = {
    failure_alerts: boolean;
    recovery_alerts: boolean;
    latency_threshold: number;
};
export type ApiCheck = {
    id: string;
    service_id: string;
    service_name: string;
    checked_at: string;
    status_code: number | null;
    latency_ms: number | null;
    success: boolean;
    status: string;
    error: string | null;
    attempts: number;
};
type ApiIncident = {
    id: string;
    service_id: string;
    service_name: string;
    state: string;
    started_at: string;
    resolved_at: string | null;
    cause: string | null;
    duration_seconds: number;
};
export type ApiAlert = {
    id: string;
    service_id: string;
    service_name: string;
    incident_id: string | null;
    kind: string;
    message: string;
    created_at: string;
    read_at: string | null;
};
type Workspace = {
    services: ApiService[];
    collections: CollectionRecord[];
    configuration: Configuration;
    phase: number;
    monitoring_enabled: boolean;
    checks: ApiCheck[];
    incidents: ApiIncident[];
    active_incident_count: number;
    alerts: ApiAlert[];
    unread_alert_count: number;
    running_service_ids: string[];
};
const emptyStore: Store = { services: [], collections: [], incidents: [], checks: [], alerts: true, recovery: true, threshold: 400 };
export const statusName = (value: string): Status => ({ healthy: "Healthy", degraded: "Degraded", down: "Down" }[value] as Status) || "Not checked";
export { request } from '../lib/http';
import { request } from '../lib/http';
export function useWorkspace(enabled: boolean) {
    const client = useQueryClient();
    const query = useQuery({ queryKey: ['workspace'], queryFn: ({ signal }) => request<Workspace>('/workspace', 'GET', undefined, signal), enabled, retry: false, refetchOnWindowFocus: true, refetchInterval: enabled ? 2500 : false });
    const mutation = useMutation({ mutationFn: ({ path, method, body }: {
            path: string;
            method: string;
            body?: unknown;
        }) => request(path, method, body), onSuccess: async () => { await Promise.all([client.invalidateQueries({ queryKey: ['workspace'] }), client.invalidateQueries({ queryKey: ['checks'] }), client.invalidateQueries({ queryKey: ['alerts'] }), client.invalidateQueries({ queryKey: ['statistics'] }), client.invalidateQueries({ queryKey: ['activity'] })]); } });
    const data = query.data;
    const collectionName = (id: string) => data?.collections.find(c => c.id === id)?.name ?? '';
    const store: Store = data ? {
        activeIncidentCount: data.active_incident_count,
        services: data.services.map(s => ({ id: s.id, name: s.name, url: s.url, method: s.method, interval: s.interval_seconds, timeout: s.timeout_seconds, collection: collectionName(s.collection_id), status: statusName(s.status), latency: s.last_latency_ms, uptime: null, createdAt: s.created_at, lastCheckedAt: s.last_checked_at, enabled: s.enabled, expectedMin: s.expected_status_min, expectedMax: s.expected_status_max, nextCheckAt: s.next_check_at, checking: data.running_service_ids.includes(s.id) })),
        collections: data.collections.map(c => c.name),
        checks: data.checks.map(c => ({ id: c.id, serviceId: c.service_id, name: c.service_name, time: c.checked_at, code: c.status_code, latency: c.latency_ms ?? 0, status: statusName(c.status), error: c.error ?? undefined, attempts: c.attempts })),
        incidents: data.incidents.map(i => ({ id: i.id, serviceId: i.service_id, name: i.service_name, cause: i.cause ?? "Cause not identified", state: ({ investigating: "Investigating", monitoring: "Monitoring", resolved: "Resolved" }[i.state] ?? "Investigating") as "Investigating" | "Monitoring" | "Resolved", started: i.started_at, ended: i.resolved_at, duration: i.duration_seconds })),
        alerts: data.configuration.failure_alerts, recovery: data.configuration.recovery_alerts, threshold: data.configuration.latency_threshold
    } : emptyStore;
    const write = (path: string, method: string, body?: unknown) => mutation.mutateAsync({ path, method, body });
    return { store, loading: enabled && query.isPending, error: enabled ? query.error : null, pending: mutation.isPending, refresh: query.refetch, monitoring: data?.monitoring_enabled ?? false, notifications: data?.alerts, unreadAlerts: data?.unread_alert_count ?? 0,
        markRead: (id: string) => write('/alerts/' + id + '/read', 'PUT'),
        markAllRead: () => write('/alerts/read-all', 'POST'),
        collectionId: (name: string) => data?.collections.find(c => c.name === name)?.id,
        saveService: (s: Service, exists: boolean) => write('/services' + (exists ? '/' + s.id : ''), exists ? 'PUT' : 'POST', { name: s.name, url: s.url, method: s.method, interval_seconds: s.interval, timeout_seconds: s.timeout, collection_id: data?.collections.find(c => c.name === s.collection)?.id, enabled: s.enabled ?? true, expected_status_min: s.expectedMin ?? 200, expected_status_max: s.expectedMax ?? 299 }),
        deleteService: (id: string) => write('/services/' + id, 'DELETE'),
        createCollection: (name: string) => write('/collections', 'POST', { name }),
        renameCollection: (id: string, name: string) => write('/collections/' + id, 'PUT', { name }),
        deleteCollection: (id: string) => write('/collections/' + id, 'DELETE'),
        checkNow: (id: string) => write('/services/' + id + '/check', 'POST'),
        checkEnabled: () => write('/check-enabled', 'POST'),
        setMonitoring: (id: string, enabled: boolean) => write('/services/' + id + '/monitoring', 'PUT', { enabled }),
        setIncident: (id: string, state: string) => write('/incidents/' + id, 'PUT', { state: ({ Investigating: 'investigating', Monitoring: 'monitoring', Resolved: 'resolved' }[state]) }),
        configure: (config: Partial<Pick<Store, 'alerts' | 'recovery' | 'threshold'>>) => write('/configuration', 'PUT', { failure_alerts: config.alerts ?? store.alerts, recovery_alerts: config.recovery ?? store.recovery, latency_threshold: config.threshold ?? store.threshold }) };
}
