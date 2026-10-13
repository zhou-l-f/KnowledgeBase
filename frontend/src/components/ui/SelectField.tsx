import { clsx } from "clsx";
import { useId } from "react";
import type { SelectHTMLAttributes } from "react";

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  options: SelectOption[];
  hint?: string;
}

/** 下拉选择：与 TextField/TextArea 保持一致的砚墨风格。 */
export function SelectField({ label, options, hint, className, id, ...rest }: SelectFieldProps) {
  const autoId = useId();
  const selectId = id ?? autoId;

  return (
    <div className="space-y-1.5">
      <label htmlFor={selectId} className="block text-xs font-medium tracking-wide text-ink-faint">
        {label}
      </label>
      <select
        {...rest}
        id={selectId}
        className={clsx(
          "h-11 w-full rounded-lg border border-line bg-paper-raised/80 px-3 text-sm text-ink",
          "transition-colors focus:border-cinnabar/60 focus:bg-paper-raised focus:outline-none focus:ring-2 focus:ring-cinnabar/15",
          "disabled:cursor-not-allowed disabled:opacity-60",
          className,
        )}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {hint ? <p className="text-xs text-ink-ghost">{hint}</p> : null}
    </div>
  );
}
