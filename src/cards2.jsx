// Infographic cards for production scripts: tiles, versus / split screen, pyramid, icon blocks, checklist,
// plus overlays: lower thirds, flashing tag, footnote.
import React from 'react';
import {spring, interpolate, Easing} from 'remotion';
import {countUp, MONO, FS} from './extras';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'};
const ease = Easing.bezier(0.65, 0, 0.35, 1);
const EN = '0123456789', BN = '০১২৩৪৫৬৭৮৯';
const numOf = (v) => { const m = String(v ?? '').replace(/[০-৯]/g, (d) => EN[BN.indexOf(d)]).replace(/,/g, '').match(/-?\d+(\.\d+)?/); return m ? parseFloat(m[0]) : 0; };
const sp = (local, fps, delay = 0) => spring({frame: local - delay, fps, config: {damping: 200}});

const Title = ({text, T, size, local, fps}) => text ? (
  <div style={{color: T.text, fontSize: FS(size), fontWeight: 800, marginBottom: 26, opacity: sp(local, fps, 2),
    transform: `translateY(${(1 - sp(local, fps, 2)) * 20}px)`}}>{text}</div>) : null;

export const TilesCard = ({s, local, fps, W, H, T, font}) => {
  const tiles = (s.tiles || []).slice(0, 4);
  const vertical = H > W;
  const cp = interpolate(local, [8, 50], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
  return (
    <div style={{position: 'absolute', left: W * 0.06, width: W * 0.88, top: vertical ? H * 0.22 : H * 0.22, fontFamily: font}}>
      <Title text={s.tiles_title} T={T} size={vertical ? 54 : 48} local={local} fps={fps} />
      <div style={{display: 'flex', flexDirection: vertical ? 'column' : 'row', gap: 26}}>
        {tiles.map((t, i) => {
          const a = sp(local, fps, 4 + i * 7);
          return (
            <div key={i} style={{flex: 1, background: T.panel, border: `1px solid ${T.edge}`, borderTop: `5px solid ${i === tiles.length - 1 ? T.accent : T.edge}`,
              padding: '26px 30px', opacity: a, transform: `translateY(${(1 - a) * 40}px)`}}>
              <div style={{fontFamily: MONO, fontSize: FS(18), letterSpacing: 3, color: T.sub, textTransform: 'uppercase', marginBottom: 8}}>{String(i + 1).padStart(2, '0')}</div>
              <div style={{color: T.accent, fontSize: FS(vertical ? 96 : 84), fontWeight: 900, lineHeight: 1.05}}>{countUp(t.value, cp)}</div>
              <div style={{color: T.text, fontSize: FS(34), fontWeight: 700, marginTop: 10, lineHeight: 1.3}}>{t.label}</div>
              {t.note ? <div style={{color: T.sub, fontSize: FS(24), marginTop: 6}}>{t.note}</div> : null}
            </div>);
        })}
      </div>
    </div>
  );
};

export const VersusCard = ({s, local, fps, W, H, T, font}) => {
  const v = s.versus || {};
  const items = [v.a || {}, v.b || {}];
  const max = Math.max(1, ...items.map((x) => numOf(x.value)));
  const vertical = H > W;
  const cp = interpolate(local, [8, 55], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
  const pulse = 1 + 0.04 * Math.max(0, 1 - Math.abs(local - 58) / 8);
  return (
    <div style={{position: 'absolute', left: W * 0.06, width: W * 0.88, top: vertical ? H * 0.2 : H * 0.2, fontFamily: font}}>
      <Title text={v.title} T={T} size={vertical ? 54 : 48} local={local} fps={fps} />
      <div style={{display: 'flex', flexDirection: vertical ? 'column' : 'row', gap: 30, alignItems: 'stretch'}}>
        {items.map((it, i) => {
          const a = sp(local, fps, 4 + i * 10);
          const hot = i === 1;
          return (
            <React.Fragment key={i}>
              {i === 1 && <div style={{alignSelf: 'center', color: T.sub, fontFamily: MONO, fontSize: FS(34), letterSpacing: 4, opacity: a}}>VS</div>}
              <div style={{flex: 1, background: T.panel, border: `1px solid ${hot ? T.accent : T.edge}`, padding: '30px 34px', opacity: a,
                transform: `translateX(${(1 - a) * (i ? 60 : -60)}px)`}}>
                <div style={{color: T.text, fontSize: FS(36), fontWeight: 700, lineHeight: 1.3, minHeight: 50}}>{it.label}</div>
                <div style={{color: hot ? T.accent : T.text, fontSize: FS(vertical ? 120 : 130), fontWeight: 900, lineHeight: 1.1,
                  transform: hot ? `scale(${pulse})` : 'none', transformOrigin: 'left center'}}>{countUp(it.value, cp)}</div>
                <div style={{height: 16, background: T.edge, marginTop: 14, opacity: 0.5}}>
                  <div style={{height: '100%', width: `${100 * cp * numOf(it.value) / max}%`, background: hot ? T.accent : T.sub}} />
                </div>
                {it.note ? <div style={{color: T.sub, fontSize: FS(24), marginTop: 10}}>{it.note}</div> : null}
              </div>
            </React.Fragment>);
        })}
      </div>
    </div>
  );
};

export const PyramidCard = ({s, local, fps, W, H, T, font}) => {
  const p = s.pyramid || {};
  const levels = (p.levels || []).slice(0, 5);          // bottom first
  const n = Math.max(1, levels.length);
  const vertical = H > W;
  const bw = W * (vertical ? 0.86 : 0.56), th = (vertical ? H * 0.42 : H * 0.52) / n;
  const x0 = (W - bw) / 2, yb = vertical ? H * 0.74 : H * 0.86;
  return (
    <div style={{position: 'absolute', inset: 0, fontFamily: font}}>
      <div style={{position: 'absolute', left: W * 0.06, top: vertical ? H * 0.18 : H * 0.12}}>
        <Title text={p.title} T={T} size={vertical ? 54 : 48} local={local} fps={fps} /></div>
      <svg width={W} height={H} style={{position: 'absolute', left: 0, top: 0}}>
        {levels.map((lv, i) => {
          const a = sp(local, fps, 8 + i * 14);
          const w0 = bw * (1 - i / n), w1 = bw * (1 - (i + 1) / n) + (i === n - 1 ? bw * 0.08 : 0);
          const y1 = yb - i * th, y0 = y1 - th + 6;
          const cx = W / 2;
          const d = `M${cx - w0 / 2},${y1} L${cx + w0 / 2},${y1} L${cx + w1 / 2},${y0} L${cx - w1 / 2},${y0} Z`;
          const top = i === n - 1;
          return (<g key={i} opacity={a} transform={`translate(0,${(1 - a) * 40})`}>
            <path d={d} fill={top ? T.accent : `rgba(255,255,255,${0.08 + 0.07 * i})`} stroke={top ? T.accent : T.edge} strokeWidth={2} />
          </g>);
        })}
      </svg>
      {levels.map((lv, i) => {
        const a = sp(local, fps, 14 + i * 14);
        const y1 = yb - i * th;
        const lab = typeof lv === 'object' ? lv : {label: lv};
        return (<div key={'t' + i} style={{position: 'absolute', left: 0, width: W, top: y1 - th + 6, height: th - 6, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', opacity: a, color: i === n - 1 ? '#fff' : T.text, textAlign: 'center'}}>
          <div style={{fontSize: FS(vertical ? 34 : 32), fontWeight: 800}}>{lab.label}</div>
          {lab.note ? <div style={{fontSize: FS(22), color: i === n - 1 ? '#fff' : T.sub}}>{lab.note}</div> : null}
        </div>);
      })}
    </div>
  );
};

export const BlocksCard = ({s, local, fps, W, H, T, font}) => {
  const b = s.blocks || {};
  const items = (b.items || []).slice(0, 4);
  const vertical = H > W;
  return (
    <div style={{position: 'absolute', left: W * 0.06, width: W * 0.88, top: vertical ? H * 0.2 : H * 0.18, fontFamily: font}}>
      <Title text={b.title} T={T} size={vertical ? 54 : 48} local={local} fps={fps} />
      <div style={{display: 'flex', flexDirection: vertical ? 'column' : 'row', gap: 24}}>
        {items.map((it, i) => {
          const a = sp(local, fps, 6 + i * 12);
          return (<div key={i} style={{flex: 1, background: T.panel, border: `1px solid ${T.edge}`, padding: '28px 26px', opacity: a,
            transform: `scale(${0.85 + 0.15 * a})`, textAlign: vertical ? 'left' : 'center', display: vertical ? 'flex' : 'block', gap: 22, alignItems: 'center'}}>
            <div style={{fontSize: FS(84), lineHeight: 1}}>{it.icon || '●'}</div>
            <div>
              <div style={{color: T.accent, fontFamily: MONO, fontSize: FS(20), letterSpacing: 3, marginTop: vertical ? 0 : 14}}>{String(i + 1).padStart(2, '0')}</div>
              <div style={{color: T.text, fontSize: FS(38), fontWeight: 800, marginTop: 6}}>{it.title}</div>
              {it.text ? <div style={{color: T.sub, fontSize: FS(26), marginTop: 8, lineHeight: 1.35}}>{it.text}</div> : null}
            </div>
          </div>);
        })}
      </div>
    </div>
  );
};

export const ChecklistCard = ({s, local, fps, W, H, T, font}) => {
  const c = s.checklist || {};
  const items = (c.items || []).slice(0, 6);
  const vertical = H > W;
  return (
    <div style={{position: 'absolute', left: W * (vertical ? 0.06 : 0.2), width: W * (vertical ? 0.88 : 0.6), top: vertical ? H * 0.22 : H * 0.18,
      fontFamily: font, background: T.panel, border: `1px solid ${T.edge}`, padding: '34px 44px'}}>
      <Title text={c.title} T={T} size={vertical ? 52 : 46} local={local} fps={fps} />
      {items.map((it, i) => {
        const st = 10 + i * 16;
        const a = sp(local, fps, st);
        const chk = interpolate(local, [st + 8, st + 20], [0, 1], clamp);
        return (<div key={i} style={{display: 'flex', alignItems: 'center', gap: 22, margin: '16px 0', opacity: a, transform: `translateX(${(1 - a) * 30}px)`}}>
          <svg width={52} height={52} style={{flex: '0 0 auto'}}>
            <rect x={3} y={3} width={46} height={46} fill="none" stroke={T.edge} strokeWidth={3} />
            <path d="M12 27 L22 37 L41 15" fill="none" stroke={T.accent} strokeWidth={6} strokeLinecap="round" strokeLinejoin="round"
              pathLength={1} strokeDasharray={1} strokeDashoffset={1 - chk} />
          </svg>
          <div style={{color: T.text, fontSize: FS(40), fontWeight: 700}}>{it}</div>
        </div>);
      })}
    </div>
  );
};

// ---- overlays usable on any scene ----
export const LowerThirds = ({s, local, fps, frames, W, H, T, font}) => {
  const L = (s.lower || []).slice(0, 4);
  if (!L.length) return null;
  const seg = frames / L.length;
  const i = Math.min(L.length - 1, Math.floor(local / seg));
  const l0 = local - i * seg;
  const a = Math.min(sp(l0, fps, 4), interpolate(l0, [seg - 10, seg], [1, 0], clamp));
  const it = L[i];
  const vertical = H > W;
  return (
    <div style={{position: 'absolute', left: 70, bottom: vertical ? 470 : 190, fontFamily: font, opacity: a, transform: `translateX(${(1 - a) * -60}px)`,
      display: 'flex', alignItems: 'stretch'}}>
      <div style={{width: 10, background: T.accent}} />
      <div style={{background: T.panel, padding: '14px 26px', border: `1px solid ${T.edge}`, borderLeft: 'none'}}>
        <div style={{color: T.text, fontSize: FS(38), fontWeight: 800}}>{it.name}</div>
        {it.role ? <div style={{color: T.sub, fontSize: FS(26), marginTop: 4}}>{it.role}</div> : null}
      </div>
    </div>
  );
};

export const TagFlash = ({s, local, W, H, T}) => {
  if (!s.tag_flash) return null;
  const on = local < 70 ? (Math.floor(local / 6) % 2 === 0 ? 1 : 0.25) : 1;
  return (
    <div style={{position: 'absolute', right: 60, top: H > W ? 200 : 110, background: T.accent, color: '#fff', fontFamily: MONO,
      fontSize: FS(28), letterSpacing: 4, padding: '10px 18px', opacity: on * interpolate(local, [0, 6], [0, 1], clamp), fontWeight: 700}}>
      ■ {s.tag_flash}</div>
  );
};

export const Footnote = ({s, local, W, H, T, font}) => {
  if (!s.note) return null;
  return (<div style={{position: 'absolute', right: 70, bottom: H > W ? 400 : 140, color: T.sub, fontFamily: font, fontSize: FS(24),
    opacity: interpolate(local, [30, 45], [0, 1], clamp), maxWidth: W * 0.5, textAlign: 'right'}}>{s.note}</div>);
};