import { PROJECT_RATIOS } from "../../config/options";

export function AspectRatioPicker({ value, onChange, disabled = false, ratios }) {
  const options = ratios?.length ? ratios : PROJECT_RATIOS;
  const normalized = options.some((o) => o.value === value) ? value : options[0]?.value || "9:16";

  return (
    <div
      className="grid grid-cols-1 gap-2 sm:grid-cols-3"
      role="radiogroup"
      aria-label="画面比例"
      aria-disabled={disabled}
    >
      {options.map((option) => {
        const selected = normalized === option.value;
        const vertical = option.value === "9:16";
        const square = option.value === "1:1";
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onChange(option.value)}
            className={`flex min-h-[4.5rem] min-w-0 items-center gap-3 overflow-hidden rounded-xl border px-3 py-2.5 text-left transition disabled:cursor-not-allowed disabled:opacity-55 ${
              selected
                ? "border-[#7c6cff]/60 bg-[#7c6cff]/12 shadow-[0_0_0_2px_rgba(124,108,255,.18)]"
                : "border-[var(--line-strong)] bg-white/[.03] hover:border-white/25"
            }`}
          >
            <span
              className={`shrink-0 rounded-[3px] border-2 ${
                selected ? "border-[#a78bfa] bg-white/10" : "border-white/25 bg-black/30"
              } ${vertical ? "h-10 w-6" : square ? "h-8 w-8" : "h-6 w-10"}`}
              aria-hidden="true"
            />
            <span className="min-w-0 flex-1">
              <strong className="timecode block truncate text-sm">{option.value}</strong>
              <span className="mt-0.5 block truncate text-xs text-[var(--muted)]">
                {option.label}
                {option.description ? ` · ${option.description}` : ""}
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
