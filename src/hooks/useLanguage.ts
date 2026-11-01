import { useEffect, useSyncExternalStore } from 'react';
import { getLanguage, setLanguage, subscribeLanguage, t } from '../lib/i18n';
export function useLanguage() {
    const language = useSyncExternalStore(subscribeLanguage, getLanguage, () => 'en' as const);
    useEffect(() => {
        document.documentElement.lang = language;
        document.title = 'API Sentinel · ' + t('Service monitoring');
        function onStorage(event: StorageEvent) {
            if (event.key === 'api-sentinel-language-v1')
                setLanguage(event.newValue === 'es' ? 'es' : 'en');
        }
        window.addEventListener('storage', onStorage);
        return () => window.removeEventListener('storage', onStorage);
    }, [language]);
    return { language, setLanguage };
}
