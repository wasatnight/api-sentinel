import { t, getLocale, localizeMessage, serviceCount } from './lib/i18n';
import { NotificationTracker } from './lib/notifications';
import { useEffect, useRef, useState } from 'react';
import { Activity, ArrowDown, ArrowRight, Bell, Box, CheckCheck, Clock3, Database, Download, EllipsisVertical, FileChartColumn, Home, Layers3, LockKeyhole, Mail, Menu, Pencil, Play, Plus, Search, Settings, ShieldCheck, Info, Pause, Sun, Trash2, Unplug, X } from 'lucide-react';
import { useWorkspace } from './hooks/useWorkspace';
import { useLanguage } from './hooks/useLanguage';
import { Modal } from './components/Modal';
import { ServiceForm } from './components/ServiceForm';
import { ChecksView } from './components/ChecksView';
import { useAnalytics, downloadStatistics, numberLabel } from './hooks/useAnalytics';
import { HistoricalChart, ReportDetails, RangeTabs } from './components/HistoricalChart';
import { ActivityMap } from './components/ActivityMap';
import { AlertsInbox } from './components/AlertsInbox';
import type { Service, Status } from './types';
import { ProfileSettings } from './components/ProfileSettings';
import { usePreferences, initials } from './hooks/usePreferences';
const navigation = [["Home", Home], ["Services", Layers3], ['Checks', CheckCheck], ["Incidents", Bell], ["Alerts", Bell], ["Reports", FileChartColumn], ["Integrations", Unplug]] as const;
const statusClass = (status: Status) => status === "Healthy" ? 'healthy' : status === "Degraded" ? 'warning' : status === "Down" ? 'danger' : 'unknown';
function ServiceIcon({ id }: {
    id: string;
}) { const Icon = id === 'auth' ? LockKeyhole : id === 'payment' ? FileChartColumn : id === 'notify' ? Mail : id === 'analytics' ? Activity : Database; return <span className={'service-icon icon-' + id}><Icon size={24}/></span>; }
export default function App() {
    const { language, setLanguage } = useLanguage();
    const [page, setPage] = useState("Home"), [collection, setCollection] = useState(''), [search, setSearch] = useState(''), [filter, setFilter] = useState("All"), [range, setRange] = useState('24H');
    const [reportService, setReportService] = useState(''), [reportCollection, setReportCollection] = useState('');
    const live = useWorkspace(true);
    const analytics = useAnalytics(["Home", "Reports", "Services"].includes(page), range, page === "Reports" ? reportService : '', page === "Reports" && reportCollection ? live.collectionId(reportCollection) ?? '' : '');
    const historical = analytics.data?.summary;
    const availabilityById = new Map(analytics.data?.services.map(s => [s.id, s.availability]));
    const store = live.store;
    const [operationError, setOperationError] = useState('');
    async function perform(action: () => Promise<unknown>) {
        setOperationError('');
        try {
            await action();
            return true;
        }
        catch (e) {
            setOperationError(e instanceof Error ? e.message : t("Could not save the change."));
            return false;
        }
    }
    async function createCollection(name: string) {
        if (!await perform(() => live.createCollection(name)))
            return;
        setModal(null);
        navigate("Services", name);
        notify(t("Collection created"));
    }
    async function deleteService(service: Service) {
        if (!await perform(() => live.deleteService(service.id)))
            return;
        setModal(null);
        notify(t("Service deleted"));
    }
    async function checkReal(id?: string) {
        if (await perform(() => id ? live.checkNow(id) : live.checkEnabled()))
            notify(id ? t("Check requested") : t("Enabled services submitted to the scheduler"));
    }
    async function pauseService(service: Service) {
        if (await perform(() => live.setMonitoring(service.id, !service.enabled)))
            notify(service.enabled ? t("Monitoring paused") : t("Monitoring resumed"));
    }
    async function configure(values: Partial<Pick<typeof store, 'alerts' | 'recovery' | 'threshold'>>) {
        await perform(() => live.configure(values));
    }
    const { preferences, save: savePreferences } = usePreferences();
    const light = preferences.theme === 'light';
    function toggleTheme() {
        if (!savePreferences({ ...preferences, theme: light ? 'dark' : 'light' }))
            notify(t("Could not save the theme in this browser"));
    }
    const [modal, setModal] = useState<'service' | 'collection' | 'settings' | 'delete' | 'manageCollection' | 'info' | null>(null), [editing, setEditing] = useState<Service>(), [selectedSnapshot, setSelected] = useState<Service>(), [toast, setToast] = useState(''), [menu, setMenu] = useState(false);
    const selected = selectedSnapshot ? (store.services.find(s => s.id === selectedSnapshot.id) ?? selectedSnapshot) : undefined;
    const [incidentFilter, setIncidentFilter] = useState("All");
    const notificationTracker = useRef(new NotificationTracker());
    const searchRef = useRef<HTMLInputElement>(null), timer = useRef<ReturnType<typeof setTimeout> | null>(null);
    function notify(message: string) { setToast(message); }
    useEffect(() => {
        if (!toast)
            return;
        const t = setTimeout(() => setToast(''), 4500);
        return () => clearTimeout(t);
    }, [toast]);
    useEffect(() => {
        function key(e: KeyboardEvent) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                searchRef.current?.focus();
            }
        }
        window.addEventListener('keydown', key);
        return () => {
            window.removeEventListener('keydown', key);
            if (timer.current)
                clearTimeout(timer.current);
        };
    }, []);
    useEffect(() => {
        if (!live.notifications)
            return;
        const incoming = notificationTracker.current.poll(live.notifications);
        if (incoming.length)
            notify(incoming.length === 1 ? t("New alert: ") + incoming[0].message : incoming.length + t(" new alerts. Check the alert inbox."));
    }, [false, live.notifications]);
    useEffect(() => {
        if (live.loading || live.error)
            return;
        if (reportService && !store.services.some(s => s.id === reportService))
            setReportService('');
        if (reportCollection && !store.collections.includes(reportCollection)) {
            setReportCollection('');
            setReportService('');
        }
    }, [false, live.loading, live.error, store.services, store.collections, reportService, reportCollection]);
    async function readAlert(id: string) { await perform(() => live.markRead(id)); }
    async function readAllAlerts() {
        if (await perform(() => live.markAllRead()))
            notify(t("Alerts marked as read"));
    }
    function navigate(next: string, group = '') { setPage(next); setCollection(group); setFilter("All"); setMenu(false); }
    const matching = store.services.filter(s => (!collection || s.collection === collection) && (!search || `${s.name} ${s.url} ${s.collection}`.toLowerCase().includes(search.toLowerCase())));
    const filtered = matching.filter(s => filter === "All" || s.status === filter);
    const visible = page === "Home" && !search ? filtered.slice(0, 5) : filtered;
    const reportServices = store.services.filter(s => (!reportService || s.id === reportService) && (!reportCollection || s.collection === reportCollection));
    const activeIncidents = store.incidents.filter(i => i.state !== "Resolved");
    const activeCount = (store.activeIncidentCount ?? activeIncidents.length);
    const counts = (status: string) => matching.filter(s => s.status === status).length;
    async function saveService(service: Service) {
        if (await perform(() => live.saveService(service, !!editing))) {
            setModal(null);
            notify(t('Service saved in PostgreSQL'));
        }
    }
    function exportReport() {
        if (analytics.data) {
            downloadStatistics(analytics.data);
            notify(t('Historical report exported'));
        }
    }
    const table = <section className="panel services-panel"><header className="panel-head"><h2>{collection || t("Your services")}</h2><div className="status-tabs">{[["All", "All"], ["Healthy", "Healthy"], ["Degraded", "Degraded"], ["Down", "Down"]].map(([value, label]) => <button key={value} className={filter === value ? 'selected' : ''} onClick={() => setFilter(value)} aria-pressed={filter === value}>{value !== "All" && <i className={'dot ' + statusClass(value as Status)}/>}<span>{t(String(label))}</span><b>{value === "All" ? matching.length : counts(value)}</b></button>)}</div>{page === "Home" && <button className="text-button" onClick={() => navigate("Services")}>{t("View all")}<ArrowRight size={14}/></button>}</header><div className="table-scroll"><table><thead><tr><th>{t("Service")}</th><th>{t("Status")}</th><th>{t("Last check")}</th><th>{t("Time")}</th><th>{t("Availability")}{' (' + range + ')'}</th><th><span className="sr-only">{t("Actions")}</span></th></tr></thead><tbody>{visible.map(s => <tr key={s.id}><td><button className="service-name" onClick={() => setSelected(s)}><ServiceIcon id={s.id}/><span><strong>{s.name}</strong><small>{s.url}</small></span></button></td><td><span className={'status ' + statusClass(s.status)}><i className="dot"/>{t(s.status)}</span>{<small className="check-error">{s.checking ? t("Checking\u2026") : s.enabled ? t("Monitoring enabled") : t("Paused")}</small>}</td><td>{<span className="muted">{s.lastCheckedAt ? new Date(s.lastCheckedAt).toLocaleTimeString(getLocale()) : t("No history")}</span>}</td><td>{s.latency === null ? '—' : s.latency + ' ms'}</td><td title={t("Successful checks / evaluated checks; empty periods excluded")}>{numberLabel(availabilityById.get(s.id), ' %')}</td><td><details className="row-menu"><summary aria-label={t("Actions for ") + s.name}><EllipsisVertical size={19}/></summary><div><button onClick={() => { setOperationError(''); setEditing(s); setModal('service'); }}><Pencil size={14}/>{t("Edit")}</button>{<><button disabled={live.pending || s.checking || !live.monitoring} onClick={() => void checkReal(s.id)}><Play size={14}/>{t("Check now")}</button><button disabled={live.pending || s.checking} onClick={() => void pauseService(s)}><Pause size={14}/>{s.enabled ? t("Pause") : t("Resume")}</button></>}<button className="error" onClick={() => { setOperationError(''); setEditing(s); setModal('delete'); }}><Trash2 size={14}/>{t("Delete")}</button></div></details></td></tr>)}</tbody></table></div>{!visible.length && <div className="empty"><Search size={28}/><h3>{t("No services")}{search ? t("matching your search") : ''}</h3><p>{t("Change the filters or add your first service.")}</p><button className="secondary" onClick={() => { setSearch(''); setFilter("All"); setOperationError(''); setEditing(undefined); setModal('service'); }}>{t("Add service")}</button></div>}<footer className="table-foot"><span><i className="dot healthy"/> {matching.length}{t("services in this view")}</span><span>{live.loading ? t("Loading\u2026") : live.error ? t("Offline") : t("Saved in PostgreSQL")}</span></footer></section>;
    const incidentList = <div className="incident-list">{store.incidents.filter(i => (incidentFilter === "All" || i.state === incidentFilter) && (page !== "Alerts" || (i.state === "Resolved" ? store.recovery : store.alerts))).slice(0, page === "Home" ? 3 : undefined).map(i => <button key={i.id} className="incident-item" onClick={() => { setSelected(store.services.find(s => s.id === i.serviceId)); }}><i className={'incident-dot ' + (i.state === "Investigating" ? 'danger' : i.state === "Monitoring" ? 'warning' : 'healthy')}/><span className="incident-text"><strong>{i.name}</strong><small>{localizeMessage(i.cause)}</small></span><span className={'badge ' + (i.state === "Investigating" ? 'danger' : i.state === "Monitoring" ? 'warning' : 'healthy')}>{t(i.state)}</span></button>)}{!store.incidents.filter(i => (incidentFilter === "All" || i.state === incidentFilter) && (page !== "Alerts" || (i.state === "Resolved" ? store.recovery : store.alerts))).length && <p className="empty">{t("No incidents match this filter.")}</p>}</div>;
    return <div className={light ? 'app light' : 'app'}><aside className={'sidebar ' + (menu ? 'open' : '')}><a className="brand" href="#inicio" onClick={e => { e.preventDefault(); navigate("Home"); }}><span className="logo"><span /></span><div><strong>API Sentinel</strong><small>Keep your APIs online</small></div></a><nav aria-label={t("Main navigation")}>{navigation.map(([name, Icon]) => <button key={name} className={page === name && !collection ? 'active' : ''} onClick={() => navigate(name)}><Icon size={21}/>{t(String(name))}{name === "Incidents" && activeCount > 0 && <span className="nav-count">{activeCount}</span>}{name === "Alerts" && true && live.unreadAlerts > 0 && <span className="nav-count" title={live.unreadAlerts + t(" unread alerts")}>{live.unreadAlerts > 99 ? '99+' : live.unreadAlerts}</span>}</button>)}</nav><div className="collection-title"><span>{t("Collections")}</span><button className="icon-button" aria-label={t("Create collection")} onClick={() => { setOperationError(''); setModal('collection'); }}><Plus size={16}/></button></div><div className="collections">{store.collections.map((c, i) => <button key={c} className={collection === c ? 'collection active' : 'collection'} onClick={() => navigate("Services", c)}><i style={{ background: ['#00cda0', '#4488ff', '#b758e4', '#7e94ad'][i % 4] }}/><span>{c}<small>{serviceCount(store.services.filter(s => s.collection === c).length)}</small></span></button>)}</div><button className={'profile profile-card cover-' + preferences.coverStyle} style={preferences.cover ? { backgroundImage: `linear-gradient(0deg,rgba(7,16,30,.92),rgba(7,16,30,.22)),url("${preferences.cover}")` } : undefined} onClick={() => setModal('settings')} title={preferences.bio || t("Personalize profile")}><span className="avatar" style={{ backgroundColor: preferences.color }}>{preferences.avatar ? <img src={preferences.avatar} alt=""/> : initials(preferences.name)}</span><span className="profile-copy"><strong>{preferences.name}</strong><small>{preferences.role || t("Workspace")}</small></span><Settings size={18}/></button></aside>{menu && <button className="sidebar-backdrop" onClick={() => setMenu(false)} aria-label={t("Close navigation")}/>}<main><header className="topbar"><button className="icon-button mobile-menu" aria-label={t("Open navigation")} onClick={() => setMenu(!menu)}><Menu /></button><label className="search"><Search size={21}/><input ref={searchRef} value={search} onChange={e => {
            setSearch(e.target.value);
            if (!["Home", "Services"].includes(page))
                navigate("Services");
        }} placeholder={t("Search services, endpoints or collections...")} aria-label={t("Search services")}/>{search ? <button className="icon-button" onClick={() => setSearch('')} aria-label={t("Clear search")}><X size={15}/></button> : <kbd>Ctrl K</kbd>}</label><button className="icon-button theme-button" aria-label={t("Switch theme")} onClick={() => toggleTheme()}><Sun size={21}/></button><div className="date"><strong>{new Intl.DateTimeFormat(getLocale(), { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date())}</strong><small>{t(t("Local workspace"))}</small></div><button className="avatar avatar-button" style={{ backgroundColor: preferences.color }} onClick={() => setModal('settings')} aria-label={t("Open settings")} title={preferences.name}>{preferences.avatar ? <img src={preferences.avatar} alt=""/> : initials(preferences.name)}</button></header><div className="demo-banner"><span><ShieldCheck size={15}/><b>{t("Persistent workspace")}</b><span>{(live.monitoring ? t("Backend monitoring is active") : t("Monitoring engine unavailable"))}</span></span><label className="language-control"><span>{t('Language')}</span><select aria-label={t('Language')} value={language} onChange={e => {
            if (!setLanguage(e.target.value as 'en' | 'es'))
                notify(t('Language is set for this session only.'));
        }}><option value="en">English</option><option value="es">Español</option></select></label></div>
 {live.loading && <div className="connection-state" role="status">{t("Loading services from PostgreSQL\u2026")}</div>}
 {live.error && <div className="connection-state error" role="alert"><span>{localizeMessage(live.error.message)}</span><button className="secondary" onClick={() => live.refresh()}>{t("Retry")}</button></div>}
 {operationError && !modal && <div className="connection-state error" role="alert">{t(String(operationError))}<button className="icon-button" aria-label={t("Dismiss error")} onClick={() => setOperationError('')}><X size={16}/></button></div>}
 {false && <p className="error" role="alert">{t("The browser cannot save changes. They will only be kept for this session.")}</p>}<header className="page-heading"><div><p className="eyebrow">{t("YOUR OBSERVABILITY WORKSPACE")}</p><h1>{page === "Home" ? "API Sentinel" : collection || t(page)}</h1>{page === "Home" ? <button className="app-info" onClick={() => setModal('info')}><Info size={14}/>{t("App information")}</button> : <p>{page === "Services" ? t("All your endpoints in one place.") : page === 'Checks' ? (t("Check availability, latency and real HTTP responses.")) : page === "Incidents" ? (t("Track detected incidents and service recoveries.")) : page === "Alerts" ? t("Choose when to receive notifications.") : page === "Reports" ? t("An overview of your service health.") : t("Connect your workflow.")}</p>}</div>{page === "Services" && collection && true && <button className="secondary" onClick={() => { setOperationError(''); setModal('manageCollection'); }}><Settings size={16}/>{t("Manage collection")}</button>}{["Home", "Services"].includes(page) && <button className="primary" onClick={() => { setEditing(undefined); setModal('service'); }}><Plus size={18}/>{t("Add service")}</button>}{page === "Reports" && <button className="primary" disabled={(!analytics.data || analytics.isPending || analytics.isFetching || !!analytics.error)} onClick={exportReport}><Download size={17}/>{t("Export report CSV")}</button>}</header>

 {page === "Reports" && true && <section className="panel report-scope"><label>{t("Report collection")}<select value={reportCollection} onChange={e => { setReportCollection(e.target.value); setReportService(''); }}><option value="">{t("All collections")}</option>{store.collections.map(c => <option key={c}>{c}</option>)}</select></label><label>{t("Report service")}<select value={reportService} onChange={e => setReportService(e.target.value)}><option value="">{t("All services")}</option>{store.services.filter(s => !reportCollection || s.collection === reportCollection).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label><RangeTabs range={range} onRange={setRange}/></section>}
 {analytics.error && ["Home", "Services", "Reports"].includes(page) && <div className="connection-state error" role="alert">{t("Could not refresh history:")}{localizeMessage(analytics.error.message)}</div>}
 {["Home", "Reports"].includes(page) && <div className="stats">{[{ icon: Box, value: page === "Reports" ? reportServices.length : store.services.length, label: t("Registered services"), note: (page === "Reports" ? reportServices : store.services).filter(s => s.enabled).length + t(" with monitoring enabled"), color: 'blue' }, { icon: Activity, value: analytics.isPending ? '…' : historical?.availability == null ? t("No data") : numberLabel(historical.availability, ' %'), label: t("Check-based availability"), note: analytics.isPending ? t("Loading period\u2026") : range + ' · ' + (historical?.evaluated_checks ?? 0) + t(" evaluated checks"), color: 'healthy' }, { icon: Clock3, value: analytics.isPending ? '…' : numberLabel(historical?.latency_avg, ' ms'), label: t("Average response time"), note: range + t(" \u00B7 samples in this period"), color: 'blue' }, { icon: Bell, value: page === "Reports" ? (historical?.active_incidents ?? '—') : activeCount, label: t("Active incidents"), note: page === "Reports" ? t("Active in this selection") : t("Active now"), color: 'danger' }].map(({ icon: Icon, value, label, note, color }) => <section className="panel stat" key={label}><span className={'stat-icon ' + color}><Icon size={27}/></span><div><strong>{value}</strong><p>{t(String(label))}</p><small className={color}>{color === 'danger' ? <ArrowRight size={13}/> : <ArrowDown size={13}/>} {t(String(note))}</small></div></section>)}</div>}
 {page === "Home" && <><div className="dashboard-grid">{table}<aside className="context">{<ActivityMap onService={id => setSelected(store.services.find(s => s.id === id))}/>}<section className="panel recent"><header className="panel-head"><h2>{t("Recent incidents")}</h2><button className="text-button" onClick={() => navigate("Incidents")}>{t("View all")}<ArrowRight size={13}/></button></header>{incidentList}</section></aside></div>{<HistoricalChart query={analytics} range={range} onRange={setRange} light={light}/>}</>}
 {page === "Services" && true && <div className="service-period"><span>{t("Check-based availability \u00B7 period")}</span><RangeTabs range={range} onRange={setRange}/></div>}{page === "Services" && table}
 {page === 'Checks' && true && <ChecksView services={store.services} monitoring={live.monitoring} pending={live.pending} onCheck={id => void checkReal(id)}/>}
 {page === 'Checks' && false && <>{false}<section className="panel"><header className="panel-head"><h2>{t("Check history")}</h2>{false}</header><div className="table-scroll"><table><thead><tr><th>{t("Service")}</th><th>{t("Date and time")}</th><th>{t("Result")}</th><th>{t("Time")}</th></tr></thead><tbody>{store.checks.map(c => <tr key={c.id}><td>{c.name}</td><td>{new Date(c.time).toLocaleString(getLocale())}</td><td><span className={'status ' + statusClass(c.status)}><i className="dot"/>{c.code ? 'HTTP ' + c.code : 'Timeout'}</span></td><td>{c.latency} ms</td></tr>)}</tbody></table></div>{!store.checks.length && <div className="empty"><CheckCheck size={30}/><h3>{t("No checks yet")}</h3><p>{t("The check engine will be implemented in Phase 3.")}</p></div>}</section></>}
 {page === "Incidents" && <section className="panel"><header className="panel-head"><h2>{t("Incident log")}</h2><select aria-label={t("Filter incidents")} value={incidentFilter} onChange={e => setIncidentFilter(e.target.value)}>{["All", "Investigating", "Monitoring", "Resolved"].map(s => <option key={s} value={s}>{t(String(s))}</option>)}</select></header>{incidentList}<p className="panel-note">{t("A check outside the configured conditions opens an incident. Recovery resolves it automatically.")}</p></section>}
 {page === "Alerts" && <><section className="panel settings-panel"><h2>{t("Alert preferences")}</h2><p className="muted">{t("Preferences are saved in PostgreSQL. Alerts are generated for incidents, escalation and recovery.")}</p><label className="switch-row"><span><strong>{t("Failure alerts")}</strong><small>{t("Receive alerts when a service fails, degrades or escalates.")}</small></span><input type="checkbox" checked={store.alerts} disabled={live.pending} onChange={e => void configure({ alerts: e.target.checked })}/></label><label className="switch-row"><span><strong>{t("Recovery alerts")}</strong><small>{t("Receive an alert when a service recovers.")}</small></span><input type="checkbox" checked={store.recovery} disabled={live.pending} onChange={e => void configure({ recovery: e.target.checked })}/></label><label className="threshold">{t("Latency threshold (ms)")}<input type="number" min={1} max={60000} defaultValue={store.threshold} key={String(false) + store.threshold} onBlur={e => {
                const n = Number(e.target.value);
                if (n >= 1 && n <= 60000)
                    void configure({ threshold: n });
                else
                    e.target.value = String(store.threshold);
            }}/><small>{t("Saved when the field loses focus. Applies to the next check; exceeding this threshold marks the service as degraded.")}</small></label><h3>{t("Notification rules")}</h3>{<p className="muted">{t("Alerts are sent once per incident, on escalation from degraded to down, and on recovery. Disabling alerts does not stop checks or incident recording.")}</p>}</section>{<AlertsInbox unread={live.unreadAlerts} pending={live.pending} onRead={id => void readAlert(id)} onReadAll={() => void readAllAlerts()}/>}</>}
 {page === "Reports" && <>{<HistoricalChart query={analytics} range={range} onRange={setRange} light={light}/>}{<ReportDetails data={analytics.data}/>}<section className="panel report-note"><FileChartColumn size={28}/><div><h2>{t("Report notes")}</h2><p>{t("Percentages use evaluated checks. Unclassified checks and intervals without samples are not counted as successes. Percentiles use continuous interpolation over measured latency; chart gaps remain empty.")}</p></div></section></>}
 {page === "Integrations" && <section className="integration-grid">{[["Email", "Receive notifications in your inbox.", Mail], ['Discord', "Share incidents with your team.", Unplug], ['Webhooks', "Connect your own tools.", Activity]].map(([name, description, Icon]) => { const I = Icon as typeof Mail; return <article className="panel integration-card" key={String(name)}><I size={30}/><h2>{t(String(name))}</h2><p>{t(String(description))}</p><span className="badge unknown">{t("Planned integration")}</span></article>; })}</section>}
 <footer className="app-footer"><span><span className="footer-mark">◉</span> API Sentinel <span className="muted">/</span>{t(t("Local workspace"))}</span><span>{t("API Sentinel 1.1 \u00B7 Local workspace")}</span></footer></main>
 {modal === 'service' && <Modal title={editing ? t("Edit service") : t("Add service")} onClose={() => setModal(null)}><ServiceForm demo={false} pending={live.pending} service={editing} collections={store.collections} onSave={saveService} onCancel={() => setModal(null)}/>{operationError && <p className="modal-error error" role="alert">{t(String(operationError))}</p>}</Modal>}
 {modal === 'collection' && <Modal title={t("New collection")} onClose={() => setModal(null)}><form className="form" onSubmit={e => {
                e.preventDefault();
                const name = String(new FormData(e.currentTarget).get('name')).trim();
                if (!name || store.collections.some(c => c.toLowerCase() === name.toLowerCase())) {
                    notify(t("Use a different collection name"));
                    return;
                }
                void createCollection(name);
            }}><label>{t("Name")}<input name="name" required maxLength={50} autoFocus placeholder={t("e.g. Infrastructure")}/></label><footer className="form-actions"><button type="button" className="secondary" onClick={() => setModal(null)}>{t("Cancel")}</button><button className="primary" disabled={live.pending}>{live.pending ? t("Saving\u2026") : t("Create collection")}</button></footer>{operationError && <p className="error" role="alert">{t(String(operationError))}</p>}</form></Modal>}
 {modal === 'delete' && editing && <Modal title={t("Delete service")} onClose={() => setModal(null)}><div className="form"><p>{t("Delete")}<strong>{editing.name}</strong>{t("and its associated history and incidents?")}</p><footer className="form-actions"><button className="secondary" onClick={() => setModal(null)}>{t("Cancel")}</button><button className="danger-button" disabled={live.pending} onClick={() => void deleteService(editing)}>{t("Delete service")}</button></footer>{operationError && <p className="error" role="alert">{t(String(operationError))}</p>}</div></Modal>}

 {modal === 'manageCollection' && <Modal title={t("Manage collection")} onClose={() => setModal(null)}><form className="form" onSubmit={async (e) => {
                e.preventDefault();
                const name = String(new FormData(e.currentTarget).get('name')).trim();
                const id = live.collectionId(collection);
                if (id && await perform(() => live.renameCollection(id, name))) {
                    setModal(null);
                    navigate("Services", name);
                    notify(t("Collection updated"));
                }
            }}><label>{t("Name")}<input name="name" required maxLength={50} defaultValue={collection}/></label><footer className="form-actions"><button type="button" className="secondary" onClick={() => setModal(null)}>{t("Cancel")}</button><button disabled={live.pending} className="primary">{t("Save name")}</button></footer><details className="reset"><summary>{t("Delete collection")}</summary><p>{t("Move or delete its services first. This action deletes the collection from PostgreSQL.")}</p><button type="button" disabled={live.pending} className="danger-button" onClick={async () => {
                const id = live.collectionId(collection);
                if (id && await perform(() => live.deleteCollection(id))) {
                    setModal(null);
                    navigate("Services");
                    notify(t("Collection deleted"));
                }
            }}>{t("Confirm deletion")}</button></details>{operationError && <p className="error" role="alert">{t(String(operationError))}</p>}</form></Modal>}
 {modal === 'info' && <Modal title={t("About API Sentinel")} onClose={() => setModal(null)}><div className="form app-about"><span className="about-mark"><ShieldCheck size={30}/></span><h3>{t("Stay online, always")}</h3><p>{t("API Sentinel brings your HTTP service and API availability into one local workspace.")}</p><ul><li>{t("Configure endpoints, methods and expected HTTP status codes.")}</li><li>{t("Review latency and check history.")}</li><li>{t("Track incidents and automatic recovery.")}</li><li>{t("Organize services into collections and personalize your profile.")}</li></ul><p className="muted">{t("Scheduled checks run while the backend is active, even when this window is closed. You can pause each service.")}</p><p className="muted">{t("Version 1.1 \u00B7 Period charts, check-based availability, percentiles and alerts with read status. Your operational data is stored in PostgreSQL.")}</p><footer className="form-actions"><button className="primary" onClick={() => setModal(null)}>{t("Got it")}</button></footer></div></Modal>}
 {modal === 'settings' && <Modal title={t("Your profile and preferences")} className="profile-dialog" onClose={() => setModal(null)}><ProfileSettings preferences={preferences} onCancel={() => setModal(null)} onSave={next => {
                if (!savePreferences(next))
                    return false;
                setModal(null);
                notify(t("Profile and preferences saved"));
                return true;
            }}/></Modal>}
 {selected && <Modal title={selected.name} onClose={() => setSelected(undefined)}><div className="form"><span className={'status ' + statusClass(selected.status)}><i className="dot"/>{selected.checking ? t("Checking\u2026") : t(selected.status)}</span><dl className="detail-grid"><dt>Endpoint</dt><dd>{selected.url}</dd><dt>{t("Method")}</dt><dd>{selected.method}</dd><dt>{t("Collection")}</dt><dd>{selected.collection}</dd><dt>{t("Interval / timeout")}</dt><dd>{selected.interval}s / {selected.timeout}s</dd>{<><dt>{t("Monitoring")}</dt><dd>{selected.enabled ? t("Active") : t("Paused")}</dd><dt>{t("Expected HTTP status")}</dt><dd>{selected.expectedMin}–{selected.expectedMax}</dd></>}{selected.createdAt && <><dt>{t("Created")}</dt><dd>{new Date(selected.createdAt).toLocaleString(getLocale())}</dd><dt>{t("Last check")}</dt><dd>{selected.lastCheckedAt ? new Date(selected.lastCheckedAt).toLocaleString(getLocale()) : t("Not checked")}</dd></>}</dl><p className="muted">{t("Real checks run by the backend. Pausing stops scheduled checks, but still allows manual checks.")}</p>{store.incidents.filter(i => i.serviceId === selected.id).map(i => <label key={i.id}>{t("Incident status \u00B7")}{new Date(i.started).toLocaleString(getLocale())}<small>{localizeMessage(i.cause)}{i.duration !== undefined ? t(" \u00B7 Duration: ") + Math.floor(i.duration / 60) + ' min ' + (i.duration % 60) + ' s' : ''}</small><select value={i.state} disabled={(live.pending || i.state === "Resolved")} onChange={async (e) => {
                    const value = e.target.value;
                    if (await perform(() => live.setIncident(i.id, value)))
                        notify(t("Incident status updated"));
                }}>{["Investigating", "Monitoring", "Resolved"].map(s => <option key={s} value={s}>{t(String(s))}</option>)}</select></label>)}<footer className="form-actions"><button className="secondary" onClick={() => { setEditing(selected); setSelected(undefined); setModal('service'); }}><Pencil size={15}/>{t("Edit service")}</button>{<button className="primary" disabled={live.pending || selected.checking || !live.monitoring} onClick={() => void checkReal(selected.id)}><Play size={15}/>{selected.checking ? t("Checking\u2026") : t("Check now")}</button>}</footer>{operationError && <p className="error" role="alert">{t(String(operationError))}</p>}</div></Modal>}
 {toast && <div className="toast" role="status"><ShieldCheck size={18}/>{localizeMessage(toast)}<button className="icon-button" aria-label={t("Dismiss notification")} onClick={() => setToast('')}><X size={15}/></button></div>}
 </div>;
}
