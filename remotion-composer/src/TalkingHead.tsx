import { AbsoluteFill, OffthreadVideo } from "remotion";
import { CaptionOverlay, WordCaption } from "./components/CaptionOverlay";

export interface TalkingHeadProps {
  videoSrc: string;
  captions: WordCaption[];
  wordsPerPage?: number;
  fontSize?: number;
  highlightColor?: string;
}

export const TalkingHead: React.FC<TalkingHeadProps> = ({
  videoSrc,
  captions,
  wordsPerPage = 4,
  fontSize = 52,
  highlightColor = "#22D3EE",
}) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <OffthreadVideo
        src={videoSrc}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
      <CaptionOverlay
        words={captions}
        wordsPerPage={wordsPerPage}
        fontSize={fontSize}
        highlightColor={highlightColor}
        backgroundColor="rgba(0, 0, 0, 0.65)"
        color="#FFFFFF"
      />
    </AbsoluteFill>
  );
};
