import { t } from './i18n';
import type { Metrics, Statistics } from '../types';
export function statisticsCsv(data: Statistics) {
    const headers = ["Period", "From UTC", "To UTC", "Service ID", "Service", 'Checks', "Evaluated", "Unclassified", "Successful", "Failures", "Check-based availability %", "Errors %", "Latency samples", "Average ms", "Minimum ms", "Maximum ms", 'p50 ms', 'p95 ms', 'p99 ms'];
    const row = (name: string, m: Metrics, id = '') => [data.period, data.start, data.end, id, name, m.total_checks, m.evaluated_checks, m.unknown_checks, m.successes, m.failures, m.availability, m.error_rate, m.latency_count, m.latency_avg, m.latency_min, m.latency_max, m.p50, m.p95, m.p99];
    const rows = [headers.map(header => t(header)), row('TOTAL', data.summary), ...data.services.map(s => row(s.name, s, s.id))];
    const cell = (value: unknown) => {
        let text = value === null || value === undefined ? '' : String(value);
        if (/^[=+@\-\t\r]/.test(text))
            text = "'" + text;
        return '"' + text.replaceAll('"', '""') + '"';
    };
    return '\uFEFF' + rows.map(r => r.map(cell).join(',')).join('\r\n');
}
