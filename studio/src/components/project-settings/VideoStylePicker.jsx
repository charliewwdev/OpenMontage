import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { Check, Images, X } from "lucide-react";
import { tr, useLocale } from "../../lib/i18n";
export function VideoStylePicker({ value, onChange, disabled = false, styles, categories }) {
  useLocale();
  const library = styles || [];
  const categoryOptions = categories || [];
  const selectedStyle = library.find((s) => s.promptValue === value || s.id === value);
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
            {selectedStyle?.label ?? (value ? tr("ui_settings_video_style_picker_existing_custom_style") : tr("ui_settings_video_style_picker_choose_visual_style"))}
          </strong>
          <span className="mt-1 block truncate text-xs text-[var(--muted)]">
            {selectedStyle?.generationPrompt ?? (value || tr("ui_settings_video_style_picker_pick_a_shared_visual_language_from"))}
          </span>
        </span>
        <span className="shrink-0 rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold text-[var(--ink)]">{tr("ui_settings_video_style_picker_choose_style")}</span>
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
                    <h3 className="display-type text-2xl font-semibold">{tr("ui_settings_video_style_picker_choose_visual_style")}</h3>
                    <p className="mt-1 text-xs text-[var(--muted)]">{tr("ui_settings_video_style_picker_unifies_the_visual_language_of_characters")}</p>
                  </div>
                  <button type="button" aria-label={tr("ui_settings_video_style_picker_close")} className="btn-ghost !min-h-9 !px-2" onClick={() => setOpen(false)}>
                    <X className="h-4 w-4" />
                  </button>
                </header>
                <div className="flex gap-2 border-b border-[var(--line)] px-5 py-3">
                  {categoryOptions.map((item) => (
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
