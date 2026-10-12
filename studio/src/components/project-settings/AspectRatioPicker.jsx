import { PROJECT_RATIOS } from "../../config/options";

export function AspectRatioPicker({ value, onChange, disabled = false, ratios }) {
  const options = ratios?.length ? ratios : PROJECT_RATIOS;
  const normalized = options.some((o) => o.value === value) ? value : options[0]?.value || "9:16";

  return (
    <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="画面比例" aria-disabled={disabled}>
      {options.map((option) => {
        const selected = normalized === option.value;
        const vertical = option.value === "9:16";
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onChange(option.value)}
            className={`flex min-h-20 items-center gap-3 rounded-xl border px-3 text-left transition disabled:cursor-not-allowed disabled:opacity-55 ${
              selected
                ? "border-[#7c6cff]/60 bg-[#7c6cff]/12 shadow-[0_0_0_2px_rgba(124,108,255,.18)]"
                : "border-[var(--line-strong)] bg-white/[.03] hover:border-white/25"
            }`}
          >
            <span
              className={`shrink-0 rounded-[3px] border-2 ${
                selected ? "border-[#a78bfa] bg-white/10" : "border-white/25 bg-black/30"
              } ${vertical ? "h-11 w-7" : "h-7 w-11"}`}
              aria-hidden="true"
            />
            <span>
              <strong className="timecode block text-sm">{option.value}</strong>
              <span className="mt-1 block text-xs text-[var(--muted)]">
                {option.label} · {option.description}
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
