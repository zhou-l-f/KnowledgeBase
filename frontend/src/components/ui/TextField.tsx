import { clsx } from "clsx";
import { useId } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  /** 输入框前置图标 */
  icon?: ReactNode;
  /** 输入框下方的补充说明 */
  hint?: string;
}

/** 带标签的文本输入框：统一砚墨风格的边框与聚焦态。 */
export function TextField({ label, icon, hint, className, id, ...rest }: TextFieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;

  return (
    <div className="space-y-1.5">
      <label htmlFor={inputId} className="block text-xs font-medium tracking-wide text-ink-faint">
        {label}
      </label>
      <div className="relative">
        {icon ? (
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-ghost">
            {icon}
          </span>
        ) : null}
        <input
          {...rest}
          id={inputId}
          className={clsx(
            "h-11 w-full rounded-lg border border-line bg-paper-raised/80 px-3 text-sm text-ink",
            "placeholder:text-ink-ghost/80 transition-colors",
            "focus:border-cinnabar/60 focus:bg-paper-raised focus:outline-none focus:ring-2 focus:ring-cinnabar/15",
            icon && "pl-10",
            className,
          )}
        />
      </div>
      {hint ? <p className="text-xs text-ink-ghost">{hint}</p> : null}
    </div>
  );
}
