import { useEffect, useRef, useState } from "react";
import { Link2, X } from "lucide-react";
import { uploadImage } from "@/lib/multimodalApi";
import { getApiAuthKey } from "@/lib/apiAuth";

const API_KEY_STORAGE = "vibe_trading_api_auth_key";

function getApiKey(): string {
  // Prefer the standard auth key set via Settings; fall back to legacy key.
  return getApiAuthKey() || localStorage.getItem(API_KEY_STORAGE) || "";
}

export type MultimodalAttachmentData =
  | { type: "image"; file: File; previewUrl: string; description: string | null }
  | { type: "url"; url: string; description: string | null };

export interface MultimodalAttachmentProps {
  apiKey?: string;
  onChange: (data: MultimodalAttachmentData | null) => void;
}

/**
 * Multimodal attachment bar for chat input.
 * Provides image upload (with vision analysis) and URL paste (with fetch+extract).
 * Result is shown as a chip above the input.
 */
export function MultimodalAttachment({ apiKey, onChange }: MultimodalAttachmentProps) {
  const [attachment, setAttachment] = useState<MultimodalAttachmentData | null>(null);
  const [urlInput, setUrlInput] = useState("");
  const [showUrlInput, setShowUrlInput] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const key = apiKey ?? getApiKey();

  // Listen for paste events from the parent chat input. The parent fires
  // ``multimodal:paste-image`` with a File detail when the user pastes an
  // image from the clipboard. We upload it just like a drag/drop file.
  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{ file: File }>).detail;
      if (!detail?.file) return;
      void handleImageFile(detail.file);
    };
    window.addEventListener("multimodal:paste-image", handler as EventListener);
    return () => window.removeEventListener("multimodal:paste-image", handler as EventListener);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // FAB-menu trigger: the parent (Agent.tsx) dispatches these events when
  // the user clicks the "Image" or "URL" items in the + menu. We react
  // here so the trigger can live in the FAB while the actual state +
  // upload logic stays local to this component.
  useEffect(() => {
    const onOpenImage = () => fileInputRef.current?.click();
    const onShowUrl = () => setShowUrlInput(true);
    window.addEventListener("multimodal:open-image", onOpenImage as EventListener);
    window.addEventListener("multimodal:show-url", onShowUrl as EventListener);
    return () => {
      window.removeEventListener("multimodal:open-image", onOpenImage as EventListener);
      window.removeEventListener("multimodal:show-url", onShowUrl as EventListener);
    };
  }, []);

  const handleImageFile = async (file: File) => {
    setError(null);
    setLoading(true);
    try {
      const previewUrl = URL.createObjectURL(file);
      const uploadRes = await uploadImage(file, key);
      const data: MultimodalAttachmentData = {
        type: "image",
        file,
        previewUrl,
        description: `Pasted (id=${uploadRes.attachment_id}, ${uploadRes.width}x${uploadRes.height})`,
      };
      setAttachment(data);
      onChange(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    void handleImageFile(file);
  };

  const handleAddUrl = () => {
    const url = urlInput.trim();
    if (!url) return;
    if (!/^https?:\/\//i.test(url)) {
      setError("URL must start with http:// or https://");
      return;
    }
    setError(null);
    const data: MultimodalAttachmentData = {
      type: "url",
      url,
      description: "Will fetch and extract on send",
    };
    setAttachment(data);
    onChange(data);
    setUrlInput("");
    setShowUrlInput(false);
  };

  const handleClear = () => {
    if (attachment && attachment.type === "image") {
      URL.revokeObjectURL(attachment.previewUrl);
    }
    setAttachment(null);
    setError(null);
    onChange(null);
  };

  return (
    <div className="flex flex-col gap-2" data-testid="multimodal-attachment">
      {attachment && (
        <div
          data-testid="attachment-chip"
          className="flex items-center gap-2 self-start max-w-full rounded-lg border bg-muted/30 px-2.5 py-1.5 text-xs"
        >
          {attachment.type === "image" ? (
            <img
              src={attachment.previewUrl}
              alt={attachment.file.name}
              className="h-6 w-6 rounded object-cover"
            />
          ) : (
            <Link2 className="h-4 w-4 shrink-0 text-blue-500" />
          )}
          <span className="truncate text-foreground">
            {attachment.type === "image" ? attachment.file.name : attachment.url}
          </span>
          {attachment.description && (
            <span className="text-muted-foreground truncate">- {attachment.description}</span>
          )}
          <button
            type="button"
            onClick={handleClear}
            className="ml-1 rounded p-0.5 hover:bg-destructive/20 hover:text-destructive"
            aria-label="Remove attachment"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Hidden file input — exposed to the parent via the global
          ``multimodal:open-image`` event so the Image action can live in
          the FAB menu (not the chat-input sidebar). */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        onChange={handleImageSelect}
        className="hidden"
        data-testid="multimodal-image-input"
        disabled={loading}
      />

      {/* Programmatic triggers: the parent FAB menu dispatches these
          custom events; we react here to keep the trigger surface inside
          the FAB while the actual upload + state still lives in this
          component. */}
      <div className="hidden">
        <button
          type="button"
          data-testid="multimodal-image-button"
          aria-hidden="true"
          tabIndex={-1}
          onClick={() => fileInputRef.current?.click()}
        />
        <button
          type="button"
          data-testid="multimodal-url-button"
          aria-hidden="true"
          tabIndex={-1}
          onClick={() => setShowUrlInput((s) => !s)}
        />
      </div>

      {showUrlInput && (
        <div className="flex items-center gap-1" data-testid="multimodal-url-row">
          <input
            type="url"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleAddUrl();
              }
              if (e.key === "Escape") {
                setShowUrlInput(false);
                setUrlInput("");
              }
            }}
            placeholder="https://example.com/article"
            className="flex-1 rounded-lg border bg-background px-2 py-1.5 text-xs outline-none focus:ring-2 focus:ring-primary/30"
            data-testid="multimodal-url-input"
            autoFocus
          />
          <button
            type="button"
            onClick={handleAddUrl}
            className="rounded-lg border px-2 py-1.5 text-xs font-medium hover:bg-muted"
            data-testid="multimodal-url-confirm"
          >
            Add
          </button>
          <button
            type="button"
            onClick={() => { setShowUrlInput(false); setUrlInput(""); }}
            className="rounded-lg px-2 py-1.5 text-xs text-muted-foreground hover:text-foreground"
            aria-label="Cancel URL"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {error && (
        <p className="text-xs text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
