import { useEffect, useRef, useState, type CSSProperties, type PointerEvent } from 'react';
import { Move, RotateCcw, ZoomIn } from 'lucide-react';
import { avatarFillZoom, avatarFrame, normalizeAvatarAdjustment, type AvatarAdjustment } from '../lib/avatar';
import { t } from '../lib/i18n';

type Props = {
  source: string;
  initial?: AvatarAdjustment;
  color: string;
  onApply: (avatar: string, source: string, adjustment: AvatarAdjustment) => void;
  onCancel: () => void;
};
export function AvatarEditor({source, initial, color, onApply, onCancel}: Props) {
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [adjustment, setAdjustment] = useState(() => normalizeAvatarAdjustment(initial ?? {}));
  const [error, setError] = useState('');
  const [applying, setApplying] = useState(false);
  const editor = useRef<HTMLElement>(null);
  useEffect(() => { editor.current?.scrollIntoView({block:'start'}); }, []);
  const drag = useRef<{id: number; clientX: number; clientY: number; x: number; y: number} | null>(null);
  useEffect(() => {
    let active = true;
    setImage(null); setError(''); setApplying(false);
    const next = new Image();
    next.onload = () => { if (!active) return; setImage(next); setAdjustment(normalizeAvatarAdjustment(initial ?? {zoom: avatarFillZoom(next.naturalWidth, next.naturalHeight)})); };
    next.onerror = () => { if (active) setError(t('Could not read the image. Try a different file.')); };
    next.src = source;
    return () => { active = false; next.onload = null; next.onerror = null; };
  }, [source, initial]);
  const frame = image ? avatarFrame(image.naturalWidth, image.naturalHeight, adjustment) : null;
  const position: CSSProperties = frame ? {left: frame.x / 256 * 100 + '%', top: frame.y / 256 * 100 + '%', width: frame.width / 256 * 100 + '%', height: frame.height / 256 * 100 + '%'} : {};
  function update(values: Partial<AvatarAdjustment>) { setAdjustment(previous => normalizeAvatarAdjustment({...previous, ...values})); }
  function pointerDown(event: PointerEvent<HTMLDivElement>) {
    if (!image || event.button !== 0) return;
    event.preventDefault();
    drag.current = {id: event.pointerId, clientX: event.clientX, clientY: event.clientY, x: adjustment.x, y: adjustment.y};
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function pointerMove(event: PointerEvent<HTMLDivElement>) {
    const start = drag.current;
    if (!start || !frame || start.id !== event.pointerId) return;
    const size = event.currentTarget.getBoundingClientRect().width;
    update({x: start.x + (event.clientX - start.clientX) / (frame.panX / 256 * size), y: start.y + (event.clientY - start.clientY) / (frame.panY / 256 * size)});
  }
  function apply() {
    if (!image || applying) return;
    setApplying(true);
    try {
      const canvas = document.createElement('canvas'); canvas.width = 256; canvas.height = 256;
      const context = canvas.getContext('2d');
      if (!context) throw new Error(t('Could not process the image.'));
      const crop = avatarFrame(image.naturalWidth, image.naturalHeight, adjustment);
      context.drawImage(image, crop.x, crop.y, crop.width, crop.height);
      onApply(canvas.toDataURL('image/png'), source, adjustment);
    } catch { setError(t('Could not process the image.')); setApplying(false); }
  }
  return <section ref={editor} className="avatar-editor" aria-label={t('Adjust avatar')}>
    <header><h3><ZoomIn size={17}/>{t('Adjust avatar')}</h3><p id="avatar-editor-help">{t('Zoom in or out, then drag the image or use the position sliders.')}</p></header>
    <div className="avatar-editor-layout"><div className="avatar-editor-preview">
      <div className="avatar-editor-stage" style={{backgroundColor:color}} aria-label={t('Avatar crop preview')} aria-describedby="avatar-editor-help"
        onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={() => {drag.current = null;}} onPointerCancel={() => {drag.current = null;}} onLostPointerCapture={() => {drag.current = null;}}>
        {image ? <img src={source} alt="" draggable={false} style={position}/> : <span>{t('Loading image…')}</span>}
      </div><span className="avatar-drag-hint"><Move size={14}/>{t('Drag to reposition')}</span>
    </div>
    <div className="avatar-editor-controls">
      <label><span>{t('Zoom')}<output>{Math.round(adjustment.zoom * 100)}%</output></span><input aria-label={t('Avatar zoom')} type="range" min="0.5" max="8" step="0.01" value={adjustment.zoom} disabled={!image} onChange={event => update({zoom: Number(event.target.value)})}/></label>
      <label><span>{t('Horizontal position')}<output>{Math.round(adjustment.x * 100)}%</output></span><input aria-label={t('Avatar horizontal position')} type="range" min="-1" max="1" step="0.01" value={adjustment.x} disabled={!image} onChange={event => update({x: Number(event.target.value)})}/></label>
      <label><span>{t('Vertical position')}<output>{Math.round(adjustment.y * 100)}%</output></span><input aria-label={t('Avatar vertical position')} type="range" min="-1" max="1" step="0.01" value={adjustment.y} disabled={!image} onChange={event => update({y: Number(event.target.value)})}/></label>
    </div>
    </div><div className="avatar-fit-actions"><button type="button" className="secondary" disabled={!image} onClick={() => setAdjustment({zoom:1,x:0,y:0})}>{t('Fit whole image')}</button><button type="button" className="secondary" disabled={!image} onClick={() => image && setAdjustment({zoom:avatarFillZoom(image.naturalWidth,image.naturalHeight),x:0,y:0})}>{t('Fill circle')}</button><button type="button" className="text-button" disabled={!image} onClick={() => setAdjustment({zoom:1,x:0,y:0})}><RotateCcw size={13}/>{t('Reset framing')}</button></div>
    {error && <p className="error" role="alert">{t(error)}</p>}
    <footer className="avatar-editor-actions"><button type="button" className="secondary" onClick={onCancel}>{t('Cancel adjustment')}</button><button type="button" className="primary" disabled={!image || applying} onClick={apply}>{t('Apply framing')}</button></footer>
  </section>;
}
