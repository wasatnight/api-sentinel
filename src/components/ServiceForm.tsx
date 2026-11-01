import { t } from '../lib/i18n';
import { useState, type FormEvent } from 'react';
import type { Service } from '../types';
export function ServiceForm({ service, collections, onSave, onCancel, demo = true, pending = false }: {
    service?: Service;
    collections: string[];
    onSave: (s: Service) => void;
    onCancel: () => void;
    demo?: boolean;
    pending?: boolean;
}) {
    const [error, setError] = useState('');
    function submit(e: FormEvent<HTMLFormElement>) {
        e.preventDefault();
        const data = new FormData(e.currentTarget);
        const url = String(data.get('url')).trim();
        try {
            const parsed = new URL(url);
            if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password)
                throw Error();
        }
        catch {
            setError(t("Enter a valid HTTP/HTTPS URL without credentials."));
            return;
        }
        const expectedMin = Number(data.get('expectedMin') ?? 200), expectedMax = Number(data.get('expectedMax') ?? 299);
        if (expectedMax < expectedMin) {
            setError(t("The maximum HTTP status code must be greater than or equal to the minimum."));
            return;
        }
        onSave({ id: service?.id ?? crypto.randomUUID(), name: String(data.get('name')).trim(), url, method: String(data.get('method')), interval: Number(data.get('interval')), timeout: Number(data.get('timeout')), collection: String(data.get('collection')), status: service?.status ?? "Not checked", latency: service?.latency ?? null, uptime: service?.uptime ?? null, enabled: demo ? true : data.get('enabled') === 'on', expectedMin, expectedMax });
    }
    return <form onSubmit={submit} className="form">
 <p className="muted">{demo ? t("Demo configuration. No requests will be sent to this URL.") : t("The backend sends real requests to this endpoint while monitoring is enabled, even when this window is closed.")}</p>
 {!collections.length && <p className="muted">{t("Create a collection in the sidebar before saving a service.")}</p>}
 <label>{t("Service name")}<input name="name" defaultValue={service?.name} required maxLength={80} autoFocus placeholder={t("My service")}/></label>
 <label>{t("Endpoint URL")}<input maxLength={2048} name="url" defaultValue={service?.url} required placeholder="https://api.example.com/health"/></label>
 <div className="form-grid">
 <label>{t("HTTP method")}<select name="method" defaultValue={service?.method ?? 'GET'}>{['GET', 'HEAD'].map(m => <option key={m}>{m}</option>)}</select></label>
 <label>{t("Collection")}<select required name="collection" defaultValue={service?.collection ?? collections[0]}>{collections.map(c => <option key={c}>{c}</option>)}</select></label>
 <label>{t("Interval (seconds)")}<input name="interval" type="number" min={10} max={86400} defaultValue={service?.interval ?? 60} required/></label>
 <label>{t("Total timeout (seconds)")}<input name="timeout" type="number" min={1} max={60} defaultValue={service?.timeout ?? 10} required/></label>
 {!demo && <><label>{t("Minimum HTTP status code")}<input name="expectedMin" type="number" min={100} max={599} defaultValue={service?.expectedMin ?? 200} required/></label><label>{t("Maximum HTTP status code")}<input name="expectedMax" type="number" min={100} max={599} defaultValue={service?.expectedMax ?? 299} required/></label></>}
 </div>
 {!demo && <><label className="monitor-toggle"><input name="enabled" type="checkbox" defaultChecked={service?.enabled ?? true}/><span>{t("Enable scheduled checks")}</span></label><p className="help-text">{t("Use GET or HEAD with a health endpoint you own or are authorized to monitor.")}</p></>}
 {error && <p role="alert" className="error">{t(String(error))}</p>}
 <footer className="form-actions"><button type="button" className="secondary" onClick={onCancel}>{t("Cancel")}</button><button className="primary" type="submit" disabled={pending || !collections.length}>{pending ? t("Saving\u2026") : t("Save service")}</button></footer></form>;
}
