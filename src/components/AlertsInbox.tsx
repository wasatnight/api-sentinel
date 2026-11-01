import { t, getLocale, localizeMessage } from '../lib/i18n';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Bell, CheckCheck } from 'lucide-react';
import { request, type ApiAlert } from '../hooks/useWorkspace';
export function AlertsInbox({ unread, pending, onRead, onReadAll }: {
    unread: number;
    pending: boolean;
    onRead: (id: string) => void;
    onReadAll: () => void;
}) {
    const [kind, setKind] = useState(''), [onlyUnread, setOnlyUnread] = useState(false), [page, setPage] = useState(0);
    const query = useQuery({ queryKey: ['alerts', kind, onlyUnread, page], queryFn: ({ signal }) => request<ApiAlert[]>('/alerts?limit=50&offset=' + page * 50 + (kind ? '&kind=' + kind : '') + (onlyUnread ? '&unread_only=true' : ''), 'GET', undefined, signal), refetchInterval: 5000, retry: false });
    const rows = query.data ?? [];
    return <section className="panel alerts-inbox"><header className="panel-head"><div><h2>{t("Alert inbox")}</h2><p>{unread}{t("unread \u00B7 changes detected by live monitoring")}</p></div><button className="secondary" disabled={pending || !unread} onClick={onReadAll}><CheckCheck size={15}/>{t("Mark all as read")}</button></header>
 <div className="alert-filters"><label>{t("Type")}<select value={kind} onChange={e => { setKind(e.target.value); setPage(0); }}><option value="">{t("All alerts")}</option><option value="failure">{t("Failures")}</option><option value="degradation">Degradaciones</option><option value="recovery">Recuperaciones</option></select></label><label className="monitor-toggle"><input type="checkbox" checked={onlyUnread} onChange={e => { setOnlyUnread(e.target.checked); setPage(0); }}/>{t("Unread only")}</label></div>
 {query.isPending ? <p className="empty" role="status">{t("Loading alerts\u2026")}</p> : query.error ? <div className="empty error" role="alert"><p>{localizeMessage(query.error.message)}</p><button className="secondary" onClick={() => query.refetch()}>{t("Retry")}</button></div> : rows.length ? <div className="alert-records">{rows.map(a => <article className={'alert-record ' + (a.read_at ? 'read' : 'unread')} key={a.id}><i className={'dot ' + (a.kind === 'recovery' ? 'healthy' : a.kind === 'degradation' ? 'warning' : 'danger')}/><div><header><strong>{a.service_name}</strong><span className={'badge ' + (a.kind === 'recovery' ? 'healthy' : a.kind === 'degradation' ? 'warning' : 'danger')}>{a.kind === 'recovery' ? t("Recovery") : a.kind === 'degradation' ? t("Degradation") : 'Fallo'}</span>{!a.read_at && <span className="unread-label">{t("Unread")}</span>}</header><p>{localizeMessage(a.message)}</p><small>{new Date(a.created_at).toLocaleString(getLocale())}{a.read_at ? t(" \u00B7 Read") : ''}</small></div>{!a.read_at && <button className="secondary" disabled={pending} onClick={() => onRead(a.id)}>{t("Mark as read")}</button>}</article>)}</div> : <div className="empty"><Bell size={28}/><h3>{t("No alerts in this view")}</h3><p>{t("Notifications appear when failures, degradations or recoveries are detected, based on your preferences.")}</p></div>}
 <footer className="pagination"><button className="secondary" disabled={page === 0 || query.isPending} onClick={() => setPage(page - 1)}>{t("Previous")}</button><span>{t("Page")}{page + 1}</span><button className="secondary" disabled={rows.length < 50 || query.isPending} onClick={() => setPage(page + 1)}>{t("Next")}</button></footer></section>;
}
