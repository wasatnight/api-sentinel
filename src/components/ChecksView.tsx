import { t, getLocale, localizeMessage } from '../lib/i18n';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CheckCheck, Play } from 'lucide-react';
import { request, statusName, type ApiCheck } from '../hooks/useWorkspace';
import type { Service } from '../types';
export function ChecksView({ services, onCheck, pending, monitoring }: {
    services: Service[];
    onCheck: (id?: string) => void;
    pending: boolean;
    monitoring: boolean;
}) {
    const [serviceId, setServiceId] = useState(''), [page, setPage] = useState(0);
    const query = useQuery({ queryKey: ['checks', serviceId, page], queryFn: ({ signal }) => request<ApiCheck[]>('/checks?limit=50&offset=' + page * 50 + (serviceId ? '&service_id=' + encodeURIComponent(serviceId) : ''), 'GET', undefined, signal), refetchInterval: page === 0 ? 2500 : false, retry: false });
    const rows = query.data ?? [];
    return <><section className="panel controls-panel"><div><h2>{t("Live checks")}</h2><p>{t("The backend runs scheduled checks even when this window is closed. You can request a manual check even when a service is paused.")}</p></div><div className="inline-controls"><label>{t("Filter by service")}<select value={serviceId} onChange={e => { setServiceId(e.target.value); setPage(0); }}><option value="">{t("All services")}</option>{services.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label><button className="primary" disabled={pending || !monitoring || !services.length} onClick={() => onCheck(serviceId || undefined)}><Play size={15}/>{serviceId ? t("Check now") : t("Check enabled services")}</button></div></section>
 <section className="panel"><header className="panel-head"><h2>{t("Check history")}</h2><span className="muted">{t("50 results per page")}</span></header>
 {query.error && <div className="connection-state error" role="alert">{localizeMessage(query.error.message)}<button className="secondary" onClick={() => query.refetch()}>{t("Retry")}</button></div>}
 {query.isPending ? <p className="empty" role="status">{t("Loading check history\u2026")}</p> : <div className="table-scroll"><table><thead><tr><th>{t("Service")}</th><th>{t("Date and time")}</th><th>{t("Result")}</th><th>{t("Time")}</th><th>{t("Attempts")}</th></tr></thead><tbody>{rows.map(c => <tr key={c.id}><td>{c.service_name}</td><td>{new Date(c.checked_at).toLocaleString(getLocale())}</td><td><span className={'status ' + ({ healthy: 'healthy', degraded: 'warning', down: 'danger' }[c.status] ?? 'unknown')}><i className="dot"/>{c.status_code ? 'HTTP ' + c.status_code : t(statusName(c.status))}</span>{c.error && <small className="check-error">{localizeMessage(c.error)}</small>}</td><td>{c.latency_ms === null ? '—' : Math.round(c.latency_ms) + ' ms'}</td><td>{c.attempts}</td></tr>)}</tbody></table></div>}
 {!query.isPending && !rows.length && !query.error && <div className="empty"><CheckCheck size={28}/><h3>{t("No checks in this view yet")}</h3><p>{t("Add an enabled service or request a check.")}</p></div>}
 <footer className="pagination"><button className="secondary" disabled={page === 0 || query.isPending} onClick={() => setPage(page - 1)}>{t("Previous")}</button><span>{t("Page")}{page + 1}</span><button className="secondary" disabled={rows.length < 50 || query.isPending} onClick={() => setPage(page + 1)}>{t("Next")}</button></footer></section></>;
}
