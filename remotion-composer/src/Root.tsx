import { Composition } from "remotion";
import { Explainer } from "./Explainer";

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="Explainer"
        component={Explainer}
        durationInFrames={30 * 60} // default 60s at 30fps, overridden by props
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          cuts: [],
          subtitles: { enabled: false },
          audio: {},
        }}
      />
    </>
  );
};
