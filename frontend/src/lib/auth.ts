/**
 * Client-side auth helpers. The session cookie is HttpOnly so the browser
 * stores it automatically; these helpers just call the API and re-fetch
 * /api/auth/me to verify the current user.
 */

const AUTH_BASE = "/api/auth";

export type UserRole = "user" | "admin";

export interface CurrentUser {
  id: number;
  username: string;
  role: UserRole;
  rate_limit_per_hour: number;
  note: string | null;
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${text}`);
  }
  return (await res.json()) as T;
}

export async function login(
  username: string,
  password: string,
): Promise<CurrentUser> {
  const res = await fetch(`${AUTH_BASE}/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  return jsonOrThrow<CurrentUser>(res);
}

export async function logout(): Promise<void> {
  await fetch(`${AUTH_BASE}/logout`, {
    method: "POST",
    credentials: "include",
  });
}

export async function me(): Promise<CurrentUser | null> {
  const res = await fetch(`${AUTH_BASE}/me`, { credentials: "include" });
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as CurrentUser;
}

export async function listUsers(): Promise<CurrentUser[]> {
  const res = await fetch(`${AUTH_BASE}/users`, { credentials: "include" });
  return jsonOrThrow<{ users: CurrentUser[] }>(res).then((d) => d.users);
}

export interface UserCreatePayload {
  username: string;
  password: string;
  role: UserRole;
  rate_limit_per_hour: number;
  note?: string | null;
}

export interface UserUpdatePayload {
  role?: UserRole;
  rate_limit_per_hour?: number;
  is_active?: number;
  note?: string | null;
  password?: string;
}

export async function createUser(payload: UserCreatePayload): Promise<CurrentUser> {
  const res = await fetch(`${AUTH_BASE}/users`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return jsonOrThrow<CurrentUser>(res);
}

export async function updateUser(
  id: number,
  payload: UserUpdatePayload,
): Promise<CurrentUser> {
  const res = await fetch(`${AUTH_BASE}/users/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return jsonOrThrow<CurrentUser>(res);
}

export async function deleteUser(id: number): Promise<void> {
  const res = await fetch(`${AUTH_BASE}/users/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok && res.status !== 204) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
}
