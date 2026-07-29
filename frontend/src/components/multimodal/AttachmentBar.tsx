import { useState } from "react";

export interface AttachmentBarProps {
  onSubmit: (text: string, urls: string[], image: File | null) => void;
  disabled?: boolean;
}

/**
 * Standalone attachment bar for multimodal chat input.
 * Sends text, URLs, and an optional image to the backend.
 */
export function AttachmentBar({ onSubmit, disabled }: AttachmentBarProps) {
  const [text, setText] = useState("");
  const [urls, setUrls] = useState("");
  const [image, setImage] = useState<File | null>(null);

  const handleSubmit = () => {
    if (!text.trim()) return;
    const urlList = urls
      .split("\n")
      .map((u) => u.trim())
      .filter((u) => u.length > 0);
    onSubmit(text, urlList, image);
    setText("");
    setUrls("");
    setImage(null);
  };

  return (
    <div className="attachment-bar p-3 border rounded-md space-y-2" data-testid="attachment-bar">
      <textarea
        data-testid="chat-input"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Ask a trading question..."
        className="w-full p-2 border rounded"
        disabled={disabled}
        rows={3}
      />
      <textarea
        data-testid="url-input"
        value={urls}
        onChange={(e) => setUrls(e.target.value)}
        placeholder="Paste URLs (one per line)..."
        className="w-full p-2 border rounded"
        disabled={disabled}
        rows={2}
      />
      <input
        type="file"
        data-testid="image-input"
        accept="image/*"
        onChange={(e) => setImage(e.target.files?.[0] ?? null)}
        disabled={disabled}
      />
      <button
        data-testid="send-button"
        onClick={handleSubmit}
        disabled={disabled || !text.trim()}
        className="px-4 py-2 bg-primary text-primary-foreground rounded disabled:opacity-50"
      >
        Send
      </button>
    </div>
  );
}
