import { Suspense, lazy, useEffect, useState, type ComponentType, type ReactNode } from "react";
import { createBrowserRouter, Navigate, useLocation } from "react-router";
import { Layout } from "@/components/layout/Layout";
import { Login } from "@/pages/Login";
import { AdminUsers } from "@/pages/AdminUsers";
import { me, type CurrentUser } from "@/lib/auth";

/**
 * Wraps a protected page in an auth gate. Unauthenticated users are
 * redirected to /login; non-admin users visiting admin-only routes are
 * redirected to /agent.
 */
function AuthGate({
  children,
  adminOnly = false,
}: {
  children: ReactNode;
  adminOnly?: boolean;
}) {
  const location = useLocation();
  const [user, setUser] = useState<CurrentUser | null | undefined>(undefined);

  useEffect(() => {
    let alive = true;
    me()
      .then((u) => {
        if (alive) setUser(u);
      })
      .catch(() => {
        if (alive) setUser(null);
      });
    return () => {
      alive = false;
    };
  }, []);

  if (user === undefined) {
    return (
      <div className="flex h-[60vh] items-center justify-center text-muted-foreground">
        Loading…
      </div>
    );
  }
  if (user === null) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (adminOnly && user.role !== "admin") {
    return <Navigate to="/agent" replace />;
  }
  return <>{children}</>;
}

const Home = lazy(() => import("@/pages/Home").then((m) => ({ default: m.Home })));
const Agent = lazy(() => import("@/pages/Agent").then((m) => ({ default: m.Agent })));
const RunDetail = lazy(() =>
  import("@/pages/RunDetail").then((m) => ({ default: m.RunDetail })),
);
const Compare = lazy(() =>
  import("@/pages/Compare").then((m) => ({ default: m.Compare })),
);
const Settings = lazy(() =>
  import("@/pages/Settings").then((m) => ({ default: m.Settings })),
);
const Runtime = lazy(() =>
  import("@/pages/Runtime").then((m) => ({ default: m.Runtime })),
);
const Reports = lazy(() =>
  import("@/pages/Reports").then((m) => ({ default: m.Reports })),
);
const Correlation = lazy(() =>
  import("@/pages/Correlation").then((m) => ({ default: m.Correlation })),
);
const AlphaZoo = lazy(() =>
  import("@/pages/AlphaZoo").then((m) => ({ default: m.AlphaZoo })),
);

function PageLoader() {
  return (
    <div className="flex h-[60vh] items-center justify-center text-muted-foreground">
      Loading…
    </div>
  );
}

function wrap(Component: ComponentType) {
  return (
    <Suspense fallback={<PageLoader />}>
      <Component />
    </Suspense>
  );
}

export const router = createBrowserRouter([
  {
    path: "/login",
    element: wrap(Login),
  },
  {
    element: <Layout />,
    children: [
      { path: "/", element: <AuthGate><Home /></AuthGate> },
      { path: "/agent", element: <AuthGate><Agent /></AuthGate> },
      { path: "/runtime", element: <AuthGate><Runtime /></AuthGate> },
      { path: "/reports", element: <AuthGate><Reports /></AuthGate> },
      { path: "/settings", element: <AuthGate><Settings /></AuthGate> },
      { path: "/runs/:runId", element: <AuthGate><RunDetail /></AuthGate> },
      { path: "/compare", element: <AuthGate><Compare /></AuthGate> },
      { path: "/correlation", element: <AuthGate><Correlation /></AuthGate> },
      { path: "/alpha-zoo", element: <AuthGate><AlphaZoo /></AuthGate> },
      { path: "/alpha-zoo/bench", element: <AuthGate><AlphaZoo /></AuthGate> },
      { path: "/alpha-zoo/compare", element: <AuthGate><AlphaZoo /></AuthGate> },
      { path: "/alpha-zoo/:alphaId", element: <AuthGate><AlphaZoo /></AuthGate> },
      {
        path: "/admin/users",
        element: (
          <AuthGate adminOnly>
            <AdminUsers />
          </AuthGate>
        ),
      },
    ],
  },
]);
