import {AbsoluteFill, useCurrentFrame, interpolate, spring, useVideoConfig} from 'remotion';
import {geoMercator, geoPath} from 'd3-geo';
import {feature} from 'topojson-client';
import world from 'world-atlas/countries-50m.json';

const countries = feature(world, world.objects.countries).features;
const HIGHLIGHT = {'050': '#e63946', '104': '#f4a261', '356': '#2a9d8f'}; // Bangladesh, Myanmar, India

export const MapTest = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const zoom = interpolate(frame, [0, 120], [700, 2600], {extrapolateRight: 'clamp'});
  const proj = geoMercator().center([90.3, 23.7]).scale(zoom).translate([960, 560]);
  const path = geoPath(proj);
  const title = spring({frame: frame - 20, fps, config: {damping: 200}});
  return (
    <AbsoluteFill style={{backgroundColor: '#0b1d2e'}}>
      <svg width={1920} height={1080}>
        {countries.map((c) => (
          <path key={c.id + (c.properties?.name || '')} d={path(c) || ''}
            fill={HIGHLIGHT[c.id] ? HIGHLIGHT[c.id] : '#1f3a52'}
            fillOpacity={HIGHLIGHT[c.id] ? interpolate(frame, [30, 60], [0.2, 0.9], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 1}
            stroke="#6b8aa6" strokeWidth={0.8} />
        ))}
      </svg>
      <div style={{position: 'absolute', left: 90, top: 70, color: 'white', fontFamily: 'Arial', fontSize: 72, fontWeight: 700,
        opacity: title, transform: `translateY(${(1 - title) * 30}px)`}}>
        Bay of Bengal
      </div>
      <div style={{position: 'absolute', left: 92, top: 160, color: '#a9c1d6', fontFamily: 'Arial', fontSize: 34, opacity: title}}>
        Pipeline test: Bangladesh, Myanmar, India
      </div>
    </AbsoluteFill>
  );
};
