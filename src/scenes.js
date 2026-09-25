// Adds the branded intro/outro around the producer's scenes. Shared by Root
// (to compute total length) and Explainer (to draw), so both always agree.
export const INTRO_SEC = 2.6;
export const OUTRO_SEC = 4.5;

export const buildScenes = (props) => {
  const scenes = (props.scenes || []).map((s) => ({...s}));
  if (!scenes.length) return scenes;
  const out = [];
  if (props.intro !== false && props.channel) {
    out.push({type: 'intro', duration: INTRO_SEC, focus: [], synthetic: true});
  }
  out.push(...scenes);
  if (props.outro !== false && props.channel) {
    const last = scenes[scenes.length - 1];
    out.push({type: 'outro', duration: OUTRO_SEC, focus: [], synthetic: true, lastFocus: last.focus});
  }
  return out;
};

export const totalFrames = (props, fps) =>
  buildScenes(props).reduce((a, s) => a + Math.max(1, Math.round((s.duration || 5) * fps)), 0);
