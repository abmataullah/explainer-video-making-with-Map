import {geoMercator, geoPath, geoArea, geoCentroid} from 'd3-geo';
import world from './data/world.json';

// Fixed world projection: everything is drawn once in "world px" and the
// camera moves with an SVG transform. Fast: no re-projection per frame.
export const WORLD_W = 4000;
export const projection = geoMercator()
  .scale(WORLD_W / (2 * Math.PI))
  .translate([WORLD_W / 2, WORLD_W / 2 * 0.72]);
const path = geoPath(projection);

export const features = world.features.map((f) => ({
  iso: f.properties.iso,
  iso2: f.properties.iso2,
  name: f.properties.name,
  bn: f.properties.bn,
  rank: f.properties.rank || 5,
  label: projection([f.properties.lx, f.properties.ly]),
  d: path(f) || '',
  f,
}));
export const norm = (k) => String(k).trim().toLowerCase().replace(/[\s.'’\-]+/g, '');
const lookup = {};
world.features.forEach((f, i) => {
  const p = f.properties;
  const c = features[i];
  [p.iso, p.iso2, p.name, p.bn, ...(p.aliases || [])].forEach((n) => {
    if (n && !(norm(n) in lookup)) lookup[norm(n)] = c;
  });
});
export const byIso = Object.fromEntries(features.map((c) => [c.iso, c]));
// Accepts ISO3, ISO2, English or Bangla name ("BGD", "bd", "Bangladesh", "বাংলাদেশ").
export const findCountry = (key) => {
  if (!key || typeof key !== 'string') return null;
  return byIso[key.trim().toUpperCase()] || lookup[norm(key)] || null;
};

// Main-territory bounds: ignore far-flung islands/overseas parts.
const mainBoundsCache = {};
export const mainBounds = (c) => {
  if (mainBoundsCache[c.iso]) return mainBoundsCache[c.iso];
  const g = c.f.geometry;
  const polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
  const items = polys.map((p) => {
    const feat = {type: 'Feature', geometry: {type: 'Polygon', coordinates: p}};
    return {feat, area: geoArea(feat), cen: geoCentroid(feat)};
  });
  const big = items.reduce((a, b) => (b.area > a.area ? b : a));
  const keep = items.filter((it) => it.area >= big.area * 0.04 &&
    Math.abs(it.cen[0] - big.cen[0]) < 40 && Math.abs(it.cen[1] - big.cen[1]) < 30);
  let b = null;
  for (const it of keep) {
    const pb = path.bounds(it.feat);
    b = b ? [[Math.min(b[0][0], pb[0][0]), Math.min(b[0][1], pb[0][1])],
             [Math.max(b[1][0], pb[1][0]), Math.max(b[1][1], pb[1][1])]] : pb;
  }
  mainBoundsCache[c.iso] = b;
  return b;
};

export const lonlat = (lon, lat) => (isFinite(lon) && isFinite(lat) ? projection([lon, lat]) : null);

// Arrow/point endpoint: ISO code, country name, {lon,lat} or [lon,lat].
export const anchor = (x) => {
  if (!x) return null;
  if (Array.isArray(x)) return lonlat(+x[0], +x[1]);
  if (typeof x === 'object' && x.lon !== undefined) return lonlat(+x.lon, +x.lat);
  const c = findCountry(x);
  return c ? c.label : null;
};

export const WORLD_CAMERA = {cx: WORLD_W / 2, cy: WORLD_W / 2 * 0.62, w: WORLD_W * 0.95, h: WORLD_W * 0.5};

// Camera for a scene = bbox of focus countries + arrow ends + points.
export const sceneCamera = (s) => {
  const boxes = [];
  for (const k of s.focus || []) {
    const c = findCountry(k);
    if (c) boxes.push(mainBounds(c));
  }
  const pt = (p) => p && boxes.push([[p[0] - 5, p[1] - 5], [p[0] + 5, p[1] + 5]]);
  for (const a of s.arrows || []) { pt(anchor(a.from)); pt(anchor(a.to)); }
  for (const p of s.points || []) pt(lonlat(+p.lon, +p.lat));
  if (!boxes.length) return null;
  const x0 = Math.min(...boxes.map((b) => b[0][0]));
  const y0 = Math.min(...boxes.map((b) => b[0][1]));
  const x1 = Math.max(...boxes.map((b) => b[1][0]));
  const y1 = Math.max(...boxes.map((b) => b[1][1]));
  const zoomOut = s.zoom ? 1 / s.zoom : 1;
  return {cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, w: Math.max(x1 - x0, 25) * zoomOut, h: Math.max(y1 - y0, 25) * zoomOut};
};

export const fitScale = (cam, W, H, pad = 1.6) => Math.min(W / (cam.w * pad), H / (cam.h * pad));
