import { AvatarEditor } from './AvatarEditor';
import type { AvatarAdjustment } from '../lib/avatar';
import { t } from '../lib/i18n';
import { useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { ImagePlus, UserRound, Upload, Trash2 } from 'lucide-react';
import { initials, type Preferences } from '../hooks/usePreferences';
type Props = {
    preferences: Preferences;
    onSave: (next: Preferences) => boolean;
    onCancel: () => void;
};
const covers = [['ocean', "Ocean"], ['slate', "Slate"], ['sunset', "Sunset"], ['forest', "Forest"]] as const;
async function readImage(file: File, kind: 'avatar' | 'cover'): Promise<string> {
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type))
        throw new Error(t("Use a JPG, PNG or WebP image."));
    if (file.size > 5 * 1024 * 1024)
        throw new Error(t("The image must be smaller than 5 MB."));
    const url = URL.createObjectURL(file);
    try {
        const image = new Image();
        image.src = url;
        await image.decode();
        const canvas = document.createElement('canvas');
        const sourceScale = Math.min(1, 1024 / Math.max(image.naturalWidth, image.naturalHeight));
        canvas.width = kind === 'avatar' ? Math.max(1, Math.round(image.naturalWidth * sourceScale)) : 1000;
        canvas.height = kind === 'avatar' ? Math.max(1, Math.round(image.naturalHeight * sourceScale)) : 350;
        const ctx = canvas.getContext('2d');
        if (!ctx)
            throw new Error(t("Could not process the image."));
        if (kind === 'avatar') {
            ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
            return canvas.toDataURL('image/webp', 0.9);
        }
        const scale = Math.max(canvas.width / image.naturalWidth, canvas.height / image.naturalHeight);
        ctx.drawImage(image, (canvas.width - image.naturalWidth * scale) / 2, (canvas.height - image.naturalHeight * scale) / 2, image.naturalWidth * scale, image.naturalHeight * scale);
        return canvas.toDataURL('image/jpeg', 0.82);
    }
    catch (error) {
        if (error instanceof Error && error.message.includes(t("process")))
            throw error;
        throw new Error(t("Could not read the image. Try a different file."));
    }
    finally {
        URL.revokeObjectURL(url);
    }
}
export function ProfileSettings({ preferences, onSave, onCancel }: Props) {
    const [draft, setDraft] = useState({ ...preferences }), [tab, setTab] = useState("Profile"), [error, setError] = useState(''), [uploading, setUploading] = useState(false);
    const [avatarEditor, setAvatarEditor] = useState<{source: string; initial?: AvatarAdjustment} | null>(null);
    const avatarInput = useRef<HTMLInputElement>(null), coverInput = useRef<HTMLInputElement>(null);
    const change = <K extends keyof Preferences>(key: K, value: Preferences[K]) => setDraft(p => ({ ...p, [key]: value }));
    async function upload(e: ChangeEvent<HTMLInputElement>, kind: 'avatar' | 'cover') {
        const file = e.target.files?.[0];
        e.target.value = '';
        if (!file)
            return;
        setUploading(true);
        setError('');
        try {
            const source = await readImage(file, kind);
            if (kind === 'avatar') setAvatarEditor({source});
            else change('cover', source);
        }
        catch (error) {
            setError(error instanceof Error ? error.message : t("Could not upload the image."));
        }
        finally {
            setUploading(false);
        }
    }
    function submit(e: FormEvent) {
        e.preventDefault();
        if (avatarEditor) return;
        if (!draft.name.trim()) {
            setError(t("Enter a profile name."));
            return;
        }
        if (!onSave({ ...draft, name: draft.name.trim(), role: draft.role.trim(), bio: draft.bio.trim() }))
            setError(t("Not enough storage to save your profile. Remove an image or use a smaller one."));
    }
    return <form className="profile-settings" onSubmit={submit}>
 <div className="settings-tabs" aria-label={t("Settings sections")}>{["Profile", "Appearance", "Local data"].map(name => <button type="button" key={name} aria-pressed={tab === name} className={tab === name ? 'selected' : ''} onClick={() => setTab(name)}>{t(String(name))}</button>)}</div>
 {tab === "Profile" && <div className="settings-section">
  <div className={'profile-preview cover-' + draft.coverStyle} style={draft.cover ? { backgroundImage: `url("${draft.cover}")` } : undefined}>
   <span className="preview-label">{t("PREVIEW")}</span><div className="preview-identity"><span className="avatar preview-avatar" style={{ backgroundColor: draft.color }}>{draft.avatar ? <img src={draft.avatar} alt={t("Avatar preview")}/> : initials(draft.name)}</span><div><strong>{draft.name || t("Your name")}</strong><span>{draft.role || t("Your workspace")}</span></div></div>
  </div>
  <div className="media-actions"><button type="button" className="secondary" disabled={uploading} onClick={() => avatarInput.current?.click()}><UserRound size={15}/>{t("Change avatar")}</button><button type="button" className="secondary" disabled={uploading} onClick={() => coverInput.current?.click()}><ImagePlus size={15}/>{t("Upload cover")}</button></div>
  {draft.avatar && !avatarEditor && <button type="button" className="text-button avatar-adjust-button" onClick={() => setAvatarEditor({source: draft.avatarSource || draft.avatar, initial: draft.avatarSource ? {zoom:draft.avatarZoom,x:draft.avatarX,y:draft.avatarY} : undefined})}>{t('Adjust avatar')}</button>}
  {avatarEditor && <AvatarEditor source={avatarEditor.source} initial={avatarEditor.initial} color={draft.color} onCancel={() => setAvatarEditor(null)} onApply={(avatar,source,adjustment) => {setDraft(previous => ({...previous,avatar,avatarSource:source,avatarZoom:adjustment.zoom,avatarX:adjustment.x,avatarY:adjustment.y}));setAvatarEditor(null);}}/>}
  <input className="file-input" ref={avatarInput} type="file" accept="image/jpeg,image/png,image/webp" aria-label={t("Avatar image")} onChange={e => void upload(e, 'avatar')}/>
  <input className="file-input" ref={coverInput} type="file" accept="image/jpeg,image/png,image/webp" aria-label={t("Cover image")} onChange={e => void upload(e, 'cover')}/>
  <p className="help-text">{t("JPG, PNG or WebP · up to 5 MB. Choose your avatar zoom and position before saving. Images stay in this browser.")}</p>
  {(draft.avatar || draft.cover) && <div className="media-remove">{draft.avatar && <button type="button" className="text-button" onClick={() => {setAvatarEditor(null);setDraft(previous => ({...previous,avatar:'',avatarSource:'',avatarZoom:1,avatarX:0,avatarY:0}));}}><Trash2 size={13}/>{t("Remove avatar")}</button>}{draft.cover && <button type="button" className="text-button" onClick={() => change('cover', '')}><Trash2 size={13}/>{t("Remove cover")}</button>}</div>}
  <div className="form-grid"><label>{t("Profile name")}<input value={draft.name} maxLength={50} onChange={e => change('name', e.target.value)} placeholder={t("Your name")} required/></label><label>{t("Role or short description")}<input value={draft.role} maxLength={60} onChange={e => change('role', e.target.value)} placeholder={t("e.g. Backend developer")}/></label></div>
  <label>{t("About you")}<textarea value={draft.bio} maxLength={240} rows={3} onChange={e => change('bio', e.target.value)} placeholder={t("A short description of your work\u2026")}/><small>{draft.bio.length}/240</small></label>
  <fieldset><legend>{t("Profile cover")}</legend><div className="cover-options">{covers.map(([value, label]) => <button type="button" className={'cover-option cover-' + value + (draft.coverStyle === value && !draft.cover ? ' selected' : '')} aria-pressed={draft.coverStyle === value && !draft.cover} key={value} onClick={() => setDraft(p => ({ ...p, coverStyle: value, cover: '' }))}>{t(String(label))}</button>)}</div></fieldset>
  <fieldset><legend>{t("Profile color")}</legend><div className="color-options">{['#3879e8', '#7254bd', '#ad405d', '#16785e', '#b06724'].map(color => <button type="button" key={color} style={{ background: color }} aria-label={'Color ' + color} aria-pressed={draft.color === color} className={draft.color === color ? 'selected' : ''} onClick={() => change('color', color)}/>)}</div></fieldset>
 </div>}
 {tab === "Appearance" && <div className="settings-section"><h3>{t("Application theme")}</h3><p className="help-text">{t("Saved when you close and reopen the browser.")}</p><div className="theme-options">{[['dark', "Dark", "Charcoal surfaces and light text."], ['light', "Light", "Light surfaces and high-contrast text."]].map(([value, name, description]) => <button type="button" key={value} className={draft.theme === value ? 'selected' : ''} aria-pressed={draft.theme === value} onClick={() => change('theme', value as Preferences['theme'])}><span className={'theme-sample ' + value}/><strong>{t(String(name))}</strong><small>{t(String(description))}</small></button>)}</div><p className="help-text">{t("Navigation is on the right. On mobile, use the menu button.")}</p></div>}
 {tab === "Local data" && <div className="settings-section"><h3>{t("Your workspace, in this browser")}</h3><p className="help-text">{t("Your profile and images are saved in this browser. There is no account or cross-device sync.")}</p></div>}
 {uploading && <p className="upload-status" role="status"><Upload size={15}/>{t("Processing image\u2026")}</p>}
 {error && <p className="profile-error error" role="alert">{t(String(error))}</p>}
 <footer className="form-actions settings-actions"><button type="button" className="secondary" onClick={onCancel}>{t("Cancel")}</button><button type="submit" disabled={uploading || !!avatarEditor} className="primary">{t("Save changes")}</button></footer>
 </form>;
}
