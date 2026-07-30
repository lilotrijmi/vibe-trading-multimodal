/**
 * Client-side API helpers for multimodal attachments.
 */

import { getApiAuthKey } from "./apiAuth";

export interface UploadResponse {
  attachment_id: number;
  bytes_hash: string;
  mime: string;
  width: number;
  height: number;
  expires_at: string | null;
}

export interface ChatResponse {
  message_id: number;
  conversation_id: number;
  /** The packed multimodal prompt (text + image descriptions + URL content).
   *  Feed this into the regular agent service (``/sessions/{id}/messages``)
   *  so the answer benefits from skills, swarm, tools, and language detection. */
  prompt: string;
}

function resolveApiKey(apiKey?: string): string {
  return apiKey ?? getApiAuthKey();
}

export async function uploadImage(
  file: File,
  apiKey?: string,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch("/api/multimodal/upload", {
    method: "POST",
    headers: { Authorization: `Bearer ${resolveApiKey(apiKey)}` },
    body: form,
  });
  if (!response.ok) {
    throw new Error(`Upload failed: ${response.statusText}`);
  }
  return response.json();
}

export async function sendMultimodalMessage(
  text: string,
  urls: string[],
  image: File | null,
  apiKey?: string,
): Promise<ChatResponse> {
  const form = new FormData();
  form.append("text", text);
  if (urls.length > 0) {
    form.append("urls", urls.join(","));
  }
  if (image) {
    form.append("image", image);
  }
  const response = await fetch("/api/multimodal/chat", {
    method: "POST",
    headers: { Authorization: `Bearer ${resolveApiKey(apiKey)}` },
    body: form,
  });
  if (!response.ok) {
    throw new Error(`Chat failed: ${response.statusText}`);
  }
  return response.json();
}
