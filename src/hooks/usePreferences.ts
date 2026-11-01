import { useState } from 'react';
export type Preferences = {
    name: string;
    role: string;
    bio: string;
    avatar: string;
    avatarSource: string;
    avatarZoom: number;
    avatarX: number;
    avatarY: number;
    cover: string;
    coverStyle: string;
    color: string;
    theme: 'dark' | 'light';
};
export const defaultPreferences: Preferences = { name: "Local workspace", role: "Local profile", bio: '', avatar: '', avatarSource: '', avatarZoom: 1, avatarX: 0, avatarY: 0, cover: '', coverStyle: 'ocean', color: '#3879e8', theme: 'dark' };
const KEY = 'api-sentinel-preferences-v1';
export function initials(name: string) { return name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('').toUpperCase() || 'AS'; }
export function usePreferences() {
    const [preferences, setPreferences] = useState<Preferences>(() => { try {
        const saved = JSON.parse(localStorage.getItem(KEY) || 'null');
        if(saved?.name==='Espacio local'&&saved?.role==='Perfil de demostración'){saved.name='Local workspace';saved.role='Local profile';}return saved ? { ...defaultPreferences, ...saved } : defaultPreferences;
    }
    catch {
        return defaultPreferences;
    } });
    function save(next: Preferences) { try {
        localStorage.setItem(KEY, JSON.stringify(next));
        setPreferences(next);
        return true;
    }
    catch {
        return false;
    } }
    return { preferences, save };
}
