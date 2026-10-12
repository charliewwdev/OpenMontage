import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { Check, Images, X } from "lucide-react";
import { VIDEO_STYLES, getStyleByPromptValue } from "../../config/videoStyles";

const CATEGORIES = [
  { value: "all", label: "全部" },
  { value: "live-action", label: "真人" },
  { value: "2d", label: "2D" },
  { value: "3d", label: "3D" },
];

export function VideoStylePicker({ value, onChange, disabled = false, styles }) {
  const library = styles?.length ? styles : VIDEO_STYLES;
  const selectedStyle = getStyleByPromptValue(value) || library.find((s) => s.promptValue === value);
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState("all");
  const filteredStyles = useMemo(
    () => (category === "all" ? library : library.filter((style) => style.category === category)),
    [category, library],
  );

  useEffect(() => {
    if (!open) return undefined;
    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        aria-haspopup="dialog"
        disabled={disabled}
        onClick={() => setOpen(true)}
        className="flex w-full items-center gap-3 overflow-hidden rounded-2xl border border-[var(--line-strong)] bg-white/[.03] p-3 text-left transition hover:border-white/25 hover:bg-white/[.05] disabled:cursor-not-allowed disabled:opacity-55"
      >
        {selectedStyle?.previewImageUrl ? (
          <span className="relative h-14 w-20 shrink-0 overflow-hidden rounded-lg bg-[#dfe4ea]">
            <img src={selectedStyle.previewImageUrl} alt="" className="h-full w-full object-cover" />
          </span>
        ) : (
          <span className="flex h-14 w-20 shrink-0 items-center justify-center rounded-lg bg-[var(--navy)] text-[var(--projector)]">
            <Images className="h-5 w-5" />
          </span>
        )}
        <span className="min-w-0 flex-1">
          <span className="label !mb-1">Selected look</span>
          <strong className="block truncate text-sm">
            {selectedStyle?.label ?? (value ? "原有自定义风格" : "选择视觉风格")}
          </strong>
          <span className="mt-1 block truncate text-xs text-[var(--muted)]">
            {selectedStyle?.generationPrompt ?? (value || "从风格库中选择统一画面语言")}
          </span>
        </span>
        <span className="shrink-0 rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold text-[var(--ink)]">
          选择风格
        </span>
      </button>

      {open
        ? createPortal(
            <div
              className="fixed inset-0 z-[80] flex items-center justify-center bg-[#09101d]/80 p-3 backdrop-blur-md md:p-6"
              onMouseDown={() => setOpen(false)}
            >
              <section
                role="dialog"
                aria-modal="true"
                className="flex h-[min(760px,calc(100vh-1.5rem))] w-full max-w-5xl flex-col overflow-hidden rounded-[24px] border border-white/15 bg-[var(--panel)] shadow-[0_36px_100px_-24px_rgba(0,0,0,.75)]"
                onMouseDown={(event) => event.stopPropagation()}
              >
                <header className="flex shrink-0 items-start justify-between gap-4 border-b border-[var(--line)] px-5 py-4 md:px-6 md:py-5">
                  <div>
                    <div className="label">Visual library · {library.length} looks</div>
                    <h3 className="display-type text-2xl font-semibold">选择视觉风格</h3>
                    <p className="mt-1 text-xs text-[var(--muted)]">统一角色、场景、道具和分镜的画面语言。</p>
                  </div>
                  <button type="button" aria-label="关闭" className="btn-ghost !min-h-9 !px-2" onClick={() => setOpen(false)}>
                    <X className="h-4 w-4" />
                  </button>
                </header>
                <div className="flex gap-2 border-b border-[var(--line)] px-5 py-3">
                  {CATEGORIES.map((item) => (
                    <button
                      key={item.value}
                      type="button"
                      className={category === item.value ? "chip-active" : "chip"}
                      onClick={() => setCategory(item.value)}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <div className="scrollbar-thin grid flex-1 grid-cols-2 gap-3 overflow-y-auto p-4 md:grid-cols-3 md:p-5 lg:grid-cols-4">
                  {filteredStyles.map((style) => {
                    const active = style.promptValue === value || style.id === value;
                    return (
                      <button
                        key={style.id}
                        type="button"
                        className={`overflow-hidden rounded-2xl border text-left transition ${
                          active ? "border-[#7c6cff] ring-2 ring-[#7c6cff]/35" : "border-[var(--line)] hover:border-white/25"
                        }`}
                        onClick={() => {
                          onChange(style.promptValue || style.generationPrompt);
                          setOpen(false);
                        }}
                      >
                        <div className="relative aspect-[4/3] bg-[var(--panel-muted)]">
                          {style.previewImageUrl ? (
                            <img src={style.previewImageUrl} alt="" className="h-full w-full object-cover" />
                          ) : null}
                          {active ? (
                            <span className="absolute right-2 top-2 rounded-full bg-[var(--gradient)] p-1 text-white">
                              <Check className="h-3.5 w-3.5" />
                            </span>
                          ) : null}
                        </div>
                        <div className="p-3">
                          <strong className="block text-sm">{style.label}</strong>
                          <span className="mt-1 line-clamp-2 text-[11px] text-[var(--muted)]">{style.generationPrompt}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </section>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
