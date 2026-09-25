import React, {useMemo} from 'react';
import {AbsoluteFill, Sequence, Html5Audio, Img, staticFile, useCurrentFrame, useVideoConfig,
  interpolate, interpolateColors, spring, Easing} from 'remotion';
import {features, findCountry, sceneCamera, fitScale, anchor, lonlat, WORLD_CAMERA, projection} from './geo';
import {buildScenes} from './scenes';
import {TilesCard, VersusCard, PyramidCard, BlocksCard, ChecklistCard, LowerThirds, TagFlash, Footnote} from './cards2';
import {THEMES, TXT, FS, bgTheme, useFontFiles, GlobeLayer, choroColors, ChoroLegend, ChartCard, BrollLayer, HudOverlay, countUp, percentOf, SpreadWorld, SpreadHud, useAdm} from './extras';

const PALETTE = {
  red: '#e63946', amber: '#f4a261', teal: '#2a9d8f', blue: '#4895ef', violet: '#9d4edd',
  green: '#52b788', yellow: '#ffd166', pink: '#ef476f', grey: '#8d99ae',
  লাল: '#e63946', কমলা: '#f4a261', ফিরোজা: '#2a9d8f', নীল: '#4895ef', বেগুনি: '#9d4edd',
  সবুজ: '#52b788', হলুদ: '#ffd166', গোলাপি: '#ef476f', ধূসর: '#8d99ae',
};
const AUTO = ['red', 'amber', 'teal', 'blue', 'violet'];
const col = (c) => PALETTE[String(c || '').trim().toLowerCase()] || PALETTE[String(c || '').trim()] || (String(c || '').startsWith('#') ? c : PALETTE.red);

const THEME = {
  bg0: '#07131f', bg1: '#0d2236', land: '#1b3148', edge: '#4a6784', text: '#ffffff',
  sub: '#a9c1d6', accent: '#ffd166', panel: 'rgba(6,16,28,0.8)',
};
const CARD_TYPES = ['title', 'stat', 'bullets', 'quote', 'timeline', 'compare', 'intro', 'outro', 'chart', 'tiles', 'versus', 'pyramid', 'blocks', 'checklist'];
const OWN_TITLE = ['title', 'intro', 'outro', 'chart', 'tiles', 'versus', 'pyramid', 'blocks', 'checklist'];
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'};
const ease = Easing.bezier(0.65, 0, 0.35, 1);
const flagSrc = (c) => (c && c.iso2 ? staticFile(`flags/${c.iso2}.svg`) : null);

const Flag = ({c, h = 30, style}) => {
  const src = flagSrc(c);
  if (!src) return null;
  return <Img src={src} style={{height: h, width: h * 4 / 3, objectFit: 'cover', borderRadius: 3,
    boxShadow: '0 2px 8px rgba(0,0,0,.6)', ...style}} />;
};

const highlightMap = (s) => {
  if (s?.type === 'choropleth' && s.values && Object.keys(s.values).length) return choroColors(s, THEME, interpolateColors);
  const m = {};
  const h = s?.highlight || {};
  if (Array.isArray(h)) h.forEach((k, j) => { const c = findCountry(k); if (c) m[c.iso] = col(AUTO[j % 5]); });
  else Object.entries(h).forEach(([k, v]) => { const c = findCountry(k); if (c) m[c.iso] = col(v); });
  if (s?.type === 'compare' && s.compare) {
    const a = findCountry(s.compare.a), b = findCountry(s.compare.b);
    if (a && !m[a.iso]) m[a.iso] = PALETTE.red;
    if (b && !m[b.iso]) m[b.iso] = PALETTE.blue;
  }
  return m;
};

