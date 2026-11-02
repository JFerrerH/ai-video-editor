import { Composition } from "remotion";
import { Live, type LiveProps } from "./Live";

export const RemotionRoot = () => (
  <>
    <Composition id="Live" component={Live as any} durationInFrames={30} fps={30} width={1080} height={1920}
      defaultProps={{} as LiveProps}
      calculateMetadata={({ props }: any) => ({ durationInFrames: Math.round(props.duration * 30) })} />
  </>
);
