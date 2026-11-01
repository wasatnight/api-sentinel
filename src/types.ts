export type Status = "Healthy" | "Degraded" | "Down" | "Not checked";
export type Service = {
    id: string;
    name: string;
    url: string;
    method: string;
    interval: number;
    timeout: number;
    collection: string;
    status: Status;
    latency: number | null;
    uptime: number | null;
    enabled?: boolean;
    expectedMin?: number;
    expectedMax?: number;
    nextCheckAt?: string | null;
    checking?: boolean;
    createdAt?: string;
    lastCheckedAt?: string | null;
};
export type Incident = {
    id: string;
    serviceId: string;
    name: string;
    cause: string;
    state: "Investigating" | "Monitoring" | "Resolved";
    started: string;
    ended?: string | null;
    duration?: number;
};
export type DemoCheck = {
    id: string;
    serviceId: string;
    name: string;
    time: string;
    code: number | null;
    latency: number;
    status: Status;
    error?: string;
    attempts?: number;
};
export type Store = {
    activeIncidentCount?: number;
    services: Service[];
    incidents: Incident[];
    checks: DemoCheck[];
    collections: string[];
    alerts: boolean;
    threshold: number;
    recovery: boolean;
};
export type Metrics = {
    total_checks: number;
    evaluated_checks: number;
    unknown_checks: number;
    successes: number;
    failures: number;
    availability: number | null;
    error_rate: number | null;
    latency_count: number;
    latency_avg: number | null;
    latency_min: number | null;
    latency_max: number | null;
    p50: number | null;
    p95: number | null;
    p99: number | null;
    active_incidents?: number;
    incident_count?: number;
};
export type Statistics = {
    period: string;
    start: string;
    end: string;
    bucket_seconds: number;
    summary: Metrics;
    services: (Metrics & {
        id: string;
        name: string;
    })[];
    series: {
        id: string;
        name: string;
    }[];
    series_total: number;
    points: ({
        time: string;
    } & Record<string, string | number | null>)[];
    incidents: {
        id: string;
        service_id: string;
        name: string;
        state: string;
        started_at: string;
        resolved_at: string | null;
        cause: string | null;
        duration_seconds: number;
    }[];
};
