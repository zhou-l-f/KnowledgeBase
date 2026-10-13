import { useEffect, useState } from "react";

import { fetchBlob } from "@/api/client";

type MediaStatus = "loading" | "ready" | "error";

/**
 * 媒体附件需携带令牌才能访问，无法直接用于 <img src>。
 * 这里统一拉取为 Blob 并生成 object URL；同一地址在会话内复用缓存，
 * 避免消息重渲染或媒体放大时重复请求（object URL 不主动回收，随会话结束释放）。
 */
const objectUrlCache = new Map<string, string>();

export function useAuthedMediaUrl(url: string): { src: string | null; status: MediaStatus } {
  const cached = objectUrlCache.get(url) ?? null;
  const [src, setSrc] = useState<string | null>(cached);
  const [status, setStatus] = useState<MediaStatus>(cached ? "ready" : "loading");

  useEffect(() => {
    const hit = objectUrlCache.get(url);
    if (hit) {
      setSrc(hit);
      setStatus("ready");
      return;
    }
    let cancelled = false;
    setStatus("loading");
    fetchBlob(url)
      .then((blob) => {
        const objectUrl = URL.createObjectURL(blob);
        objectUrlCache.set(url, objectUrl);
        if (!cancelled) {
          setSrc(objectUrl);
          setStatus("ready");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setStatus("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [url]);

  return { src, status };
}
