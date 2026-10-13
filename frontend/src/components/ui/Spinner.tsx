import { Loader2 } from "lucide-react";

import { clsx } from "clsx";

/** 加载指示器：默认继承当前文字色，尺寸随 className 调整。 */
export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={clsx("size-4 animate-spin", className)} strokeWidth={2} />;
}