const cameraFor = (s, lastCam) => {
  if (s.type === 'intro') return WORLD_CAMERA;
  if (s.type === 'spread' && s.zoom_bbox) {
    const [x0, y0] = projection([s.zoom_bbox[0], s.zoom_bbox[3]]), [x1, y1] = projection([s.zoom_bbox[2], s.zoom_bbox[1]]);
    return {cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, w: Math.max(2, (x1 - x0) * 0.92), h: Math.max(2, (y1 - y0) * 0.92)};
  }
  if (s.type === 'outro') return sceneCamera({focus: s.lastFocus || [], zoom: 0.3}) || WORLD_CAMERA;
  if (s.type === 'compare' && s.compare && !(s.focus || []).length)
    return sceneCamera({focus: [s.compare.a, s.compare.b]}) || lastCam;
  return sceneCamera(s) || lastCam;
};

const useTimeline = (scenes, fps) => useMemo(() => {
  let t = 0;
  const out = [];
  let lastCam = WORLD_CAMERA;
  scenes.forEach((s, i) => {
    const frames = Math.max(1, Math.round((s.duration || 5) * fps));
    const cam = cameraFor(s, lastCam);
    out.push({s, i, from: t, frames, cam, prevCam: lastCam, moves: cam !== lastCam && i > 0});
    lastCam = cam;
    t += frames;
  });
  return {items: out, total: t};
}, [scenes, fps]);

