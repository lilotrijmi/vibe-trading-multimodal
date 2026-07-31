// @vitest-environment node

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const agentSource = readFileSync(
  fileURLToPath(new URL("../Agent.tsx", import.meta.url)),
  "utf8",
);

const composerStartMarker = "{/* chat-composer:start */}";
const composerEndMarker = "{/* chat-composer:end */}";
const attachmentMarker = "<MultimodalAttachment";

function getComposerSource(): string {
  const composerStart = agentSource.indexOf(composerStartMarker);
  const composerEnd = agentSource.indexOf(composerEndMarker);

  expect(composerStart).toBeGreaterThan(-1);
  expect(composerEnd).toBeGreaterThan(composerStart);
  return agentSource.slice(composerStart, composerEnd + composerEndMarker.length);
}

describe("Agent attachment layout", () => {
  it("mounts multimodal attachments once outside the full rounded composer", () => {
    const attachmentMatches = agentSource.split(attachmentMarker).length - 1;
    const attachmentIndex = agentSource.indexOf(attachmentMarker);
    const composerStart = agentSource.indexOf(composerStartMarker);
    const composerSource = getComposerSource();

    expect(attachmentMatches).toBe(1);
    expect(attachmentIndex).toBeGreaterThan(-1);
    expect(attachmentIndex).toBeLessThan(composerStart);
    expect(composerSource).not.toContain(attachmentMarker);
  });

  it("keeps every primary composer control inside the composer boundary", () => {
    const composerSource = getComposerSource();

    expect(composerSource).toContain('data-testid="composer-attachment-trigger"');
    expect(composerSource).toContain('data-testid="composer-textarea"');
    expect(composerSource).toContain('data-testid="composer-submit-control"');
    expect(composerSource).toContain('data-testid="chat-composer"');
  });
});
