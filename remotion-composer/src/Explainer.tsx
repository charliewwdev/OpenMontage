import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/SpaceGrotesk";

// Resolve asset path — use staticFile() for local paths, passthrough URLs
function resolveAsset(src: string): string {
  if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:")) {
    return src;
  }
  // Strip any file:// prefix
  const clean = src.replace(/^file:\/\/\/?/, "");
  return staticFile(clean);
}
import { TextCard } from "./components/TextCard";
import { StatCard } from "./components/StatCard";
import { CalloutBox } from "./components/CalloutBox";
import { ComparisonCard } from "./components/ComparisonCard";
import { CaptionOverlay, WordCaption } from "./components/CaptionOverlay";
import { SectionTitle } from "./components/SectionTitle";
import { StatReveal } from "./components/StatReveal";
import { HeroTitle } from "./components/HeroTitle";

// Load Space Grotesk font for cinematic typography
const { fontFamily } = loadFont("normal", {
  weights: ["400", "700"],
  subsets: ["latin"],
});

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
    position?: string | { x: number; y: number };
  };
}

interface Overlay {
  type: "section_title" | "stat_reveal" | "hero_title";
  in_seconds: number;
  out_seconds: number;
  text: string;
  subtitle?: string;
  accentColor?: string;
  position?: string;
}

interface AudioLayer {
  src: string;
  volume?: number;
}

interface AudioConfig {
  narration?: AudioLayer;
  music?: AudioLayer & {
    fadeInSeconds?: number;
    fadeOutSeconds?: number;
  };
}

export interface ExplainerProps {
  cuts: Cut[];
  overlays?: Overlay[];
  captions?: WordCaption[];
  audio?: AudioConfig;
}

// ---------------------------------------------------------------------------
// Image Extensions
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

// ---------------------------------------------------------------------------
// Cinematic vignette overlay
// ---------------------------------------------------------------------------

const Vignette: React.FC = () => (
  <AbsoluteFill
    style={{
      background:
        "radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,0.6) 100%)",
      pointerEvents: "none",
    }}
  />
);

// ---------------------------------------------------------------------------
// Enhanced Image Scene — spring physics, parallax, variety
// ---------------------------------------------------------------------------

