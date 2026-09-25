import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Img, OffthreadVideo, staticFile, interpolate, interpolateColors, spring, Easing,
  delayRender, continueRender} from 'remotion';
import {geoOrthographic, geoPath, geoGraticule10, geoDistance} from 'd3-geo';
import {features, findCountry} from './geo';

export const MONO = "Consolas, 'Cascadia Mono', 'Courier New', monospace";
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'};
const ease = Easing.bezier(0.65, 0, 0.35, 1);

// ---- text size: one multiplier for every caption, card and label (Settings > Text size) ----
export const TXT = {k: 1.25};
export const FS = (n) => Math.round(n * TXT.k);

// ---- background colour: any base colour becomes a full palette (sea, land, panels) ----
export const BGS = {navy: '#0b2447', blue: '#0d3b66', red: '#5a0f1a', maroon: '#3d0a12', teal: '#083d44',
  green: '#0f3d24', purple: '#2b1150', brown: '#3b2412', charcoal: '#15181c'};
const hx = (h) => { const n = parseInt(String(h).replace('#', ''), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
const mixc = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));
const rgb = (c) => `rgb(${c.join(',')})`;
export const bgTheme = (key) => {
  const h = BGS[key] || (/^#[0-9a-f]{6}$/i.test(String(key || '')) ? key : null);
  if (!h) return {};
  const c = hx(h), K = [0, 0, 0], Wt = [255, 255, 255];
  const red = c[0] > c[2] * 1.6 && c[0] > c[1] * 1.6;
  return {bg0: rgb(mixc(c, K, 0.42)), bg1: rgb(c), sea: rgb(mixc(c, K, 0.22)), land: rgb(mixc(c, Wt, 0.14)),
    edge: rgb(mixc(c, Wt, 0.4)), panel: `rgba(${mixc(c, K, 0.5).join(',')},0.9)`, dim: mixc(c, K, 0.6).join(','),
    choroLow: rgb(mixc(c, Wt, 0.2)), grid: 'rgba(255,255,255,0.07)', sub: rgb(mixc(c, Wt, 0.66)),
    ...(red ? {accent: '#ffc233', choroHigh: '#ffc233', glow: 'rgba(255,194,51,0.25)'} : {})};
};

export const THEMES = {
  classic: {bg0: '#07131f', bg1: '#0d2236', land: '#1b3148', edge: '#4a6784', text: '#ffffff', sub: '#a9c1d6',
    accent: '#ffd166', panel: 'rgba(6,16,28,0.8)', dim: '4,10,18', shadow: '0 2px 8px rgba(0,0,0,0.9)',
    capBg: 'rgba(0,0,0,0.62)', capText: '#ffffff', grid: 'rgba(255,255,255,0.06)', sea: '#0b2a44',
    choroLow: '#24425f', choroHigh: '#ffd166', glow: 'rgba(72,149,239,0.35)'},
  hud: {bg0: '#08090b', bg1: '#15181c', land: '#262a31', edge: '#454b54', text: '#f2f2f0', sub: '#8d9199',
    accent: '#e0283c', panel: 'rgba(12,13,16,0.9)', dim: '5,6,8', shadow: '0 2px 8px rgba(0,0,0,0.9)',
    capBg: 'rgba(0,0,0,0.75)', capText: '#ffffff', grid: 'rgba(255,255,255,0.05)', sea: '#0a0b0d',
    choroLow: '#2a2e35', choroHigh: '#e0283c', glow: 'rgba(224,40,60,0.18)'},
  light: {bg0: '#dcd9d1', bg1: '#f1efea', land: '#cbc7bd', edge: '#a39e92', text: '#141414', sub: '#555555',
    accent: '#d6203a', panel: 'rgba(250,250,248,0.95)', dim: '239,237,232', shadow: '0 1px 2px rgba(255,255,255,0.9)',
    capBg: 'rgba(20,20,20,0.86)', capText: '#ffffff', grid: 'rgba(0,0,0,0.05)', sea: '#e7e4dd',
    choroLow: '#ebe3d6', choroHigh: '#d6203a', glow: 'rgba(0,0,0,0.08)'},
};

// load the producer's chosen fonts before the first frame is drawn
export const useFontFiles = (files) => {
  const [h] = useState(() => (files && files.length ? delayRender('fonts') : null));
  useEffect(() => {
    if (!h) return;
    Promise.all(files.map((f) => new FontFace(f.family, `url(${staticFile(f.src)})`, {weight: String(f.weight || 400)})
      .load().then((ff) => document.fonts.add(ff)).catch(() => null))).then(() => continueRender(h));
  }, []);
};

const BN = '০১২৩৪৫৬৭৮৯';
export const bnDigits = (s, lang) => (lang === 'bn' ? String(s).replace(/[0-9]/g, (d) => BN[+d]) : String(s));
const fmtNum = (v, lang) => {
  const n = Math.abs(v) >= 1000 ? Math.round(v).toLocaleString('en-US') : String(Math.round(v * 100) / 100);
  return bnDigits(n, lang);
};

// ---- lon/lat helpers for the globe ----
const llOf = (x) => {
  if (!x) return null;
  if (Array.isArray(x)) return [+x[0], +x[1]];
  if (typeof x === 'object' && x.lon !== undefined) return [+x.lon, +x.lat];
  const c = findCountry(x);
  return c ? [c.f.properties.lx, c.f.properties.ly] : null;
};
export const focusCenter = (s) => {
  const pts = [];
  (s.focus || []).forEach((k) => { const p = llOf(k); if (p) pts.push(p); });
  if (s.type === 'choropleth' && !pts.length) Object.keys(s.values || {}).forEach((k) => { const p = llOf(k); if (p) pts.push(p); });
  (s.points || []).forEach((p) => pts.push([+p.lon, +p.lat]));
  if (!pts.length) return [90.3, 23.7];
  const lat = pts.reduce((a, p) => a + p[1], 0) / pts.length;
  const x = pts.reduce((a, p) => a + Math.cos(p[0] * Math.PI / 180), 0), y = pts.reduce((a, p) => a + Math.sin(p[0] * Math.PI / 180), 0);
  return [Math.atan2(y, x) * 180 / Math.PI, lat];
};

// ---- rotating 3D globe ----
export const GlobeLayer = ({s, prevS, local, W, H, T, hl, lang, font}) => {
  const to = focusCenter(s);
  const from = prevS ? focusCenter(prevS) : [to[0] - 70, to[1] * 0.3];
  let dl = to[0] - from[0];
  if (dl > 180) dl -= 360;
  if (dl < -180) dl += 360;
  const m = interpolate(local, [0, 50], [0, 1], {...clamp, easing: ease});
  const lon = from[0] + dl * m + Math.max(0, local - 50) * 0.03;
  const lat = from[1] + (to[1] - from[1]) * m;
  const R = Math.min(W, H) * 0.42 * interpolate(local, [0, 50], [0.9, 1.0], {...clamp, easing: ease});
  const proj = geoOrthographic().scale(R).translate([W / 2, H / 2]).rotate([-lon, -lat * 0.85]).clipAngle(90);
  const path = geoPath(proj);
  const center = [lon, lat * 0.85];
  const vis = (p) => geoDistance(p, center) < Math.PI / 2 - 0.05;
  const fadeIn = interpolate(local, [0, 12], [0, 1], clamp);
  return (
    <AbsoluteFill style={{opacity: fadeIn}}>
      <svg width={W} height={H}>
        <defs>
          <radialGradient id="gsea" cx="42%" cy="38%" r="70%">
            <stop offset="0%" stopColor={T.bg1} /><stop offset="100%" stopColor={T.sea} />
          </radialGradient>
          <radialGradient id="gglow" cx="50%" cy="50%" r="50%">
            <stop offset="80%" stopColor={T.glow} /><stop offset="100%" stopColor="rgba(0,0,0,0)" />
          </radialGradient>
        </defs>
        <circle cx={W / 2} cy={H / 2} r={R * 1.12} fill="url(#gglow)" />
        <path d={path({type: 'Sphere'})} fill="url(#gsea)" stroke={T.edge} strokeWidth={1.5} />
        <path d={path(geoGraticule10())} fill="none" stroke={T.grid} strokeWidth={1} />
        {features.map((c) => {
          const d = path(c.f);
          return d ? <path key={c.iso + c.name} d={d} fill={hl[c.iso] || T.land} stroke={T.edge}
            strokeWidth={hl[c.iso] ? 1.4 : 0.6} strokeLinejoin="round" /> : null;
        })}
        {(s.arrows || []).map((a, j) => {
          const A = llOf(a.from), B = llOf(a.to);
          if (!A || !B) return null;
          const p = interpolate(local, [30 + j * 12, 70 + j * 12], [0, 1], {...clamp, easing: ease});
          const d = path({type: 'LineString', coordinates: [A, B]});
          return d ? <path key={'ga' + j} d={d} fill="none" stroke={T.accent} strokeWidth={5} strokeLinecap="round"
            pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} /> : null;
        })}
        {(s.points || []).map((pt, j) => {
          const ll = [+pt.lon, +pt.lat];
          if (!vis(ll)) return null;
          const [x, y] = proj(ll);
          const pulse = (local % 40) / 40;
          return (<g key={'gp' + j}>
            <circle cx={x} cy={y} r={8 + pulse * 22} fill="none" stroke={T.accent} strokeWidth={3} opacity={1 - pulse} />
            <circle cx={x} cy={y} r={8} fill={T.accent} stroke={T.bg0} strokeWidth={3} />
            <text x={x + 16} y={y + 9} fill={T.text} fontSize={FS(30)} fontWeight={700} fontFamily={font}
              style={{paintOrder: 'stroke'}} stroke={T.bg0} strokeWidth={6}>{pt.name}</text></g>);
        })}
        {features.filter((c) => hl[c.iso]).map((c) => {
          const ll = [c.f.properties.lx, c.f.properties.ly];
          if (!vis(ll)) return null;
          const [x, y] = proj(ll);
          return <text key={'gl' + c.iso} x={x} y={y} textAnchor="middle" fill={T.text} fontSize={FS(34)} fontWeight={800}
            fontFamily={font} opacity={interpolate(local, [30, 45], [0, 1], clamp)}
            style={{paintOrder: 'stroke'}} stroke={T.bg0} strokeWidth={7}>{lang === 'bn' ? c.bn : c.name}</text>;
        })}
      </svg>
    </AbsoluteFill>
  );
};
// ---- choropleth colours + legend ----
export const choroColors = (s, T, interpolateColors) => {
  const v = s.values || {};
  const ks = Object.keys(v);
  if (!ks.length) return {};
  const lo = Math.min(...ks.map((k) => v[k])), hi = Math.max(...ks.map((k) => v[k]));
  const out = {};
  ks.forEach((k) => {
    const c = findCountry(k);
    if (c) out[c.iso] = interpolateColors(hi === lo ? 1 : (v[k] - lo) / (hi - lo), [0, 1], [T.choroLow, T.choroHigh]);
  });
  return out;
};
export const ChoroLegend = ({s, T, W, H, local, fps, lang, font}) => {
  const v = Object.values(s.values || {});
  if (!v.length) return null;
  const lo = Math.min(...v), hi = Math.max(...v);
  const a = spring({frame: local - 10, fps, config: {damping: 200}});
  const vertical = H > W;
  const unit = s.unit || '';
  return (
    <div style={{position: 'absolute', left: 70, bottom: vertical ? 430 : 170, opacity: a, fontFamily: font,
      background: T.panel, padding: '16px 22px', border: `1px solid ${T.edge}`, minWidth: 380}}>
      <div style={{width: 360, height: 16, background: `linear-gradient(90deg, ${T.choroLow}, ${T.choroHigh})`}} />
      <div style={{display: 'flex', justifyContent: 'space-between', color: T.text, fontSize: FS(28), fontWeight: 700, marginTop: 8}}>
        <span>{fmtNum(lo, lang)}{unit}</span><span>{fmtNum(hi, lang)}{unit}</span>
      </div>
      {s.source ? <div style={{color: T.sub, fontSize: FS(20), marginTop: 6}}>{s.source}</div> : null}
    </div>
  );
};

