import { useCallback, useEffect, useState, type MouseEvent } from "react";

export function usePointerParallax(maximum = 8) {
  const [enabled, setEnabled] = useState(false);
  const [offset, setOffset] = useState({ x: 0, y: 0 });

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const pointer = window.matchMedia("(pointer: fine)");
    const update = () => setEnabled(!media.matches && pointer.matches);
    update();
    media.addEventListener?.("change", update);
    pointer.addEventListener?.("change", update);
    return () => {
      media.removeEventListener?.("change", update);
      pointer.removeEventListener?.("change", update);
    };
  }, []);

  const onPointerMove = useCallback(
    (event: MouseEvent<HTMLElement>) => {
      if (!enabled) return;
      const rect = event.currentTarget.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width - 0.5) * maximum * 2;
      const y = ((event.clientY - rect.top) / rect.height - 0.5) * maximum * 2;
      setOffset({ x, y });
    },
    [enabled, maximum],
  );

  const onPointerLeave = useCallback(() => setOffset({ x: 0, y: 0 }), []);
  return { offset, onPointerMove, onPointerLeave };
}