// --- map ------------------------------------------------------------------------
const MapLayer = ({tl, frame, W, H, lang, fps, font, adm = {}}) => {
  const {items} = tl;
  let idx = items.findIndex((it) => frame >= it.from && frame < it.from + it.frames);
  if (idx < 0) idx = items.length - 1;
  const cur = items[idx];
  const prev = items[idx - 1];
  const local = frame - cur.from;
  if (cur.s.type === 'globe') {
    return <GlobeLayer s={cur.s} prevS={prev ? prev.s : null} local={local} W={W} H={H} T={THEME}
      hl={highlightMap(cur.s)} lang={lang} font={font} />;
  }

  const moveFrames = Math.min(45, Math.round(cur.frames * 0.4));
  const t = interpolate(local, [0, moveFrames], [0, 1], {...clamp, easing: ease});
  const kA = fitScale(cur.prevCam, W, H), kB = fitScale(cur.cam, W, H);
  const push = interpolate(local, [moveFrames, cur.frames], [1, 1.06], clamp);
  const k = Math.exp(Math.log(kA) + (Math.log(kB) - Math.log(kA)) * t) * push;
  const cx = cur.prevCam.cx + (cur.cam.cx - cur.prevCam.cx) * t;
  const cy = cur.prevCam.cy + (cur.cam.cy - cur.prevCam.cy) * t;
  const toScreen = (p) => [(p[0] - cx) * k + W / 2, (p[1] - cy) * k + H / 2];

  const hCur = highlightMap(cur.s);
  const hPrev = prev ? highlightMap(prev.s) : {};
  const fade = interpolate(local, [0, 18], [0, 1], clamp);
  const dim = CARD_TYPES.includes(cur.s.type) ? (cur.s.type === 'intro' || cur.s.type === 'outro' ? 0.35 : 0.55) : 0;

  const labels = [];
  for (const c of features) {
    const on = hCur[c.iso];
    const [x, y] = toScreen(c.label);
    if (x < 40 || x > W - 40 || y < 60 || y > H - 60) continue;
    const bigEnough = c.rank <= (k > 1.5 ? 6 : k > 0.6 ? 4 : 2);
    if (!on && !bigEnough) continue;
    labels.push({c, x, y, on});
  }
  // text cards sit on a dimmed map: hide country labels so they never clash with the card
  const showLabels = !CARD_TYPES.includes(cur.s.type) && cur.s.type !== 'spread';

  return (
    <AbsoluteFill>
      <svg width={W} height={H} style={{position: 'absolute'}}>
        <defs>
          <radialGradient id="ocean" cx="50%" cy="45%" r="75%">
            <stop offset="0%" stopColor={THEME.bg1} />
            <stop offset="100%" stopColor={THEME.bg0} />
          </radialGradient>
        </defs>
        <rect width={W} height={H} fill="url(#ocean)" />
        <g transform={`translate(${W / 2},${H / 2}) scale(${k}) translate(${-cx},${-cy})`}>
          {features.map((c) => {
            const a = hPrev[c.iso] || THEME.land;
            const b = hCur[c.iso] || THEME.land;
            const fill = a === b ? b : interpolateColors(fade, [0, 1], [a, b]);
            return <path key={c.iso + c.name} d={c.d} fill={fill} stroke={THEME.edge}
              strokeWidth={hCur[c.iso] ? 1.6 : 0.7} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />;
          })}
          {cur.s.type === 'spread' && <SpreadWorld s={cur.s} adm={adm[cur.s.adm]} local={local} frames={cur.frames} T={THEME} />}
        </g>
        {(cur.s.arrows || []).map((a, j) => {
          const A = anchor(a.from), B = anchor(a.to);
          if (!A || !B) return null;
          const [x1, y1] = toScreen(A), [x2, y2] = toScreen(B);
          const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
          const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy) || 1;
          const bend = Math.min(len * 0.25, 160);
          const qx = mx - (dy / len) * bend, qy = my + (dx / len) * bend;
          const start = 12 + j * 14;
          const p = interpolate(local, [start, start + 35], [0, 1], {...clamp, easing: ease});
          const L = len * 1.25;
          const ang = Math.atan2(y2 - qy, x2 - qx);
          const c = col(a.color || 'yellow');
          return (
            <g key={'ar' + j}>
              <path d={`M${x1},${y1} Q${qx},${qy} ${x2},${y2}`} fill="none" stroke={c} strokeWidth={6}
                strokeLinecap="round" strokeDasharray={L} strokeDashoffset={L * (1 - p)} />
              {p > 0.97 && <polygon fill={c} transform={`translate(${x2},${y2}) rotate(${ang * 180 / Math.PI})`}
                points="0,0 -26,-13 -26,13" />}
              {a.label && p > 0.5 && <text x={qx} y={qy - 14} fill={c} fontSize={FS(30)} fontWeight={700}
                textAnchor="middle" style={{paintOrder: 'stroke'}} stroke={THEME.bg0} strokeWidth={6}>{a.label}</text>}
            </g>
          );
        })}
        {(cur.s.points || []).map((pt, j) => {
          const P = lonlat(+pt.lon, +pt.lat);
          if (!P) return null;
          const [x, y] = toScreen(P);
          const pop = spring({frame: local - 10 - j * 8, fps, config: {damping: 12}});
          const pulse = (local % 40) / 40;
          return (
            <g key={'pt' + j} opacity={Math.min(1, pop)}>
              <circle cx={x} cy={y} r={10 + pulse * 30} fill="none" stroke={THEME.accent} strokeWidth={3} opacity={1 - pulse} />
              <circle cx={x} cy={y} r={9 * pop} fill={THEME.accent} stroke={THEME.bg0} strokeWidth={3} />
              <text x={x + 18} y={y + 10} fill={THEME.text} fontSize={FS(30)} fontWeight={700}
                style={{paintOrder: 'stroke'}} stroke={THEME.bg0} strokeWidth={7}>{pt.name}</text>
            </g>
          );
        })}
      </svg>
      {cur.s.type === 'spread' && <SpreadHud s={cur.s} adm={adm[cur.s.adm]} local={local} frames={cur.frames} fps={fps}
        toScreen={toScreen} W={W} H={H} T={THEME} font={font} lang={lang} />}
      {showLabels && labels.map(({c, x, y, on}) => (
        <div key={'lb' + c.iso + c.name} style={{position: 'absolute', left: x, top: y, transform: 'translate(-50%,-50%)',
          display: 'flex', alignItems: 'center', gap: 10, opacity: on ? Math.max(fade, 0.001) : 1,
          color: on ? THEME.text : THEME.sub, fontSize: FS(on ? 36 : 22), fontWeight: on ? 800 : 500,
          textShadow: THEME.shadow, whiteSpace: 'nowrap', letterSpacing: on ? 0.5 : 1}}>
          {on && <Flag c={c} h={30} />}
          {lang === 'bn' ? c.bn : (on ? c.name : c.name.toUpperCase())}
        </div>
      ))}
      <AbsoluteFill style={{backgroundColor: `rgba(${THEME.dim},${dim * interpolate(local, [0, 15], [0, 1], clamp)})`}} />
    </AbsoluteFill>
  );
};

