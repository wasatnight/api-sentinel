import { t, getLocale, localizeMessage } from '../lib/i18n';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';
import type { UseQueryResult } from '@tanstack/react-query';
import { Activity } from 'lucide-react';
import { numberLabel, type Statistics } from '../hooks/useAnalytics';
const colors = ['#3796ff', '#00b98d', '#e9ad16', '#ad72ea', '#f07161', '#3abcc6'];
export function RangeTabs({ range, onRange }: {
    range: string;
    onRange: (value: string) => void;
}) {
    return <div className="range-tabs" aria-label={t("Period")}>{['1H', '6H', '24H', '7D', '30D'].map(r => <button key={r} onClick={() => onRange(r)} aria-pressed={range === r} className={range === r ? 'selected' : ''}>{r}</button>)}</div>;
}
export function HistoricalChart({ query, range, onRange, light = false }: {
    query: UseQueryResult<Statistics, Error>;
    range: string;
    onRange: (value: string) => void;
    light?: boolean;
}) {
    const palette = light ? ['#2466bd', '#007f60', '#996800', '#8051b0', '#b84c3e', '#087f8d'] : colors;
    const data = query.data;
    const hasLatency = (data?.summary.latency_count ?? 0) > 0;
    const time = (stamp: string) => new Date(stamp).toLocaleString(getLocale(), range === '7D' || range === '30D' ? { day: '2-digit', month: 'short', hour: '2-digit' } : { hour: '2-digit', minute: '2-digit' });
    return <section className="panel chart-panel historical-chart"><header className="panel-head"><div><h2>{t("Response time trends")}</h2><p>{t("Average per interval \u00B7 real samples in milliseconds")}</p></div><RangeTabs range={range} onRange={onRange}/></header>
 {query.isPending ? <p className="empty" role="status">{t("Loading history\u2026")}</p> : query.error ? <div className="empty error" role="alert"><p>{localizeMessage(query.error.message)}</p><button className="secondary" onClick={() => query.refetch()}>{t("Retry")}</button></div> : !hasLatency ? <div className="empty"><Activity size={27}/><h3>{t("No latency samples in this period")}</h3><p>{t("Recorded checks will appear here. Empty intervals are not filled in.")}</p></div> : <><div className="chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={data?.points} margin={{ left: 5, right: 22, top: 12, bottom: 0 }}><CartesianGrid vertical={false} stroke="#29333d"/><XAxis dataKey="time" tickFormatter={time} minTickGap={65} tick={{ fill: '#aab9c9', fontSize: 10 }} axisLine={false} tickLine={false}/><YAxis width={68} tick={{ fill: '#aab9c9', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={v => numberLabel(v) + ' ms'} domain={[0, 'auto']}/><Tooltip itemStyle={{ color: '#f1f6ff' }} labelFormatter={v => new Date(String(v)).toLocaleString(getLocale())} formatter={(value, name) => [numberLabel(Number(value), ' ms'), name]} contentStyle={{ background: '#172231', border: '1px solid #415775', borderRadius: 10, color: '#fff' }}/>{data?.series.map((s, i) => <Line key={s.id} dataKey={s.id} name={s.name} type="linear" connectNulls={false} stroke={palette[i % palette.length]} strokeWidth={1.8} dot={{ r: 2, strokeWidth: 0 }} activeDot={{ r: 4 }} isAnimationActive={false}/>)}</LineChart></ResponsiveContainer></div><div className="chart-legend">{data?.series.map((s, i) => <span key={s.id}><i style={{ background: palette[i % palette.length] }}/>{s.name}</span>)}</div></>}
 <p className="analytics-note">{t("Availability is based on evaluated checks; periods without data are not extrapolated.")}{data && data.series_total > 6 ? t(" Showing 6 series by name; select a service in Reports to view the others.") : ''}</p></section>;
}
export function ReportDetails({ data }: {
    data?: Statistics;
}) {
    if (!data)
        return null;
    const m = data.summary;
    return <><div className="detail-stats">{[["Recorded checks", m?.total_checks, ''], ["Errors", m?.error_rate, ' %'], ["Minimum latency", m?.latency_min, ' ms'], ["Maximum latency", m?.latency_max, ' ms'], ['p50', m?.p50, ' ms'], ['p95', m?.p95, ' ms'], ['p99', m?.p99, ' ms'], ["Incidents in this period", m?.incident_count, '']].map(([label, value, unit]) => <section className="panel detail-stat" key={String(label)}><span>{t(String(label))}</span><strong>{numberLabel(value as number | undefined, String(unit))}</strong></section>)}</div>
 <section className="panel"><header className="panel-head"><div><h2>{t("Service statistics")}</h2><p>{data?.period ?? '—'}{t("\u00B7 empty values indicate no evaluated samples")}</p></div></header><div className="table-scroll"><table><thead><tr><th>{t("Service")}</th><th>Checks</th><th>{t("Availability")}</th><th>{t("Errors")}</th><th>{t("Average")}</th><th>p95</th><th>p99</th></tr></thead><tbody>{data?.services.map(s => <tr key={s.id}><td>{s.name}</td><td>{s.total_checks}</td><td>{numberLabel(s.availability, ' %')}</td><td>{numberLabel(s.error_rate, ' %')}</td><td>{numberLabel(s.latency_avg, ' ms')}</td><td>{numberLabel(s.p95, ' ms')}</td><td>{numberLabel(s.p99, ' ms')}</td></tr>)}</tbody></table></div>{!data?.services.length && <p className="empty">{t("No services in this selection.")}</p>}</section>
 <section className="panel incident-report"><header className="panel-head"><h2>{t("Incident history for this period")}</h2><span className="muted">{m?.incident_count ?? 0}{t("incidents")}</span></header>{data?.incidents.map(i => <article key={i.id}><strong>{i.name}</strong><span className={'badge ' + (i.state === 'resolved' ? 'healthy' : i.state === 'monitoring' ? 'warning' : 'danger')}>{i.state === 'resolved' ? t("Resolved") : i.state === 'monitoring' ? t("Monitoring") : t("Investigating")}</span><p>{i.cause ?? t("Cause not identified")}</p><small>{new Date(i.started_at).toLocaleString(getLocale())} · {Math.floor(i.duration_seconds / 60)} min {i.duration_seconds % 60} s</small></article>)}{!data?.incidents.length && <p className="empty">{t("No incidents in this period.")}</p>}{(m?.incident_count ?? 0) > 100 && <p className="analytics-note">{t("Showing the 100 most recent incidents in this period.")}</p>}</section></>;
}
