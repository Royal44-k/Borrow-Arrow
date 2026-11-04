export type BoatPart = 'hull' | 'straw' | 'armor' | 'lantern';
export type Point3 = [number, number, number];

export const HULL_HALF_LENGTH = 4.8;

export function hullHalfWidth(x: number): number {
  const t = Math.max(0, Math.min(1, (x + HULL_HALF_LENGTH) / (HULL_HALF_LENGTH * 2)));
  return .075 + 1.34 * Math.pow(Math.max(0, Math.sin(Math.PI * t)), .68);
}

export function hullPoint(x: number, height: number, side: 1 | -1): Point3 {
  const t = Math.max(0, Math.min(1, height));
  const rise = .53 * Math.pow(Math.abs(x / HULL_HALF_LENGTH), 4);
  return [x, -.62 + .88 * t + rise, side * hullHalfWidth(x) * Math.sin(t * Math.PI / 2)];
}

export function normalizeAngle(angle: number): number {
  return Number.isFinite(angle) ? ((angle % 360) + 360) % 360 : 0;
}

export function arrowVisualCount(density: number): number {
  return Number.isFinite(density) ? Math.round(Math.max(0, Math.min(100, density)) * 1.6) : 0;
}

export function strawLayout(): Array<{ x: number; z: number; side: 1 | -1 }> {
  const result: Array<{ x: number; z: number; side: 1 | -1 }> = [];
  for (const side of [-1, 1] as const) {
    for (let i = 0; i < 8; i++) {
      const x = -3.5 + i;
      result.push({ x, z: side * (hullHalfWidth(x) + .08), side });
    }
  }
  return result;
}

/** Stable procedural variation, deliberately independent of story state. */
export function seededRandom(seed = 7927): () => number {
  let state = seed >>> 0;
  return () => {
    state = (1664525 * state + 1013904223) >>> 0;
    return state / 4294967296;
  };
}
