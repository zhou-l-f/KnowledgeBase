import { clsx } from "clsx";
import { useId } from "react";
import type { TextareaHTMLAttributes } from "react";

interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  hint?: string;
}

/** 多行文本输入：与 TextField 保持一致的砚墨风格。 */
export function TextArea({ label, hint, className, id, rows = 3, ...rest }: TextAreaProps) {
  const autoId = useId();
  const areaId = id ?? autoId;

  return (
    <div className="space-y-1.5">
      <label htmlFor={areaId} className="block text-xs font-medium tracking-wide text-ink-faint">
        {label}
      </label>
      <textarea
        {...rest}
        id={areaId}
        rows={rows}
        className={clsx(
          "block w-full resize-y rounded-lg border border-line bg-paper-raised/80 px-3 py-2 text-sm text-ink",
          "placeholder:text-ink-ghost/80 transition-colors",
          "focus:border-cinnabar/60 focus:bg-paper-raised focus:outline-none focus:ring-2 focus:ring-cinnabar/15",
          className,
        )}
      />
      {hint ? <p className="text-xs text-ink-ghost">{hint}</p> : null}
    </div>
  );
}
