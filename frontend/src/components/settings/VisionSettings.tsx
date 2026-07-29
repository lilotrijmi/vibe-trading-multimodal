import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, Eye, Save, RotateCcw, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import {
  api,
  type VisionSettings,
  type UpdateVisionSettingsRequest,
  type LLMProviderOption,
} from "@/lib/api";

/**
 * Vision model settings for multimodal (image) attachments.
 * Independent from the chat LLM so users can route vision to a multimodal
 * model (e.g. gpt-4o, Genflow minimax-m3) while keeping a cheaper model
 * for text-only chat.
 */
export function VisionSettingsSection() {
  const { t } = useTranslation();
  const [settings, setSettings] = useState<VisionSettings | null>(null);
  const [providers, setProviders] = useState<LLMProviderOption[]>([]);
  const [provider, setProvider] = useState("openai");
  const [modelName, setModelName] = useState("gpt-4o");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getVisionSettings()
      .then((s) => {
        setSettings(s);
        setProviders(s.providers);
        setProvider(s.provider);
        setModelName(s.model_name);
        setBaseUrl(s.base_url);
        setEnabled(s.enabled);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load vision settings");
      })
      .finally(() => setLoading(false));
  }, []);

  const selectedProvider = providers.find((p) => p.name === provider);

  const handleProviderChange = (name: string) => {
    setProvider(name);
    setClearApiKey(false);
    setApiKey("");
    const p = providers.find((item) => item.name === name);
    if (p) {
      setBaseUrl(p.default_base_url);
      setModelName(p.default_model);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: UpdateVisionSettingsRequest = {
        provider,
        model_name: modelName.trim(),
        base_url: baseUrl.trim() || undefined,
        api_key: apiKey.trim() || undefined,
        clear_api_key: clearApiKey,
        enabled,
      };
      const updated = await api.updateVisionSettings(payload);
      setSettings(updated);
      setApiKey("");
      setClearApiKey(false);
      toast.success(t("visionSettings.saved", "Vision settings saved"));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save vision settings";
      setError(message);
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (!settings) return;
    setProvider(settings.provider);
    setModelName(settings.model_name);
    setBaseUrl(settings.base_url);
    setApiKey("");
    setClearApiKey(false);
    setEnabled(settings.enabled);
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        {t("visionSettings.loading", "Loading vision settings...")}
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-xl border bg-card p-5" data-testid="vision-settings">
      <div className="flex items-center gap-2">
        <Eye className="h-5 w-5 text-primary" />
        <div className="flex-1">
          <h2 className="text-lg font-semibold">
            {t("visionSettings.title", "Vision Model (for image attachments)")}
          </h2>
          <p className="text-xs text-muted-foreground">
            {t(
              "visionSettings.description",
              "Separate model used to analyze uploaded images. Used automatically when an image is attached in chat."
            )}
          </p>
        </div>
        <label className="inline-flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            data-testid="vision-enabled"
          />
          {t("visionSettings.enabled", "Enabled")}
        </label>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <div className="grid gap-1.5">
          <label className="text-xs font-medium text-muted-foreground">
            {t("visionSettings.provider", "Provider")}
          </label>
          <select
            value={provider}
            onChange={(e) => handleProviderChange(e.target.value)}
            disabled={!enabled}
            data-testid="vision-provider"
            className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          >
            {(providers.length > 0 ? providers : [{ name: "openai", label: "OpenAI" }]).map((p) => (
              <option key={p.name} value={p.name}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <div className="grid gap-1.5">
          <label className="text-xs font-medium text-muted-foreground">
            {t("visionSettings.model", "Model")}
          </label>
          <input
            type="text"
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            disabled={!enabled}
            placeholder="gpt-4o, minimax-m3, GenflowAi-3.5-GenflowAi, ..."
            data-testid="vision-model"
            className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>

        <div className="grid gap-1.5 md:col-span-2">
          <label className="text-xs font-medium text-muted-foreground">
            {t("visionSettings.baseUrl", "Base URL")}
          </label>
          <input
            type="text"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            disabled={!enabled}
            placeholder={selectedProvider?.default_base_url ?? "https://api.openai.com/v1"}
            data-testid="vision-base-url"
            className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30 font-mono"
          />
        </div>

        <div className="grid gap-1.5 md:col-span-2">
          <label className="text-xs font-medium text-muted-foreground">
            {t("visionSettings.apiKey", "API Key")}
            {settings?.api_key_configured && (
              <span className="ml-2 text-[10px] uppercase tracking-wide text-emerald-600 dark:text-emerald-400">
                {t("visionSettings.keyConfigured", "configured")}
              </span>
            )}
          </label>
          <div className="flex gap-2">
            <input
              type="password"
              value={apiKey}
              onChange={(e) => { setApiKey(e.target.value); setClearApiKey(false); }}
              disabled={!enabled}
              placeholder={settings?.api_key_configured ? "••••••••" : t("visionSettings.apiKeyPlaceholder", "Enter new API key")}
              data-testid="vision-api-key"
              className="flex-1 rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
            {settings?.api_key_configured && (
              <button
                type="button"
                onClick={() => { setClearApiKey(!clearApiKey); setApiKey(""); }}
                className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                  clearApiKey
                    ? "border-destructive bg-destructive/10 text-destructive"
                    : "hover:bg-muted"
                }`}
                data-testid="vision-clear-api-key"
              >
                {clearApiKey ? t("visionSettings.willClear", "Will clear") : t("visionSettings.clear", "Clear")}
              </button>
            )}
          </div>
          <p className="text-[10px] text-muted-foreground">
            {t(
              "visionSettings.apiKeyHint",
              "If left blank and the chat LLM uses the same key, it is reused. Keys starting with \"gf-\" auto-route to Genflow."
            )}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || !enabled || !modelName.trim()}
          data-testid="vision-save"
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity disabled:opacity-40 hover:opacity-90"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          {t("visionSettings.save", "Save")}
        </button>
        <button
          type="button"
          onClick={handleReset}
          disabled={saving}
          className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
        >
          <RotateCcw className="h-4 w-4" />
          {t("visionSettings.reset", "Reset")}
        </button>
        {settings && (
          <span className="ml-auto text-[10px] text-muted-foreground font-mono">
            {settings.env_path}
          </span>
        )}
      </div>
    </div>
  );
}
