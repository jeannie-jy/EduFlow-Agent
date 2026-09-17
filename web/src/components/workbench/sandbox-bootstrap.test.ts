import { describe, expect, it } from "vitest";
import sandboxHtml from "../../../sandbox.html?raw";

describe("sandbox bootstrap document", () => {
  it("installs the message listener inline for an opaque-origin iframe", () => {
    expect(sandboxHtml).toContain('window.addEventListener("message"');
    expect(sandboxHtml).toContain('message.type !== "eduflow:sandbox-document"');
    expect(sandboxHtml).not.toContain('type="module"');
    expect(sandboxHtml).not.toContain('src="/src/sandbox-bootstrap.ts"');
  });
});
