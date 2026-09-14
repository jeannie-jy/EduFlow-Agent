const MAX_SANDBOX_DOCUMENT_BYTES = 5 * 1024 * 1024;

interface SandboxDocumentMessage {
  type: "eduflow:sandbox-document";
  html: string;
}

function isSandboxDocumentMessage(value: unknown): value is SandboxDocumentMessage {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<SandboxDocumentMessage>;
  return candidate.type === "eduflow:sandbox-document" && typeof candidate.html === "string";
}

window.addEventListener("message", (event: MessageEvent<unknown>) => {
  let parentOrigin = "";
  try {
    parentOrigin = document.referrer ? new URL(document.referrer).origin : "";
  } catch {
    return;
  }
  // The sandbox has an opaque origin by design, so event.origin must be checked
  // against the embedding document's referrer rather than window.location.origin
  // (which is "null" for this iframe).
  if (event.source !== window.parent || !parentOrigin || event.origin !== parentOrigin) return;
  if (!isSandboxDocumentMessage(event.data)) return;
  if (new Blob([event.data.html]).size > MAX_SANDBOX_DOCUMENT_BYTES) return;

  // The iframe intentionally has no allow-same-origin permission. Its dedicated
  // response CSP blocks network access and navigation while allowing the generated
  // inline React runtime to execute only inside this opaque-origin document.
  document.open();
  document.write(event.data.html);
  document.close();
});
