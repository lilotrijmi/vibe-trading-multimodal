import { useState, type FormEvent } from "react";
import { useNavigate, useLocation } from "react-router";
import { useTranslation } from "react-i18next";
import { BarChart3, Loader2, LogIn } from "lucide-react";
import { toast } from "sonner";
import { login, type CurrentUser } from "@/lib/auth";

export function Login() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Where to go after login. The route guard sets this when it redirects.
  const from = (location.state as { from?: string } | null)?.from ?? "/agent";

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const user: CurrentUser = await login(username, password);
      toast.success(`Welcome, ${user.username}`);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-gradient-to-br from-background via-background to-muted/30 p-4">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center gap-3 mb-8">
          <div className="h-12 w-12 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
            <BarChart3 className="h-7 w-7" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Vibe-Trading</h1>
          <p className="text-sm text-muted-foreground">
            Sign in to access the trading agent
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-xl border bg-card/80 backdrop-blur-sm shadow-lg p-6 space-y-4"
        >
          {error && (
            <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          <div className="grid gap-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              {t("login.username", "Username")}
            </label>
            <input
              type="text"
              required
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              data-testid="login-username"
            />
          </div>

          <div className="grid gap-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              {t("login.password", "Password")}
            </label>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              data-testid="login-password"
            />
          </div>

          <button
            type="submit"
            disabled={submitting || !username || !password}
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-opacity disabled:opacity-40 hover:opacity-90"
            data-testid="login-submit"
          >
            {submitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <LogIn className="h-4 w-4" />
            )}
            {t("login.signIn", "Sign in")}
          </button>

          <p className="text-[11px] text-center text-muted-foreground">
            First time? The default admin is{" "}
            <code className="rounded bg-muted px-1 py-0.5">admin</code> /{" "}
            <code className="rounded bg-muted px-1 py-0.5">vibe-trading</code>.
            Change it in Admin → Users after signing in.
          </p>
        </form>
      </div>
    </div>
  );
}
