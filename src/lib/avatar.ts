/** Image framing is shared by the live preview and the saved 256px avatar. */
export function avatarPlacement(width: number, height: number, size = 256) {
  if (![width, height, size].every(value => Number.isFinite(value) && value > 0)) {
    throw new Error('Image dimensions must be positive finite numbers.');
  }
  const scale = size / Math.hypot(width, height);
  const drawWidth = width * scale;
  const drawHeight = height * scale;
  return { x: (size - drawWidth) / 2, y: (size - drawHeight) / 2, width: drawWidth, height: drawHeight };
}
export type AvatarAdjustment = { zoom: number; x: number; y: number };
export function normalizeAvatarAdjustment(value: Partial<AvatarAdjustment>): AvatarAdjustment {
  const bounded = (n: unknown, fallback: number, min: number, max: number) =>
    typeof n === 'number' && Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : fallback;
  return { zoom: bounded(value.zoom, 1, 0.5, 8), x: bounded(value.x, 0, -1, 1), y: bounded(value.y, 0, -1, 1) };
}
export function avatarFrame(width: number, height: number, adjustment: Partial<AvatarAdjustment>, size = 256) {
  const base = avatarPlacement(width, height, size);
  const value = normalizeAvatarAdjustment(adjustment);
  const drawWidth = base.width * value.zoom;
  const drawHeight = base.height * value.zoom;
  const panX = Math.max(size / 2, (drawWidth - size) / 2);
  const panY = Math.max(size / 2, (drawHeight - size) / 2);
  return { x: (size - drawWidth) / 2 + value.x * panX,
    y: (size - drawHeight) / 2 + value.y * panY, width: drawWidth, height: drawHeight, panX, panY };
}
export function avatarFillZoom(width: number, height: number): number {
  avatarPlacement(width, height);
  return normalizeAvatarAdjustment({zoom: Math.hypot(width, height) / Math.min(width, height)}).zoom;
}
