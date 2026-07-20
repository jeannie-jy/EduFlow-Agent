export function EduFlowBrand({ compact = false }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <img src="/brand/eduflow-mark.png" alt="" className="size-8 shrink-0" />
      {!compact && (
        <span className="font-semibold tracking-[-0.02em]">EduFlow</span>
      )}
    </span>
  );
}