// --- overlays ----------------------------------------------------------------------
const Headline = ({text, local, fps, font, W}) => {
  if (!text) return null;
  const s = spring({frame: local - 6, fps, config: {damping: 200}});
  return (
    <div style={{position: 'absolute', left: 70, top: 60, display: 'flex', alignItems: 'stretch', opacity: s,
      transform: `translateX(${(1 - s) * -40}px)`, fontFamily: font}}>
      <div style={{width: 10, background: THEME.accent, borderRadius: 3}} />
      <div style={{background: THEME.panel, color: THEME.text, fontSize: FS(46), fontWeight: 800, padding: '14px 26px',
        maxWidth: Math.min(1100, W - 200), lineHeight: 1.3}}>{text}</div>
    </div>
  );
};

const Caption = ({cues, local, fps, W, H, font}) => {
  const hud = THEME.accent === THEMES.hud.accent;
  const t = local / fps;
  const cue = (cues || []).find((c) => t >= c.start && t < c.end);
  if (!cue) return null;
  const vertical = H > W;
  return (
    <div style={{position: 'absolute', bottom: vertical ? 260 : 70, left: 0, width: W, display: 'flex', justifyContent: 'center'}}>
      <div style={{background: THEME.capBg, color: THEME.capText, fontSize: FS(vertical ? 48 : 40), fontWeight: 600, padding: '12px 28px',
        borderRadius: hud ? 0 : 10, borderLeft: hud ? `6px solid ${THEME.accent}` : 'none', maxWidth: W * 0.86, textAlign: 'center', lineHeight: 1.45, fontFamily: font}}>{cue.text}</div>
    </div>
  );
};

