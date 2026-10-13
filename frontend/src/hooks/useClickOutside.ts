import { useEffect } from "react";
import type { RefObject } from "react";

/**
 * 点击指定元素之外或按下 Esc 时触发回调（active 为 false 时不监听）。
 * 用于下拉菜单、弹层等轻量浮层的关闭处理。
 */
export function useClickOutside<T extends HTMLElement>(
  ref: RefObject<T | null>,
  onOutside: () => void,
  active = true,
): void {
  useEffect(() => {
    if (!active) {
      return;
    }
    function handlePointer(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        onOutside();
      }
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onOutside();
      }
    }
    document.addEventListener("mousedown", handlePointer);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handlePointer);
      document.removeEventListener("keydown", handleKey);
    };
  }, [ref, onOutside, active]);
}
