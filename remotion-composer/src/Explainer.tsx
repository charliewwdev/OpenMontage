import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { TextCard } from "./components/TextCard";
import { StatCard } from "./components/StatCard";
import { CalloutBox } from "./components/CalloutBox";
import { ComparisonCard } from "./components/ComparisonCard";

// ---------------------------------------------------------------------------
// Types — aligned with edit_decisions artifact schema
// ---------------------------------------------------------------------------

interface Cut {
  id: string;
  source: string;
  in_seconds: number;
  out_seconds: number;
  layer?: string;
  type?: string;
  // Component-specific props
  text?: string;
  stat?: string;
  subtitle?: string;
  callout_type?: "info" | "warning" | "tip" | "quote";
  title?: string;
  // Comparison props
  leftLabel?: string;
  rightLabel?: string;
  leftValue?: string;
  rightValue?: string;
  // Animation & transitions
  animation?: string;
  transition_in?: string;
  transition_out?: string;
  transform?: {
    animation?: string;
    scale?: number;
    position?: { x: number; y: number };
  };
}

interface AudioLayer {
  src: string;
  volume?: number;
}

interface SfxCue {
  src: string;
  start_seconds: number;
  volume?: number;
}

interface AudioConfig {
  narration?: AudioLayer;
  music?: AudioLayer;
  sfx?: SfxCue[];
}

interface ExplainerProps {
  cuts: Cut[];
  subtitles?: { enabled: boolean; src?: string };
  audio?: AudioConfig;
}

// ---------------------------------------------------------------------------
// Image scene — spring / interpolate animations (replaces FFmpeg Ken Burns)
// ---------------------------------------------------------------------------

const IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"];
const VIDEO_EXTENSIONS = [".mp4", ".mov", ".webm", ".avi", ".mkv"];

function isImage(source: string): boolean {
  const lower = source.toLowerCase();
  return IMAGE_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function isVideo(source: string): boolean {
  const lower = source.toLowerCase();
  return VIDEO_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

const ImageScene: React.FC<{ src: string; animation?: string }> = ({
  src,
  animation,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Smooth fade-in on entrance
  const fadeIn = spring({ frame, fps, config: { damping: 20 } });

  let scale = 1;
  let translateX = 0;
  let translateY = 0;
  const anim = animation || "zoom-in";

  if (anim === "zoom-in") {
    scale = interpolate(frame, [0, durationInFrames], [1, 1.15], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
  } else if (anim === "zoom-out") {
    scale = interpolate(frame, [0, durationInFrames], [1.15, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
  } else if (anim === "pan-left") {
    translateX = interpolate(frame, [0, durationInFrames], [30, -30], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    scale = 1.15;
  } else if (anim === "pan-right") {
    translateX = interpolate(frame, [0, durationInFrames], [-30, 30], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    scale = 1.15;
  } else if (anim === "ken-burns") {
    scale = interpolate(frame, [0, durationInFrames], [1, 1.2], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    translateX = interpolate(frame, [0, durationInFrames], [0, -20], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    translateY = interpolate(frame, [0, durationInFrames], [0, -10], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
  }
  // "static" or "none" → no motion, just fade in

  return (
    <AbsoluteFill style={{ overflow: "hidden", backgroundColor: "#000" }}>
      <Img
        src={src}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          opacity: fadeIn,
          transform: `scale(${scale}) translate(${translateX}px, ${translateY}px)`,
        }}
      />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Video scene — OffthreadVideo for frame-accurate rendering
// ---------------------------------------------------------------------------

const VideoScene: React.FC<{ src: string; startFrom?: number }> = ({
  src,
  startFrom = 0,
}) => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill>
      <OffthreadVideo
        src={src}
        startFrom={Math.round(startFrom * fps)}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Fade transition wrapper
// ---------------------------------------------------------------------------

const FadeIn: React.FC<{
  children: React.ReactNode;
  durationFrames?: number;
}> = ({ children, durationFrames = 10 }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, durationFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return <AbsoluteFill style={{ opacity }}>{children}</AbsoluteFill>;
};

// ---------------------------------------------------------------------------
// Scene renderer — maps cut type / source to the right component
// ---------------------------------------------------------------------------

const SceneRenderer: React.FC<{ cut: Cut }> = ({ cut }) => {
  // Explicit component types
  if (cut.type === "text_card" && cut.text) {
    return <TextCard text={cut.text} />;
  }
  if (cut.type === "stat_card" && cut.stat) {
    return <StatCard stat={cut.stat} subtitle={cut.subtitle} />;
  }
  if (cut.type === "callout" && cut.text) {
    return (
      <CalloutBox text={cut.text} type={cut.callout_type} title={cut.title} />
    );
  }
  if (
    cut.type === "comparison" &&
    cut.leftLabel &&
    cut.rightLabel &&
    cut.leftValue &&
    cut.rightValue
  ) {
    return (
      <ComparisonCard
        leftLabel={cut.leftLabel}
        rightLabel={cut.rightLabel}
        leftValue={cut.leftValue}
        rightValue={cut.rightValue}
        title={cut.title}
      />
    );
  }

  // Auto-detect from source file extension
  const animation = cut.animation || cut.transform?.animation;

  if (isImage(cut.source)) {
    return <ImageScene src={cut.source} animation={animation} />;
  }

  if (isVideo(cut.source)) {
    return <VideoScene src={cut.source} startFrom={cut.in_seconds} />;
  }

  // Fallback: treat as image
  return <ImageScene src={cut.source} animation={animation} />;
};

// ---------------------------------------------------------------------------
// Main composition
// ---------------------------------------------------------------------------

export const Explainer: React.FC<ExplainerProps> = ({ cuts, audio }) => {
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Visual layers */}
      {cuts.map((cut) => {
        const from = Math.round(cut.in_seconds * fps);
        const duration = Math.round(
          (cut.out_seconds - cut.in_seconds) * fps
        );

        const scene = <SceneRenderer cut={cut} />;
        const wrapped =
          cut.transition_in === "fade" ? (
            <FadeIn>{scene}</FadeIn>
          ) : (
            scene
          );

        return (
          <Sequence key={cut.id} from={from} durationInFrames={duration}>
            <AbsoluteFill>{wrapped}</AbsoluteFill>
          </Sequence>
        );
      })}

      {/* Audio layers */}
      {audio?.narration?.src && (
        <Audio src={audio.narration.src} volume={audio.narration.volume ?? 1} />
      )}
      {audio?.music?.src && (
        <Audio
          src={audio.music.src}
          volume={audio.music.volume ?? 0.06}
        />
      )}
      {audio?.sfx?.map((cue, i) => (
        <Sequence
          key={`sfx-${i}`}
          from={Math.round(cue.start_seconds * fps)}
        >
          <Audio src={cue.src} volume={cue.volume ?? 0.5} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