// ---- chart card: R draws every frame of the build-up, the card itself enters differently per chart type ----
const ENTRY = {
  bar: 'rise', stacked: 'rise', hbar: 'slide', lollipop: 'slide', line: 'focus', area: 'focus',
  donut: 'spin', pie: 'spin', waffle: 'zoom', treemap: 'zoom',
};
export const ChartCard = ({s, local, fps, W, H, T, font, look, lang}) => {
  const ch = s.chart || {};
  if (!ch.dir && !ch.img) return null;
  const vertical = H > W;
  const a = spring({frame: local - 2, fps, config: {damping: 16, mass: 0.7}});
  const e = ENTRY[ch.kind] || 'rise';
  const tf = e === 'slide' ? `translateX(${(1 - a) * -120}px)` : e === 'spin' ? `scale(${0.7 + 0.3 * a}) rotate(${(1 - a) * -8}deg)`
    : e === 'zoom' ? `scale(${0.85 + 0.15 * a})` : `translateY(${(1 - a) * 90}px)`;
  const blur = e === 'focus' ? `blur(${(1 - a) * 14}px)` : 'none';
  const n = ch.frames || 1;
  const fi = Math.max(0, Math.min(n - 1, local - 10));
  const src = ch.dir ? `${ch.dir}/f${String(fi).padStart(3, '0')}.png` : ch.img;
  const left = W * (vertical ? 0.04 : 0.07), width = W * (vertical ? 0.92 : 0.86);
  const titleIn = interpolate(local, [4, 20], [0, 1], clamp);
  const accentW = interpolate(local, [6, 30], [0, 1], {...clamp, easing: ease});
  return (
    <div style={{position: 'absolute', left, width, top: vertical ? H * 0.17 : H * 0.1, opacity: Math.min(1, a * 1.4),
      transform: tf, filter: blur, background: T.panel, border: `1px solid ${T.edge}`,
      padding: vertical ? '30px 28px' : '26px 40px', fontFamily: font, boxSizing: 'border-box', overflow: 'hidden'}}>
      <div style={{position: 'absolute', left: 0, top: 0, height: 4, width: `${accentW * 100}%`, background: T.accent}} />
      {look === 'hud' ? <div style={{fontFamily: MONO, fontSize: FS(20), letterSpacing: 3, color: T.sub, marginBottom: 10, opacity: titleIn}}>
        <span style={{color: T.accent}}>■ </span>DATA // {lang === 'bn' ? 'তথ্য' : 'CHART'} // {String(ch.kind || '').toUpperCase()}</div> : null}
      <div style={{color: T.text, fontSize: FS(vertical ? 58 : 52), fontWeight: 800, lineHeight: 1.25, marginBottom: 12,
        opacity: titleIn, transform: `translateX(${(1 - titleIn) * 30}px)`}}>{ch.title || s.headline}</div>
      <div style={{position: 'relative', overflow: 'hidden'}}>
        <Img src={staticFile(src)} style={{display: 'block', width: '100%', height: vertical ? H * 0.55 : H * 0.64, objectFit: 'contain',
          transform: `scale(${1 + Math.min(0.07, Math.max(0, local - 10 - n) * 0.0005)})`, transformOrigin: '50% 60%'}} />
        {local - 10 - n > 0 && ((local - 10 - n) % 150) < 45 ? <div style={{position: 'absolute', top: 0, bottom: 0, width: '16%',
          left: `${-20 + (((local - 10 - n) % 150) / 45) * 140}%`, transform: 'skewX(-14deg)',
          background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.10), transparent)'}} /> : null}
      </div>
      {ch.source ? <div style={{color: T.sub, fontSize: FS(22), marginTop: 8, opacity: interpolate(local, [50, 70], [0, 1], clamp)}}>
        {(lang === 'bn' ? 'সূত্র: ' : 'Source: ') + ch.source}</div> : null}
    </div>
  );
};

// ---- counting number for stat cards: keeps prefix/suffix and Bangla digits ----
const EN = '0123456789';
export const countUp = (value, p) => {
  const str = String(value ?? '');
  if (/(^|[^0-9০-৯,.])(1[89]|20|১[৮৯]|২০)[0-9০-৯]{2}([^0-9০-৯,.]|$)/.test(str) && !/[,.%]/.test(str)) return str;
  const toEn = str.replace(/[০-৯]/g, (d) => EN[BN.indexOf(d)]);
  const m = toEn.match(/-?\d[\d,]*(\.\d+)?/);
  if (!m) return str;
  const isBn = /[০-৯]/.test(str);
  const target = parseFloat(m[0].replace(/,/g, ''));
  const decs = m[1] ? m[1].length - 1 : 0;
  let v = (target * p).toFixed(decs);
  if (m[0].includes(',')) v = Number(v).toLocaleString('en-US', {minimumFractionDigits: decs, maximumFractionDigits: decs});
  const out = toEn.slice(0, m.index) + v + toEn.slice(m.index + m[0].length);
  return isBn ? out.replace(/[0-9]/g, (d) => BN[+d]) : out.replace(/[0-9]/g, (d, i) => d);
};
export const percentOf = (value) => {
  const s = String(value ?? '').replace(/[০-৯]/g, (d) => EN[BN.indexOf(d)]);
  const m = s.match(/(\d+(\.\d+)?)\s*%/);
  return m ? Math.min(100, parseFloat(m[1])) : null;
};

// ---- stock footage ----
export const BrollLayer = ({s, local, frames, T, look, W, H}) => {
  const z = interpolate(local, [0, frames], [1.05, 1.16]);
  return (
    <AbsoluteFill style={{opacity: interpolate(local, [0, 8], [0, 1], clamp), background: '#000'}}>
      <OffthreadVideo src={staticFile(s.broll_file)} startFrom={Math.round((s.broll_offset || 0) * 30)} muted style={{width: '100%', height: '100%', objectFit: 'cover',
        transform: `scale(${z})`, filter: look === 'hud' ? 'contrast(1.08) saturate(0.72)' : 'saturate(0.95)'}} />
      <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(0,0,0,0.45) 0%, rgba(0,0,0,0) 25%, rgba(0,0,0,0) 60%, rgba(0,0,0,0.6) 100%)'}} />
      {look === 'hud' ? <div style={{position: 'absolute', right: 60, bottom: H > W ? 420 : 150, fontFamily: MONO, fontSize: FS(20),
        letterSpacing: 3, color: '#fff', background: 'rgba(0,0,0,0.55)', padding: '6px 12px', border: '1px solid rgba(255,255,255,0.25)'}}>
        <span style={{color: T.accent}}>● </span>FOOTAGE // LIVE FEED</div> : null}
    </AbsoluteFill>
  );
};

// ---- HUD frame: grid, border and corner labels ----
export const HudOverlay = ({W, H, T, channel, cur, frame, fps, year, dataNote}) => {
  const [lon, lat] = focusCenter(cur.s);
  const t = frame / fps;
  const mm = `${String(Math.floor(t / 60)).padStart(2, '0')}.${String(Math.floor(t % 60)).padStart(2, '0')}`;
  const isBroll = cur.s.type === 'broll';
  const lab = {position: 'absolute', fontFamily: MONO, fontSize: FS(18), letterSpacing: 3, textTransform: 'uppercase',
    color: isBroll ? '#ffffff' : T.sub};
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {!isBroll ? <AbsoluteFill style={{backgroundImage: `linear-gradient(${T.grid} 1px, transparent 1px), linear-gradient(90deg, ${T.grid} 1px, transparent 1px)`,
        backgroundSize: '80px 80px'}} /> : null}
      <div style={{position: 'absolute', inset: 26, border: `1px solid ${isBroll ? 'rgba(255,255,255,0.25)' : T.edge}`}} />
      <div style={{...lab, top: 42, left: 50}}><span style={{color: T.accent}}>● </span>{channel} // {(cur.s.type || 'map').toUpperCase()}</div>
      <div style={{...lab, top: 42, right: 50}}>SCENE {String(cur.i + 1).padStart(2, '0')} / {mm}</div>
      <div style={{...lab, bottom: 40, left: 50}}>{Math.abs(lat).toFixed(2)}°{lat >= 0 ? 'N' : 'S'} {Math.abs(lon).toFixed(2)}°{lon >= 0 ? 'E' : 'W'}</div>
      <div style={{...lab, bottom: 40, right: 50, textTransform: 'none'}}>{dataNote ? dataNote : `REPORT // ${year}`}</div>
    </AbsoluteFill>
  );
};
// ============================================================ spreading events inside a country ----
import {projection as WORLDPROJ} from './geo';
const admPath = geoPath(WORLDPROJ);
export const EFFECTS = {
  flood: {c: '#2f80ed', pat: 'waves', bn: 'বন্যাকবলিত এলাকা', en: 'Flooded area'},
  conflict: {c: '#e63946', pat: 'hatch', pulse: true, bn: 'সংঘাতপূর্ণ এলাকা', en: 'Conflict area'},
  fire: {c: '#ff6b1a', pat: 'hatch', pulse: true, bn: 'আগুনে ক্ষতিগ্রস্ত এলাকা', en: 'Fire affected'},
  drought: {c: '#c9912c', pat: 'cracks', bn: 'খরাপীড়িত এলাকা', en: 'Drought hit'},
  disease: {c: '#9d4edd', pat: 'dots', bn: 'আক্রান্ত এলাকা', en: 'Affected area'},
  protest: {c: '#ffb703', pat: 'dots', pulse: true, bn: 'বিক্ষোভের এলাকা', en: 'Protest area'},
  control: {c: '#e0283c', pat: 'none', bn: 'নিয়ন্ত্রিত এলাকা', en: 'Controlled area'},
  cyclone: {c: '#56ccf2', pat: 'waves', bn: 'ঘূর্ণিঝড়ের পথ', en: 'Cyclone path'},
};

// load the boundary files named in the scenes (once, before rendering)
export const useAdm = (scenes) => {
  const files = [...new Set((scenes || []).map((s) => s.adm).filter(Boolean))];
  const [data, setData] = useState({});
  const [h] = useState(() => (files.length ? delayRender('boundaries') : null));
  useEffect(() => {
    if (!h) return;
    Promise.all(files.map((f) => fetch(staticFile(f)).then((r) => r.json()).then((j) => [f, j]).catch(() => [f, null])))
      .then((all) => { setData(Object.fromEntries(all)); continueRender(h); });
  }, []);
  return data;
};

// which affected regions have been reached at frame `local`, and the spread radius (world px)
export const spreadState = (s, adm, local, frames) => {
  const feats = (adm && adm.features) || [];
  const by = Object.fromEntries(feats.map((f) => [f.name, f]));
  const aff = (s.affected || []).filter((n) => by[n]);
  const t0 = 12, t1 = Math.max(t0 + 30, frames * 0.78);
  const o = s.origin_ll ? WORLDPROJ(s.origin_ll) : null;
  const act = {};
  let R = 0, Rmax = 1;
  if ((s.mode || 'regions') === 'spread' && o) {
    const pool = aff.length ? aff.map((n) => by[n]) : feats;
    Rmax = Math.max(1, ...pool.map((f) => { const p = WORLDPROJ(f.c); return Math.hypot(p[0] - o[0], p[1] - o[1]); })) * 1.25;
    R = Rmax * interpolate(local, [t0, t1], [0, 1], {...clamp, easing: Easing.inOut(Easing.quad)});
    pool.forEach((f) => { const p = WORLDPROJ(f.c); const d = Math.hypot(p[0] - o[0], p[1] - o[1]);
      act[f.name] = t0 + (t1 - t0) * Math.min(1, d / Rmax); });
  } else {
    aff.forEach((n, i) => { act[n] = t0 + (aff.length > 1 ? i / (aff.length - 1) : 0) * (t1 - t0); });
  }
  return {by, aff, act, o, R, t0, t1};
};

const Pattern = ({id, kind, unit, color, local}) => {
  const u = unit;
  if (kind === 'waves') return (<pattern id={id} width={u * 4} height={u * 2} patternUnits="userSpaceOnUse"
    patternTransform={`translate(${(local * u * 0.06) % (u * 4)},0)`}>
    <path d={`M0 ${u} Q ${u} 0 ${u * 2} ${u} T ${u * 4} ${u}`} fill="none" stroke="#ffffff" strokeOpacity={0.55} strokeWidth={u * 0.18} /></pattern>);
  if (kind === 'hatch') return (<pattern id={id} width={u * 1.6} height={u * 1.6} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
    <line x1={0} y1={0} x2={0} y2={u * 1.6} stroke="#000" strokeOpacity={0.35} strokeWidth={u * 0.5} /></pattern>);
  if (kind === 'dots') return (<pattern id={id} width={u * 1.8} height={u * 1.8} patternUnits="userSpaceOnUse">
    <circle cx={u * 0.9} cy={u * 0.9} r={u * 0.32} fill="#ffffff" fillOpacity={0.5} /></pattern>);
  if (kind === 'cracks') return (<pattern id={id} width={u * 3} height={u * 3} patternUnits="userSpaceOnUse">
    <path d={`M0 ${u * 1.5} L${u * 0.8} ${u} L${u * 1.5} ${u * 1.9} L${u * 2.3} ${u * 1.1} L${u * 3} ${u * 1.6}`} fill="none"
      stroke="#3a2a10" strokeOpacity={0.6} strokeWidth={u * 0.14} /></pattern>);
  return null;
};

// drawn inside the map's camera group (world coordinates)
export const SpreadWorld = ({s, adm, local, frames, T}) => {
  if (!adm) return null;
  const ef = EFFECTS[s.effect] || EFFECTS.flood;
  const color = s.color || ef.c;
  const st = spreadState(s, adm, local, frames);
  const feats = adm.features;
  const bb = s.zoom_bbox || [0, 0, 1, 1];
  const a = WORLDPROJ([bb[0], bb[3]]), b = WORLDPROJ([bb[2], bb[1]]);
  const unit = Math.max(0.05, (b[0] - a[0]) / 70);
  const pulse = ef.pulse ? 0.85 + 0.15 * Math.sin(local / 4) : 1;
  const uid = 'sp' + (s.adm || '').replace(/\W/g, '');
  const spread = (s.mode || 'regions') === 'spread' && st.o;
  const heat = s.mode === 'heat' && s.heat;
  const hv = heat ? Object.values(s.heat) : [];
  const hlo = heat ? Math.min(...hv) : 0, hhi = heat ? Math.max(...hv) : 1;
  const heatCol = (v) => interpolateColors(hhi === hlo ? 1 : (v - hlo) / (hhi - hlo), [0, 1], [T.choroLow, color]);
  const clipFeats = st.aff.length ? st.aff.map((n) => st.by[n]) : feats;
  return (
    <g>
      <defs>
        <Pattern id={uid + 'p'} kind={ef.pat} unit={unit} color={color} local={local} />
        <clipPath id={uid + 'c'}>{clipFeats.map((f) => <path key={f.name} d={admPath(f.geometry)} />)}</clipPath>
        <filter id={uid + 'f'} x="-30%" y="-30%" width="160%" height="160%">
          <feTurbulence type="fractalNoise" baseFrequency={0.16 / unit} numOctaves={3} seed={4} />
          <feDisplacementMap in="SourceGraphic" scale={unit * 7} />
        </filter>
      </defs>
      {heat ? st.aff.map((n) => {
        const f = st.by[n];
        const p = interpolate(local, [st.act[n], st.act[n] + 14], [0, 1], {...clamp, easing: ease});
        if (p <= 0 || s.heat[n] === undefined) return null;
        return <path key={'h' + n} d={admPath(f.geometry)} fill={heatCol(s.heat[n])} fillOpacity={0.92 * p} />;
      }) : spread ? (
        <g clipPath={`url(#${uid}c)`}>
          <circle cx={st.o[0]} cy={st.o[1]} r={st.R} fill={color} fillOpacity={0.62 * pulse} filter={`url(#${uid}f)`} />
          {ef.pat !== 'none' && <circle cx={st.o[0]} cy={st.o[1]} r={st.R} fill={`url(#${uid}p)`} filter={`url(#${uid}f)`} />}
        </g>
      ) : st.aff.map((n) => {
        const f = st.by[n];
        const p = interpolate(local, [st.act[n], st.act[n] + 14], [0, 1], {...clamp, easing: ease});
        if (p <= 0) return null;
        const d = admPath(f.geometry);
        const ring = interpolate(local, [st.act[n], st.act[n] + 22], [1, 0], clamp);
        return (<g key={n}>
          <path d={d} fill={color} fillOpacity={0.72 * p * pulse} />
          {ef.pat !== 'none' && <path d={d} fill={`url(#${uid}p)`} opacity={p} />}
          <path d={d} fill="none" stroke="#ffffff" strokeOpacity={ring * 0.9} strokeWidth={2 + ring * 5} vectorEffect="non-scaling-stroke" />
        </g>);
      })}
      {feats.map((f) => <path key={'b' + f.name} d={admPath(f.geometry)} fill="none" stroke={T.text}
        strokeOpacity={0.28} strokeWidth={0.8} vectorEffect="non-scaling-stroke" />)}
    </g>
  );
};

// screen-space extras: origin pulse, labels, cyclone track, legend with a live count
export const SpreadHud = ({s, adm, local, frames, fps, toScreen, W, H, T, font, lang}) => {
  if (!adm) return null;
  const ef = EFFECTS[s.effect] || EFFECTS.flood;
  const color = s.color || ef.c;
  const st = spreadState(s, adm, local, frames);
  const reached = Object.keys(st.act).filter((n) => local >= st.act[n]);
  const labelsOn = (st.aff.length ? st.aff : []).filter((n) => local >= st.act[n] + 4).slice(0, 14);
  const unitName = lang === 'bn' ? (s.level === 1 ? 'বিভাগ' : 'জেলা') : (s.level === 1 ? 'divisions' : 'districts');
  const vertical = H > W;
  const track = (s.track || []).map((p) => toScreen(WORLDPROJ([+p[0], +p[1]])));
  const tp = interpolate(local, [10, frames * 0.85], [0, 1], {...clamp, easing: Easing.inOut(Easing.quad)});
  let cyc = null, trackD = null;
  if (track.length > 1) {
    const segs = track.slice(1).map((p, i) => Math.hypot(p[0] - track[i][0], p[1] - track[i][1]));
    const total = segs.reduce((x, y) => x + y, 0);
    let dist = tp * total, i = 0;
    while (i < segs.length - 1 && dist > segs[i]) { dist -= segs[i]; i++; }
    const f = segs[i] ? Math.min(1, dist / segs[i]) : 0;
    cyc = [track[i][0] + (track[i + 1][0] - track[i][0]) * f, track[i][1] + (track[i + 1][1] - track[i][1]) * f];
    trackD = 'M' + [...track.slice(0, i + 1), cyc].map((p) => p.join(',')).join('L');
  }
  const leg = spring({frame: local - 8, fps, config: {damping: 200}});
  return (
    <AbsoluteFill>
      <svg width={W} height={H} style={{position: 'absolute'}}>
        {st.o && !track.length && (() => { const [x, y] = toScreen(st.o); const q = (local % 36) / 36;
          return <g><circle cx={x} cy={y} r={10 + q * 40} fill="none" stroke={color} strokeWidth={4} opacity={1 - q} />
            <circle cx={x} cy={y} r={9} fill={color} stroke="#fff" strokeWidth={3} /></g>; })()}
        {trackD && <path d={trackD} fill="none" stroke={color} strokeWidth={5} strokeDasharray="14 10" opacity={0.9} />}
        {cyc && <g transform={`translate(${cyc[0]},${cyc[1]}) rotate(${-local * 9})`}>
          <circle r={58} fill={color} opacity={0.18} />
          {[0, 120, 240].map((r) => <path key={r} transform={`rotate(${r})`} d="M0,0 C18,-8 34,-4 46,12" fill="none"
            stroke="#e9fbff" strokeWidth={9} strokeLinecap="round" />)}
          <circle r={11} fill="#0b2a44" stroke="#e9fbff" strokeWidth={4} />
        </g>}
      </svg>
      {labelsOn.map((n) => { const f = st.by[n]; const [x, y] = toScreen(WORLDPROJ(f.c));
        const o = interpolate(local, [st.act[n] + 4, st.act[n] + 16], [0, 1], clamp);
        const nm = (s.labels && s.labels[n]) || (lang === 'bn' ? f.bn || f.name : f.name);
        const txt = s.mode === 'heat' && s.heat && s.heat[n] !== undefined ? `${nm} ${bnDigits(s.heat[n], lang)}` : nm;
        return <div key={'l' + n} style={{position: 'absolute', left: x, top: y, transform: 'translate(-50%,-50%)', opacity: o,
          color: '#fff', fontFamily: font, fontSize: FS(26), fontWeight: 800, whiteSpace: 'nowrap',
          textShadow: '0 2px 6px rgba(0,0,0,0.95), 0 0 2px #000'}}>{txt}</div>; })}
      <div style={{position: 'absolute', left: 70, bottom: vertical ? 430 : 170, opacity: leg, transform: `translateX(${(1 - leg) * -40}px)`,
        background: T.panel, border: `1px solid ${T.edge}`, padding: '14px 20px', fontFamily: font, display: 'flex', gap: 16, alignItems: 'center'}}>
        <div style={{width: s.mode === 'heat' ? 120 : 34, height: 34, opacity: 0.9,
          background: s.mode === 'heat' ? `linear-gradient(90deg, ${T.choroLow}, ${color})` : color}} />
        <div>
          <div style={{color: T.text, fontSize: FS(28), fontWeight: 800}}>{s.legend || (lang === 'bn' ? ef.bn : ef.en)}</div>
          {Object.keys(st.act).length > 0 && <div style={{color: T.sub, fontSize: FS(24), marginTop: 2}}>
            {bnDigits(reached.length, lang)} {unitName}</div>}
        </div>
      </div>
    </AbsoluteFill>
  );
};