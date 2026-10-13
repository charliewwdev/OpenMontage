import { useMemo } from "react";
import { PenLine } from "lucide-react";

export function GenrePicker({ value, onChange, disabled = false, genres }) {
  const options = genres || [];
  const isPreset = useMemo(() => options.some((option) => option === value), [options, value]);

  return (
    <div>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="题材" aria-disabled={disabled}>
        {options.map((option) => (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={value === option}
            disabled={disabled}
            onClick={() => onChange(option)}
            className={`rounded-full border px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-55 ${
              value === option
                ? "border-transparent bg-[var(--gradient)] text-white shadow-sm"
                : "border-[var(--line-strong)] bg-white/[.03] text-[var(--muted)] hover:border-white/25 hover:text-[var(--ink)]"
            }`}
          >
            {option}
          </button>
        ))}
        <button
          type="button"
          role="radio"
          aria-checked={!isPreset}
          disabled={disabled}
          onClick={() => {
            if (isPreset) onChange("");
          }}
          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-55 ${
            !isPreset
              ? "border-[#7c6cff]/50 bg-[#7c6cff]/15 text-[var(--ink)]"
              : "border-dashed border-[var(--line-strong)] bg-white/[.03] text-[var(--muted)] hover:border-[#7c6cff]/50 hover:text-[var(--ink)]"
          }`}
        >
          <PenLine className="h-3.5 w-3.5" />
          自定义
        </button>
      </div>
      {!isPreset ? (
        <input
          className="field mt-3"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="输入自定义题材，例如：民国谍战"
          maxLength={80}
          autoFocus
          disabled={disabled}
        />
      ) : null}
    </div>
  );
}
