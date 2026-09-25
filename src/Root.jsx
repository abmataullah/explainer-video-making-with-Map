import {Composition} from 'remotion';
import {Explainer} from './Explainer';
import {totalFrames} from './scenes';
import sample from './sample.json';

export const Root = () => (
  <Composition
    id="Explainer"
    component={Explainer}
    fps={30}
    width={1920}
    height={1080}
    durationInFrames={300}
    defaultProps={sample}
    calculateMetadata={({props}) => ({
      durationInFrames: Math.max(totalFrames(props, 30), 30),
      width: props.width || 1920,
      height: props.height || 1080,
    })}
  />
);
