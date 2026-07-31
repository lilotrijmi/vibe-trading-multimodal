// @vitest-environment node

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const agentSource = readFileSync(
  fileURLToPath(new URL("../Agent.tsx", import.meta.url)),
  "utf8",
);

const composerMarker = 'data-testid="chat-composer"';
const attachmentMarker = "<MultimodalAttachment";

describe("Agent attachment layout", () => {
  it("mounts multimodal attachments once above the rounded composer", () => {
    const attachmentMatches = agentSource.match(/<MultimodalAttachment\b/g) ?? [];
    const attachmentIndex = agentSource.indexOf(attachmentMarker);
    const composerIndex = agentSource.indexOf(composerMarker);

    expect(attachmentMatches).toHaveLength(1);
    expect(attachmentIndex).toBeGreaterThan(-1);
    expect(composerIndex).toBeGreaterThan(-1);
    expect(attachmentIndex).toBeLessThan(composerIndex);
  });

  it("keeps the text input section free of multimodal attachment UI", () => {
    const composerIndex = agentSource.indexOf(composerMarker);
    const textareaIndex = agentSource.indexOf("<textarea", composerIndex);
    const composerPrefix = agentSource.slice(composerIndex, textareaIndex);

    expect(textareaIndex).toBeGreaterThan(composerIndex);
    expect(composerPrefix).not.toContain(attachmentMarker);
  });
});