const Card = ({s, local, fps, W, H, font, lang, channel}) => {
  const a = spring({frame: local - 4, fps, config: {damping: 200}});
  const base = {position: 'absolute', fontFamily: font, color: THEME.text, opacity: a};
  const vertical = H > W;
  const center = {...base, left: 0, top: 0, width: W, height: H, display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center', textAlign: 'center'};

  if (s.type === 'intro') {
    const line = interpolate(local, [8, 30], [0, 1], {...clamp, easing: ease});
    const letters = interpolate(local, [4, 34], [0, 1], clamp);
    const out = interpolate(local, [s.duration * fps - 12, s.duration * fps], [1, 0], clamp);
    return (
      <div style={{...center, opacity: out}}>
        <div style={{fontSize: FS(vertical ? 90 : 120), fontWeight: 900, letterSpacing: interpolate(letters, [0, 1], [40, 8]),
          opacity: letters, textShadow: '0 8px 40px rgba(0,0,0,.8)'}}>{channel}</div>
        <div style={{width: 420 * line, height: 8, background: THEME.accent, borderRadius: 4, marginTop: 24}} />
      </div>
    );
  }
  if (s.type === 'outro') {
    const b = spring({frame: local - 18, fps, config: {damping: 14}});
    return (
      <div style={center}>
        <div style={{fontSize: FS(vertical ? 64 : 76), fontWeight: 900}}>{lang === 'bn' ? 'দেখার জন্য ধন্যবাদ' : 'Thanks for watching'}</div>
        <div style={{fontSize: FS(44), color: THEME.sub, marginTop: 18}}>{channel}</div>
        <div style={{marginTop: 50, background: '#e62117', color: '#fff', fontSize: FS(40), fontWeight: 800,
          padding: '18px 46px', borderRadius: 12, transform: `scale(${b})`}}>
          {lang === 'bn' ? 'সাবস্ক্রাইব করুন' : 'SUBSCRIBE'}</div>
      </div>
    );
  }
  if (s.type === 'title') return (
    <div style={{...center, transform: `scale(${0.94 + a * 0.06})`}}>
      <div style={{fontSize: FS(vertical ? 80 : 96), fontWeight: 900, maxWidth: W * 0.85, lineHeight: 1.25, textShadow: '0 6px 30px rgba(0,0,0,.7)'}}>{s.title || s.headline}</div>
      <div style={{width: 160 * a, height: 8, background: THEME.accent, margin: '30px 0', borderRadius: 4}} />
      {s.subtitle && <div style={{fontSize: FS(44), color: THEME.sub, maxWidth: W * 0.75, lineHeight: 1.4}}>{s.subtitle}</div>}
    </div>
  );
  if (s.type === 'stat') {
    const cp = interpolate(local, [6, 48], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
    const pct = percentOf(s.stat?.value);
    const R0 = 215, C = 2 * Math.PI * R0;
    const num = <div style={{fontSize: FS(pct !== null ? 132 : (vertical ? 140 : 170)), fontWeight: 900, color: THEME.accent, lineHeight: 1.1,
      transform: `translateY(${(1 - a) * 40}px) scale(${1 + 0.06 * Math.max(0, 1 - Math.abs(local - 50) / 8)})`}}>{countUp(s.stat?.value, cp)}</div>;
    return (
    <div style={center}>
      {pct !== null ? (
        <div style={{position: 'relative', width: R0 * 2 + 40, height: R0 * 2 + 40, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
          <svg width={R0 * 2 + 40} height={R0 * 2 + 40} style={{position: 'absolute', left: 0, top: 0, opacity: a}}>
            <circle cx={R0 + 20} cy={R0 + 20} r={R0} fill="none" stroke={THEME.edge} strokeWidth={14} opacity={0.5} />
            <circle cx={R0 + 20} cy={R0 + 20} r={R0} fill="none" stroke={THEME.accent} strokeWidth={14} strokeLinecap="round"
              strokeDasharray={C} strokeDashoffset={C * (1 - cp * pct / 100)} transform={`rotate(-90 ${R0 + 20} ${R0 + 20})`} />
          </svg>
          {num}
        </div>) : num}
      <div style={{fontSize: FS(50), fontWeight: 600, maxWidth: W * 0.75, marginTop: 20, lineHeight: 1.4}}>{s.stat?.label}</div>
      {s.stat?.source && <div style={{fontSize: FS(26), color: THEME.sub, marginTop: 24}}>{s.stat.source}</div>}
    </div>
  );}
  if (s.type === 'bullets') return (
    <div style={{...base, right: vertical ? 60 : 80, left: vertical ? 60 : undefined, top: vertical ? 420 : 180,
      width: vertical ? undefined : Math.min(900, W * 0.5), background: THEME.panel,
      borderLeft: `8px solid ${THEME.accent}`, padding: '34px 40px', borderRadius: 8}}>
      {(s.bullets || []).map((b, j) => {
        const bj = spring({frame: local - 12 - j * 18, fps, config: {damping: 200}});
        return <div key={j} style={{fontSize: FS(42), lineHeight: 1.45, marginBottom: 22, opacity: bj,
          transform: `translateX(${(1 - bj) * 30}px)`, display: 'flex', gap: 18}}>
          <span style={{color: THEME.accent, fontWeight: 900}}>{j + 1}</span><span>{b}</span></div>;
      })}
    </div>
  );
  if (s.type === 'quote') return (
    <div style={{...base, left: W * 0.1, top: H * 0.25, width: W * 0.8, textAlign: 'center'}}>
      <div style={{fontSize: FS(60), fontWeight: 700, lineHeight: 1.45}}>“{typeof s.quote === 'string' ? s.quote : s.quote?.text}”</div>
      <div style={{fontSize: FS(36), color: THEME.accent, marginTop: 30}}>{(typeof s.quote === 'object' && s.quote?.by) || s.by}</div>
    </div>
  );
  if (s.type === 'timeline') {
    const ev = (s.events || []).slice(0, 6);
    const n = Math.max(ev.length, 1);
    const x0 = W * 0.08, x1 = W * 0.92;
    const lineP = interpolate(local, [6, 30], [0, 1], {...clamp, easing: ease});
    const y = vertical ? H * 0.5 : H * 0.55;
    if (vertical) {
      // vertical timeline for Shorts
      const top = H * 0.24, bot = H * 0.78;
      return (
        <div style={{...base, left: 0, top: 0, width: W, height: H}}>
          <div style={{position: 'absolute', left: 120, top, width: 6, height: (bot - top) * lineP, background: THEME.accent, borderRadius: 3}} />
          {ev.map((e, j) => {
            const yy = top + (bot - top) * (n === 1 ? 0.5 : j / (n - 1));
            const pj = spring({frame: local - 20 - j * 14, fps, config: {damping: 200}});
            return <div key={j} style={{position: 'absolute', left: 100, top: yy - 22, display: 'flex', gap: 30, opacity: pj,
              transform: `translateX(${(1 - pj) * 30}px)`, alignItems: 'flex-start', width: W - 180}}>
              <div style={{width: 46, height: 46, borderRadius: 23, background: THEME.accent, border: `6px solid ${THEME.bg0}`, flex: '0 0 auto'}} />
              <div><div style={{fontSize: FS(44), fontWeight: 900, color: THEME.accent}}>{e.date}</div>
                <div style={{fontSize: FS(36), lineHeight: 1.35}}>{e.text}</div></div></div>;
          })}
        </div>
      );
    }
    return (
      <div style={{...base, left: 0, top: 0, width: W, height: H}}>
        <div style={{position: 'absolute', left: x0, top: y - 3, width: (x1 - x0) * lineP, height: 6, background: THEME.accent, borderRadius: 3}} />
        {ev.map((e, j) => {
          const x = x0 + (x1 - x0) * (n === 1 ? 0.5 : (j + 0.5) / n);
          const pj = spring({frame: local - 20 - j * 14, fps, config: {damping: 200}});
          const up = j % 2 === 0;
          return (
            <div key={j} style={{opacity: pj}}>
              <div style={{position: 'absolute', left: x - 20, top: y - 20, width: 40, height: 40, borderRadius: 20,
                background: THEME.accent, border: `6px solid ${THEME.bg0}`, transform: `scale(${pj})`}} />
              <div style={{position: 'absolute', left: x - 170, width: 340, textAlign: 'center',
                top: up ? y - 190 : y + 40, transform: `translateY(${(1 - pj) * (up ? -20 : 20)}px)`}}>
                <div style={{fontSize: FS(46), fontWeight: 900, color: THEME.accent}}>{e.date}</div>
                <div style={{fontSize: FS(30), lineHeight: 1.35, marginTop: 6}}>{e.text}</div>
              </div>
            </div>
          );
        })}
      </div>
    );
  }
  if (s.type === 'compare' && s.compare) {
    const A = findCountry(s.compare.a), B = findCountry(s.compare.b);
    const nm = (c, raw) => (c ? (lang === 'bn' ? c.bn : c.name) : raw);
    const rows = (s.compare.rows || []).slice(0, 5);
    const w = Math.min(1300, W * 0.9);
    return (
      <div style={{...base, left: (W - w) / 2, top: vertical ? H * 0.2 : 170, width: w, background: THEME.panel,
        borderRadius: 14, padding: '30px 40px', border: `1px solid ${THEME.edge}`}}>
        <div style={{display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr', alignItems: 'center', gap: 20,
          paddingBottom: 18, borderBottom: `2px solid ${THEME.edge}`}}>
          <div />
          {[[A, s.compare.a, PALETTE.red], [B, s.compare.b, PALETTE.blue]].map(([c, raw, cc], j) => (
            <div key={j} style={{display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 14}}>
              <Flag c={c} h={42} />
              <span style={{fontSize: FS(44), fontWeight: 900, color: cc}}>{nm(c, raw)}</span>
            </div>
          ))}
        </div>
        {rows.map((r, j) => {
          const pj = spring({frame: local - 16 - j * 16, fps, config: {damping: 200}});
          return (
            <div key={j} style={{display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr', gap: 20, alignItems: 'center',
              padding: '18px 0', borderBottom: `1px solid rgba(74,103,132,.5)`, opacity: pj,
              transform: `translateY(${(1 - pj) * 16}px)`}}>
              <div style={{fontSize: FS(34), color: THEME.sub}}>{r.label}</div>
              <div style={{fontSize: FS(44), fontWeight: 800, textAlign: 'center'}}>{r.a}</div>
              <div style={{fontSize: FS(44), fontWeight: 800, textAlign: 'center'}}>{r.b}</div>
            </div>
          );
        })}
        {s.compare.source && <div style={{fontSize: FS(24), color: THEME.sub, marginTop: 16}}>{s.compare.source}</div>}
      </div>
    );
  }
  return null;
};

// --- composition ------------------------------------------------------------------------
export const Explainer = (props) => {
  const {lang = 'bn', channel = '', music = null, musicVolume = 0.1, captions = true, sfx = true,
    font = "'Hind Siliguri','Noto Sans Bengali','Nirmala UI',Arial,sans-serif"} = props;
  const scenes = useMemo(() => buildScenes(props), [props]);
  const frame = useCurrentFrame();
  const {fps, width: W, height: H, durationInFrames} = useVideoConfig();
  const tl = useTimeline(scenes, fps);
  useFontFiles(props.fontFiles);
  const adm = useAdm(scenes);
  const look = props.look || 'classic';
  Object.assign(THEME, THEMES[look] || THEMES.classic);
  if (props.bg && look !== 'light') Object.assign(THEME, bgTheme(props.bg));
  TXT.k = props.textScale || 1.25;
  const fontT = props.fontText ? `'${props.fontText}','Noto Sans Bengali','Nirmala UI',sans-serif` : font;
  const fontC = props.fontCaption ? `'${props.fontCaption}','Noto Sans Bengali','Nirmala UI',sans-serif` : fontT;
  if (!scenes.length) return <AbsoluteFill style={{background: THEME.bg0}} />;
  const cur = tl.items.find((it) => frame >= it.from && frame < it.from + it.frames) || tl.items[tl.items.length - 1];
  const hideChannel = ['intro', 'outro'].includes(cur.s.type);

  return (
    <AbsoluteFill style={{fontFamily: fontT, background: THEME.bg0}}>
      <MapLayer tl={tl} frame={frame} W={W} H={H} lang={lang} fps={fps} font={fontT} adm={adm} />
      {tl.items.map((it) => (
        <Sequence key={it.i} from={it.from} durationInFrames={it.frames}>
          <SceneOverlay it={it} fps={fps} W={W} H={H} font={fontT} capFont={fontC} captions={captions} lang={lang} channel={channel} look={look} />
          {it.s.audio && <Html5Audio src={staticFile(it.s.audio)} />}
          {sfx && it.moves && it.s.type !== 'outro' && <Html5Audio src={staticFile('sfx/whoosh.wav')} volume={0.28} />}
          {sfx && (it.s.sfx || []).map((x, j) => {
            const at = Math.round((x.at || 0) * fps);
            const len = Math.max(10, it.frames - at);
            return (<Sequence key={'fx' + j} from={at} durationInFrames={len}>
              <Html5Audio src={staticFile(x.src)} loop={!!x.loop}
                volume={(f) => (x.vol || 0.3) * (x.loop ? Math.min(1, f / 15, Math.max(0, (len - f) / 20)) : 1)} />
            </Sequence>);
          })}
          {sfx && it.s.type === 'intro' && <Html5Audio src={staticFile('sfx/impact.wav')} volume={0.6} />}
          {sfx && (it.s.points || []).map((p, j) => (
            <Sequence key={'pop' + j} from={10 + j * 8} durationInFrames={10}>
              <Html5Audio src={staticFile('sfx/pop.wav')} volume={0.25} />
            </Sequence>
          ))}
        </Sequence>
      ))}
      {music && <Html5Audio src={staticFile(music)} loop
        volume={(f) => {
          // louder where nobody is speaking (intro and outro), softer under the voice
          const b = props.musicBoost || 1;
          const intro = tl.items.find((x) => x.s.type === 'intro');
          const outro = tl.items.find((x) => x.s.type === 'outro');
          let k = 1;
          if (intro && f < intro.from + intro.frames) k = interpolate(f, [intro.from + intro.frames - 20, intro.from + intro.frames], [b, 1], clamp);
          if (outro && f >= outro.from - 20) k = interpolate(f, [outro.from - 20, outro.from + 10], [1, b], clamp);
          return Math.min(1, musicVolume * k) * Math.min(1, f / 45, Math.max(0, (durationInFrames - f) / 90));
        }} />}
      {look === 'hud' && !hideChannel && <HudOverlay W={W} H={H} T={THEME} channel={channel} cur={cur} frame={frame} fps={fps}
        year={props.year || new Date().getFullYear()} dataNote={props.dataNote} />}
      {look !== 'hud' && props.dataNote && !hideChannel && <div style={{position: 'absolute', left: 60, bottom: 22, color: THEME.sub,
        fontSize: FS(20), opacity: 0.85}}>{props.dataNote}</div>}
      {look !== 'hud' && channel && !hideChannel && <div style={{position: 'absolute', right: 60, top: 56, color: 'rgba(255,255,255,0.75)', fontSize: FS(28),
        fontWeight: 700, letterSpacing: 2, color: THEME.sub}}>{channel}</div>}
      <div style={{position: 'absolute', left: 0, bottom: 0, height: 6, width: W * frame / durationInFrames,
        background: THEME.accent, opacity: 0.85}} />
    </AbsoluteFill>
  );
};

const SceneOverlay = ({it, fps, W, H, font, capFont, captions, lang, channel, look}) => {
  const local = useCurrentFrame();
  const s = it.s;
  const out = s.type === 'outro' ? 1 : interpolate(local, [it.frames - 8, it.frames], [1, 0], clamp);
  return (
    <AbsoluteFill style={{opacity: out}}>
      {s.type === 'broll' && s.broll_file && <BrollLayer s={s} local={local} frames={it.frames} T={THEME} look={look} W={W} H={H} />}
      {!OWN_TITLE.includes(s.type) && <Headline text={s.headline} local={local} fps={fps} font={font} W={W} />}
      <Card s={s} local={local} fps={fps} W={W} H={H} font={font} lang={lang} channel={channel} />
      {s.type === 'tiles' && <TilesCard s={s} local={local} fps={fps} W={W} H={H} T={THEME} font={font} />}
      {s.type === 'versus' && <VersusCard s={s} local={local} fps={fps} W={W} H={H} T={THEME} font={font} />}
      {s.type === 'pyramid' && <PyramidCard s={s} local={local} fps={fps} W={W} H={H} T={THEME} font={font} />}
      {s.type === 'blocks' && <BlocksCard s={s} local={local} fps={fps} W={W} H={H} T={THEME} font={font} />}
      {s.type === 'checklist' && <ChecklistCard s={s} local={local} fps={fps} W={W} H={H} T={THEME} font={font} />}
      <LowerThirds s={s} local={local} fps={fps} frames={it.frames} W={W} H={H} T={THEME} font={font} />
      <TagFlash s={s} local={local} W={W} H={H} T={THEME} />
      <Footnote s={s} local={local} W={W} H={H} T={THEME} font={font} />
      {s.type === 'chart' && <ChartCard s={s} local={local} fps={fps} W={W} H={H} T={THEME} font={font} look={look} lang={lang} />}
      {s.type === 'choropleth' && <ChoroLegend s={s} T={THEME} W={W} H={H} local={local} fps={fps} lang={lang} font={font} />}
      {captions && <Caption cues={s.cues} local={local} fps={fps} W={W} H={H} font={capFont || font} />}
    </AbsoluteFill>
  );
};
