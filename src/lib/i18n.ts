import { spanish } from './translations';
export type Language = 'en' | 'es';
const KEY = 'api-sentinel-language-v1';
const listeners = new Set<() => void>();
let language: Language = 'en';
try { language = globalThis.localStorage?.getItem(KEY) === 'es' ? 'es' : 'en'; } catch { /* Private browsing may disable storage. */ }
const english = Object.fromEntries(Object.entries(spanish).map(([en, es]) => [es, en]));
export function getLanguage(): Language { return language; }
export function getLocale(): string { return language === 'es' ? 'es-MX' : 'en-US'; }
export function subscribeLanguage(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; }
export function setLanguage(next: Language): boolean {
  if (next !== 'en' && next !== 'es') return false;
  language = next;
  let stored = true;
  try { globalThis.localStorage?.setItem(KEY, next); } catch { stored = false; }
  for (const listener of listeners) listener();
  return stored;
}
export function t(text: string, values: Record<string, string | number> = {}): string {
  const clean = text.trim();
  const leading = text.slice(0, text.indexOf(clean));
  const trailing = text.slice(text.indexOf(clean) + clean.length);
  const source = english[clean] ?? clean;
  const translated = language === 'es' ? spanish[source] ?? source : source;
  return leading + translated.replace(/\{(\w+)\}/g, (match, key: string) => values[key] === undefined ? match : String(values[key])) + trailing;
}
// Only system messages are localized. Names, URLs and user-authored profile text remain untouched.
export function localizeMessage(text: string): string {
  const direct = t(text);
  if (direct !== text || english[text] || spanish[text]) return direct;
  const http = text.match(/^HTTP (\d+) (?:fuera del rango esperado|outside the expected range) (.+)$/);
  if (http) return t('HTTP {code} outside the expected range {range}', {code: http[1], range: http[2]});
  const timeout = text.match(/^(?:Se agotó el tiempo de espera|Request timed out) \((.+)\)\.$/);
  if (timeout) return t('Request timed out ({duration}).', {duration: timeout[1]});
  const latency = text.match(/^(?:Latencia|Latency) (.+) ms (?:mayor al umbral de|exceeds the threshold of) (.+) ms\.$/);
  if (latency) return t('Latency {latency} ms exceeds the threshold of {threshold} ms.', {latency: latency[1], threshold: latency[2]});
  const recovery = text.match(/^(.*) (?:volvió a responder dentro de las condiciones configuradas\.|is responding within the configured conditions again\.)$/);
  if (recovery) return t('{service} is responding within the configured conditions again.', {service: recovery[1]});
  const split = text.indexOf(': ');
  if (split >= 0) { const tail = localizeMessage(text.slice(split + 2)); return text.slice(0, split + 2) + tail; }
  return text;
}

export function serviceCount(count: number): string { return t(count === 1 ? '{count} service' : '{count} services', {count}); }
