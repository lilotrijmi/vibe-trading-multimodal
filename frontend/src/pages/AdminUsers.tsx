import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { Loader2, Shield, ShieldOff, UserPlus, Trash2, Pencil, Check, X } from "lucide-react";
import { toast } from "sonner";
import {
  createUser,
  deleteUser,
  listUsers,
  me,
  updateUser,
  type CurrentUser,
  type UserRole,
} from "@/lib/auth";

export function AdminUsers() {
  const navigate = useNavigate();
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [users, setUsers] = useState<CurrentUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // Form state for the create dialog.
  const [form, setForm] = useState({
    username: "",
    password: "",
    role: "user" as UserRole,
    rate_limit_per_hour: 60,
    note: "",
  });

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const meRes = await me();
        if (!alive) return;
        if (!meRes || meRes.role !== "admin") {
          toast.error("Admin access required");
          navigate("/agent", { replace: true });
          return;
        }
        setCurrentUser(meRes);
        const list = await listUsers();
        if (alive) setUsers(list);
      } catch (err) {
        if (alive) setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [navigate]);

  const reload = async () => {
    setLoading(true);
    try {
      const list = await listUsers();
      setUsers(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reload");
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await createUser({
        username: form.username,
        password: form.password,
        role: form.role,
        rate_limit_per_hour: form.rate_limit_per_hour,
        note: form.note || null,
      });
      toast.success(`User ${form.username} created`);
      setCreateOpen(false);
      setForm({ username: "", password: "", role: "user", rate_limit_per_hour: 60, note: "" });
      await reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create user");
    }
  };

  const handleUpdate = async (id: number, payload: Parameters<typeof updateUser>[1]) => {
    try {
      await updateUser(id, payload);
      toast.success("User updated");
      setEditingId(null);
      await reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update user");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteUser(id);
      toast.success("User deleted");
      setDeletingId(null);
      await reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete user");
    }
  };

  if (loading && !currentUser) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin mr-2" />
        Loading users…
      </div>
    );
  }

  if (error) {
    return <div className="p-6 text-destructive">{error}</div>;
  }

  return (
    <div className="h-full overflow-auto p-4 sm:p-6 max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-semibold">User Management</h1>
          <span className="text-xs text-muted-foreground">
            ({users.length} user{users.length === 1 ? "" : "s"})
          </span>
        </div>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          data-testid="admin-add-user"
        >
          <UserPlus className="h-4 w-4" />
          Add user
        </button>
      </div>

      <div className="rounded-xl border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="text-start px-4 py-2">User</th>
              <th className="text-start px-4 py-2">Role</th>
              <th className="text-start px-4 py-2">Rate / hour</th>
              <th className="text-start px-4 py-2">Status</th>
              <th className="text-end px-4 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-t hover:bg-muted/30">
                <td className="px-4 py-2.5">
                  <div className="flex flex-col">
                    <span className="font-medium">{u.username}</span>
                    <span className="text-[11px] text-muted-foreground">
                      {u.note || "—"}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-2.5">
                  {u.role === "admin" ? (
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-primary">
                      <Shield className="h-3 w-3" /> admin
                    </span>
                  ) : (
                    <span className="text-xs text-muted-foreground">user</span>
                  )}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs">{u.rate_limit_per_hour}</td>
                <td className="px-4 py-2.5">
                  <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
                    <Check className="h-3 w-3" /> active
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-1 justify-end">
                    <button
                      type="button"
                      onClick={() => setEditingId(u.id)}
                      className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs hover:bg-muted"
                      data-testid={`admin-edit-${u.username}`}
                    >
                      <Pencil className="h-3 w-3" /> Edit
                    </button>
                    {u.id !== currentUser?.id && (
                      <button
                        type="button"
                        onClick={() => setDeletingId(u.id)}
                        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-destructive hover:bg-destructive/10"
                        data-testid={`admin-delete-${u.username}`}
                      >
                        <Trash2 className="h-3 w-3" /> Delete
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create dialog */}
      {createOpen && (
        <div className="fixed inset-0 z-40 bg-black/50 flex items-center justify-center p-4">
          <form
            onSubmit={handleCreate}
            className="w-full max-w-md rounded-xl border bg-card p-5 space-y-3 shadow-2xl"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold flex items-center gap-2">
                <UserPlus className="h-4 w-4" /> Create user
              </h2>
              <button
                type="button"
                onClick={() => setCreateOpen(false)}
                className="rounded p-1 hover:bg-muted"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="grid gap-1.5">
              <label className="text-xs font-medium text-muted-foreground">Username</label>
              <input
                required
                minLength={1}
                maxLength={64}
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            <div className="grid gap-1.5">
              <label className="text-xs font-medium text-muted-foreground">Password (min 8)</label>
              <input
                type="password"
                required
                minLength={8}
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="grid gap-1.5">
                <label className="text-xs font-medium text-muted-foreground">Role</label>
                <select
                  value={form.role}
                  onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}
                  className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                >
                  <option value="user">user</option>
                  <option value="admin">admin</option>
                </select>
              </div>
              <div className="grid gap-1.5">
                <label className="text-xs font-medium text-muted-foreground">Rate / hour</label>
                <input
                  type="number"
                  min={1}
                  max={10000}
                  value={form.rate_limit_per_hour}
                  onChange={(e) =>
                    setForm({ ...form, rate_limit_per_hour: Number(e.target.value) })
                  }
                  className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
            </div>
            <div className="grid gap-1.5">
              <label className="text-xs font-medium text-muted-foreground">Note (optional)</label>
              <input
                value={form.note}
                onChange={(e) => setForm({ ...form, note: e.target.value })}
                className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                placeholder="e.g. friend's account"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setCreateOpen(false)}
                className="rounded-lg border px-3 py-1.5 text-sm hover:bg-muted"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90"
              >
                Create
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Edit dialog */}
      {editingId !== null && (
        <EditUserDialog
          user={users.find((u) => u.id === editingId)!}
          onClose={() => setEditingId(null)}
          onSave={(payload) => handleUpdate(editingId, payload)}
        />
      )}

      {/* Delete confirm */}
      {deletingId !== null && (
        <div className="fixed inset-0 z-40 bg-black/50 flex items-center justify-center p-4">
          <div className="w-full max-w-sm rounded-xl border bg-card p-5 space-y-3">
            <h2 className="text-base font-semibold flex items-center gap-2 text-destructive">
              <ShieldOff className="h-4 w-4" /> Delete user?
            </h2>
            <p className="text-sm text-muted-foreground">
              This will revoke all sessions and rate-limit data. This action cannot
              be undone.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setDeletingId(null)}
                className="rounded-lg border px-3 py-1.5 text-sm hover:bg-muted"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleDelete(deletingId)}
                className="rounded-lg bg-destructive px-3 py-1.5 text-sm font-medium text-destructive-foreground hover:opacity-90"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function EditUserDialog({
  user,
  onClose,
  onSave,
}: {
  user: CurrentUser;
  onClose: () => void;
  onSave: (payload: Parameters<typeof updateUser>[1]) => void;
}) {
  const [role, setRole] = useState<UserRole>(user.role);
  const [rate, setRate] = useState(user.rate_limit_per_hour);
  const [isActive, setIsActive] = useState(1);
  const [password, setPassword] = useState("");
  return (
    <div className="fixed inset-0 z-40 bg-black/50 flex items-center justify-center p-4">
      <div className="w-full max-w-md rounded-xl border bg-card p-5 space-y-3 shadow-2xl">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold flex items-center gap-2">
            <Pencil className="h-4 w-4" /> Edit {user.username}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 hover:bg-muted"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div className="grid gap-1.5">
            <label className="text-xs font-medium text-muted-foreground">Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            >
              <option value="user">user</option>
              <option value="admin">admin</option>
            </select>
          </div>
          <div className="grid gap-1.5">
            <label className="text-xs font-medium text-muted-foreground">Rate / hour</label>
            <input
              type="number"
              min={1}
              max={10000}
              value={rate}
              onChange={(e) => setRate(Number(e.target.value))}
              className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
        </div>
        <div className="grid gap-1.5">
          <label className="text-xs font-medium text-muted-foreground">Status</label>
          <select
            value={isActive}
            onChange={(e) => setIsActive(Number(e.target.value))}
            className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          >
            <option value={1}>active</option>
            <option value={0}>disabled</option>
          </select>
        </div>
        <div className="grid gap-1.5">
          <label className="text-xs font-medium text-muted-foreground">
            New password (leave blank to keep)
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border px-3 py-1.5 text-sm hover:bg-muted"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() =>
              onSave({
                role,
                rate_limit_per_hour: rate,
                is_active: isActive,
                ...(password ? { password } : {}),
              })
            }
            className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
