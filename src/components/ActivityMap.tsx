import { t, getLocale, localizeMessage } from '../lib/i18n';
import { useQuery } from '@tanstack/react-query';
import { Activity } from 'lucide-react';
import { request } from '../hooks/useWorkspace';
type Cell = {
    time: string;
    status: string;
    samples: number;
};
type Data = {
    start: string;
    end: string;
    rows: {
        id: string;
        name: string;
        cells: Cell[];
    }[];
    total_services: number;
};
const className = (value: string) => value === 'healthy' ? 'healthy' : value === 'degraded' ? 'warning' : value === 'down' ? 'danger' : 'unknown';
export function ActivityMap({ onService }: {
    onService: (id: string) => void;
}) {
    const query = useQuery({ queryKey: ['activity'], queryFn: ({ signal }) => request<Data>('/activity', 'GET', undefined, signal), retry: false, refetchInterval: 10000 });
    const data = query.data;
    return <section className="panel activity-panel real-activity"><header className="panel-head"><div><h2>{t("Activity map")}</h2><p>{t("Last 24 hours \u00B7 one point per hour")}</p></div></header>
 {query.isPending ? <p className="empty" role="status">{t("Loading activity\u2026")}</p> : query.error ? <div className="empty error" role="alert"><p>{localizeMessage(query.error.message)}</p><button className="secondary" onClick={() => query.refetch()}>{t("Retry")}</button></div> : !data?.rows.length ? <div className="empty"><Activity size={26}/><p>{t("Add services to view their activity.")}</p></div> : <><div className="heatmap">{data.rows.map(row => <div className="heat-row" key={row.id}><span title={row.name}>{row.name}</span><div>{row.cells.map(cell => { const label = cell.status === 'healthy' ? "Healthy" : cell.status === 'down' ? "Down" : cell.status === 'degraded' ? "Degraded" : cell.samples ? t("Unclassified") : t("No data"); const description = row.name + ', ' + new Date(cell.time).toLocaleString(getLocale()) + ', ' + label + ', ' + cell.samples + t(" samples"); return <button key={cell.time} title={description} aria-label={description} className={'heat ' + className(cell.status)} onClick={() => onService(row.id)}/>; })}</div></div>)}</div><div className="heat-axis">{[0, 6, 12, 18].map(i => <span key={i}>{new Date(data.rows[0].cells[i].time).toLocaleTimeString(getLocale(), { hour: '2-digit', hour12: false })} h</span>)}</div></>}
 <div className="heat-legend"><span><i className="dot healthy"/>{t("Healthy")}</span><span><i className="dot warning"/>{t("Degraded")}</span><span><i className="dot danger"/>{t("Down")}</span><span><i className="dot unknown"/>{t("No data")}</span></div>{data && data.total_services > 8 && <p className="analytics-note">{t("Showing the first 8 services by name.")}</p>}</section>;
}
