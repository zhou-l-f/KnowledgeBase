import { clsx } from "clsx";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { Spinner } from "@/components/ui/Spinner";

type Variant = "primary" | "outline" | "ghost" | "danger";
type Size = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

const BASE =
  "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-all duration-150 " +
  "disabled:cursor-not-allowed disabled:opacity-45 focus-visible:outline-none " +
  "focus-visible:ring-2 focus-visible:ring-cinnabar/35 focus-visible:ring-offset-1 focus-visible:ring-offset-paper";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-cinnabar text-paper-raised shadow-[0_8px_20px_-10px_rgba(165,50,29,0.85)] " +
    "hover:bg-cinnabar-soft active:translate-y-px",
  outline:
    "border border-line bg-paper-raised/70 text-ink-soft hover:border-ink-ghost hover:bg-paper-raised active:translate-y-px",
  ghost: "text-ink-faint hover:bg-paper-sunk/60 hover:text-ink",
  danger:
    "border border-cinnabar/35 bg-cinnabar/8 text-cinnabar hover:bg-cinnabar/15 active:translate-y-px",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-4 text-sm",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  icon,
  className,
  children,
  disabled,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      type={type}
      disabled={disabled || loading}
      className={clsx(BASE, SIZES[size], VARIANTS[variant], className)}
    >
      {loading ? <Spinner /> : icon}
      {children}
    </button>
  );
}