const ImageScene: React.FC<{ src: string; animation?: string }> = ({
  src,
  animation,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Smooth spring fade-in
  const fadeIn = spring({ frame, fps, config: { damping: 18, stiffness: 80 } });

  // Fade-out for crossfade effect
  const fadeOutStart = durationInFrames - 8;
  const fadeOut = interpolate(frame, [fadeOutStart, durationInFrames], [1, 0.3], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  let scale = 1;
  let translateX = 0;
  let translateY = 0;
  const anim = animation || "zoom-in";

  // Progress with easing — smoother than linear
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  if (anim === "zoom-in") {
    scale = 1 + progress * 0.18;
  } else if (anim === "zoom-out") {
    scale = 1.18 - progress * 0.18;
  } else if (anim === "pan-left") {
    translateX = interpolate(progress, [0, 1], [40, -40]);
    scale = 1.15;
  } else if (anim === "pan-right") {
    translateX = interpolate(progress, [0, 1], [-40, 40]);
    scale = 1.15;
  } else if (anim === "ken-burns" || anim === "ken-burns-slow-zoom") {
    // Cinematic Ken Burns: gentle zoom + diagonal drift
    scale = 1 + progress * 0.22;
    translateX = interpolate(progress, [0, 1], [0, -25]);
    translateY = interpolate(progress, [0, 1], [0, -15]);
  } else if (anim === "parallax") {
    // Subtle parallax — foreground moves faster
    translateY = interpolate(progress, [0, 1], [15, -15]);
    scale = 1.1;
  }
  // "static" or "none" → just display

  return (
    <AbsoluteFill style={{ overflow: "hidden", backgroundColor: "#0F172A" }}>
      <Img
        src={resolveAsset(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          opacity: fadeIn * fadeOut,
          transform: `scale(${scale}) translate(${translateX}px, ${translateY}px)`,
          willChange: "transform, opacity",
        }}
      />
      <Vignette />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Enhanced Video Scene
// ---------------------------------------------------------------------------

const VideoScene: React.FC<{ src: string; startFrom?: number }> = ({
  src,
  startFrom = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const fadeIn = spring({ frame, fps, config: { damping: 20 } });
  const fadeOutStart = durationInFrames - 8;
  const fadeOut = interpolate(frame, [fadeOutStart, durationInFrames], [1, 0.3], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#0F172A" }}>
      <OffthreadVideo
        src={resolveAsset(src)}
        startFrom={Math.round(startFrom * fps)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          opacity: fadeIn * fadeOut,
        }}
        muted
      />
      <Vignette />
    </AbsoluteFill>
  );
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

  const animation = cut.animation || cut.transform?.animation;

  if (isImage(cut.source)) {
    return <ImageScene src={cut.source} animation={animation} />;
  }

  if (isVideo(cut.source)) {
    return <VideoScene src={cut.source} startFrom={cut.in_seconds} />;
  }

  return <ImageScene src={cut.source} animation={animation} />;
};

// ---------------------------------------------------------------------------
// Overlay renderer
// ---------------------------------------------------------------------------

const OverlayRenderer: React.FC<{ overlay: Overlay }> = ({ overlay }) => {
  if (overlay.type === "section_title") {
    return (
      <SectionTitle
        title={overlay.text}
        subtitle={overlay.subtitle}
        accentColor={overlay.accentColor}
        position={(overlay.position as any) || "top-left"}
      />
    );
  }
  if (overlay.type === "stat_reveal") {
    return (
      <StatReveal
        stat={overlay.text}
        label={overlay.subtitle}
        accentColor={overlay.accentColor}
        position={(overlay.position as any) || "bottom-right"}
      />
    );
  }
  if (overlay.type === "hero_title") {
    return <HeroTitle title={overlay.text} subtitle={overlay.subtitle} />;
  }
  return null;
};

// ---------------------------------------------------------------------------
// Main composition
// ---------------------------------------------------------------------------

export const Explainer: React.FC<ExplainerProps> = ({
  cuts,
  overlays,
  captions,
  audio,
}) => {
  const { fps, durationInFrames } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: "#0F172A", fontFamily }}>
      {/* Layer 1: Visual scenes */}
      {cuts.map((cut) => {
        const from = Math.round(cut.in_seconds * fps);
        const duration = Math.round((cut.out_seconds - cut.in_seconds) * fps);

        return (
          <Sequence key={cut.id} from={from} durationInFrames={duration}>
            <SceneRenderer cut={cut} />
          </Sequence>
        );
      })}

      {/* Layer 2: Overlays (section titles, stat reveals, hero titles) */}
      {overlays?.map((overlay, i) => {
        const from = Math.round(overlay.in_seconds * fps);
        const duration = Math.round(
          (overlay.out_seconds - overlay.in_seconds) * fps
        );

        return (
          <Sequence key={`overlay-${i}`} from={from} durationInFrames={duration}>
            <OverlayRenderer overlay={overlay} />
          </Sequence>
        );
      })}

      {/* Layer 3: Captions (word-by-word highlight) */}
      {captions && captions.length > 0 && (
        <CaptionOverlay
          words={captions}
          wordsPerPage={6}
          fontSize={42}
          highlightColor="#22D3EE"
          backgroundColor="rgba(15, 23, 42, 0.7)"
        />
      )}

      {/* Layer 4: Audio — narration */}
      {audio?.narration?.src && (
        <Audio src={resolveAsset(audio.narration.src)} volume={audio.narration.volume ?? 1} />
      )}

      {/* Layer 4: Audio — music with fade in/out */}
      {audio?.music?.src && (
        <Audio
          src={resolveAsset(audio.music.src)}
          volume={(f) => {
            const baseVol = audio.music!.volume ?? 0.1;
            const fadeInDur = (audio.music!.fadeInSeconds ?? 2) * fps;
            const fadeOutDur = (audio.music!.fadeOutSeconds ?? 3) * fps;
            const totalFrames = durationInFrames;

            // Fade in
            const fadeIn = interpolate(f, [0, fadeInDur], [0, baseVol], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            // Fade out
            const fadeOut = interpolate(
              f,
              [totalFrames - fadeOutDur, totalFrames],
              [baseVol, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
            return Math.min(fadeIn, fadeOut);
          }}
        />
      )}
    </AbsoluteFill>
  );
};
