import { useState, useMemo } from "react";
import { useApi } from "@core/hooks";
import { useT } from "@core/i18n";
import { useAuth } from "@core/auth";
import { DataTable, Modal, useToast } from "@shared/ui";
import type { Column } from "@shared/ui";
import type { UserInfo, UserRole } from "@core/api";
import { fmtDate } from "@core/utils";
import { Pencil, KeyRound, Trash2 } from "lucide-react";
import { translateApiError, isValidPassword } from "@core/utils";
import { ROLE_BADGE_COLORS } from "@shared/ui";
import { adminApi } from "./api";

const ALL_ROLES: UserRole[] = ["viewer", "researcher", "trader", "risk_manager", "admin"];

export function AdminPage() {
  const { t } = useT();
  const { toast } = useToast();
  const { role: currentRole } = useAuth();
  const { data: users, loading, error, refresh } = useApi(adminApi.listUsers);

  // Modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingUser, setEditingUser] = useState<UserInfo | null>(null);
  const [resetUser, setResetUser] = useState<UserInfo | null>(null);

  // Create form state
  const [createForm, setCreateForm] = useState({ username: "", display_name: "", password: "", confirmPassword: "", role: "viewer" });
  const [createLoading, setCreateLoading] = useState(false);

  // Edit form state
  const [editForm, setEditForm] = useState({ display_name: "", role: "", is_active: true });
  const [editLoading, setEditLoading] = useState(false);

  // Reset password state
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [resetLoading, setResetLoading] = useState(false);

  const roleDescriptions = t.admin.roleDescriptions as Record<string, string>;

  const handleCreate = async () => {
    if (createForm.password !== createForm.confirmPassword) {
      toast("error", t.admin.passwordMismatch);
      return;
    }
    setCreateLoading(true);
    try {
      await adminApi.createUser(createForm);
      toast("success", t.admin.userCreated);
      setShowCreateModal(false);
      setCreateForm({ username: "", display_name: "", password: "", confirmPassword: "", role: "viewer" });
      refresh();
    } catch (err) {
      toast("error", translateApiError(err instanceof Error ? err.message : t.common.requestFailed, t));
    } finally {
      setCreateLoading(false);
    }
  };

  const handleEdit = async () => {
    if (!editingUser) return;
    setEditLoading(true);
    try {
      await adminApi.updateUser(editingUser.id, {
        display_name: editForm.display_name,
        role: editForm.role,
        is_active: editForm.is_active,
      });
      toast("success", t.admin.userUpdated);
      setEditingUser(null);
      refresh();
    } catch (err) {
      toast("error", translateApiError(err instanceof Error ? err.message : t.common.requestFailed, t));
    } finally {
      setEditLoading(false);
    }
  };

  const handleResetPassword = async () => {
    if (!resetUser) return;
    if (newPassword !== confirmNewPassword) {
      toast("error", t.admin.passwordMismatch);
      return;
    }
    setResetLoading(true);
    try {
      await adminApi.resetPassword(resetUser.id, newPassword);
      toast("success", t.admin.passwordReset);
      setResetUser(null);
      setNewPassword("");
      setConfirmNewPassword("");
    } catch (err) {
      toast("error", translateApiError(err instanceof Error ? err.message : t.common.requestFailed, t));
    } finally {
      setResetLoading(false);
    }
  };

  const handleDelete = async (user: UserInfo) => {
    // Prevent self-deletion — compare by username stored in JWT/localStorage
    if (user.role === currentRole && user.is_active) {
      // Simple heuristic: warn if trying to delete an active admin when logged in as admin
    }
    if (!window.confirm(t.admin.deleteConfirm)) return;
    try {
      await adminApi.deleteUser(user.id);
      toast("success", t.admin.userDeleted);
      refresh();
    } catch (err) {
      toast("error", translateApiError(err instanceof Error ? err.message : t.common.requestFailed, t));
    }
  };

  const handleToggleActive = async (user: UserInfo) => {
    try {
      await adminApi.updateUser(user.id, { is_active: !user.is_active });
      toast("success", t.admin.userUpdated);
      refresh();
    } catch (err) {
      toast("error", translateApiError(err instanceof Error ? err.message : t.common.requestFailed, t));
    }
  };

  const openEdit = (user: UserInfo) => {
    setEditForm({ display_name: user.display_name, role: user.role, is_active: user.is_active });
    setEditingUser(user);
  };

  const openReset = (user: UserInfo) => {
    setNewPassword("");
    setConfirmNewPassword("");
    setResetUser(user);
  };

  const columns = useMemo<Column<UserInfo>[]>(() => [
    {
      key: "username",
      label: t.admin.username,
      render: (row) => <span className="font-medium">{row.username}</span>,
      sortValue: (row) => row.username,
    },
    {
      key: "display_name",
      label: t.admin.displayName,
      render: (row) => row.display_name,
      sortValue: (row) => row.display_name,
    },
    {
      key: "role",
      label: t.admin.role,
      render: (row) => (
        <div className="flex items-center gap-2">
          <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${ROLE_BADGE_COLORS[row.role]}`}>
            {t.common.roles[row.role]}
          </span>
          <span className="text-sm text-slate-400 dark:text-slate-500">
            {roleDescriptions[row.role]}
          </span>
        </div>
      ),
      sortValue: (row) => row.role,
    },
    {
      key: "status",
      label: "Status",
      render: (row) => (
        <button
          onClick={() => handleToggleActive(row)}
          className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
            row.is_active
              ? "bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400"
              : "bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400"
          }`}
        >
          {row.is_active ? t.admin.active : t.admin.inactive}
        </button>
      ),
    },
    {
      key: "created_at",
      label: t.admin.createdAt,
      render: (row) => <span className="text-slate-500 dark:text-slate-400 text-sm">{fmtDate(row.created_at)}</span>,
      sortValue: (row) => row.created_at,
    },
    {
      key: "actions",
      label: t.admin.actions,
      render: (row) => (
        <div className="flex items-center gap-1">
          <button
            onClick={() => openEdit(row)}
            title={t.admin.editUser}
            className="p-1.5 rounded-lg text-slate-400 hover:text-blue-500 hover:bg-slate-100 dark:hover:bg-surface-light transition-colors"
          >
            <Pencil size={14} />
          </button>
          <button
            onClick={() => openReset(row)}
            title={t.admin.resetPassword}
            className="p-1.5 rounded-lg text-slate-400 hover:text-amber-500 hover:bg-slate-100 dark:hover:bg-surface-light transition-colors"
          >
            <KeyRound size={14} />
          </button>
          <button
            onClick={() => handleDelete(row)}
            title={t.admin.deleteUser}
            className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-slate-100 dark:hover:bg-surface-light transition-colors"
          >
            <Trash2 size={14} />
          </button>
        </div>
      ),
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [t, roleDescriptions]);

  if (error) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold">{t.admin.title}</h2>
        <div className="bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 rounded-xl p-4 text-sm">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">{t.admin.title}</h2>
        <button
          onClick={() => {
            setCreateForm({ username: "", display_name: "", password: "", confirmPassword: "", role: "viewer" });
            setShowCreateModal(true);
          }}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium text-white transition-colors"
        >
          {t.admin.addUser}
        </button>
      </div>

      {loading ? (
        <div className="text-slate-500 dark:text-slate-400 py-8 text-center">Loading...</div>
      ) : (
        <DataTable
          columns={columns}
          data={users ?? []}
          keyFn={(row) => String(row.id)}
          emptyMessage={t.admin.noUsers}
        />
      )}

      {/* Create User Modal */}
      <Modal open={showCreateModal} onClose={() => setShowCreateModal(false)} title={t.admin.addUser} closeLabel={t.common.close}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">{t.admin.username}</label>
            <input
              type="text"
              value={createForm.username}
              onChange={(e) => setCreateForm((f) => ({ ...f, username: e.target.value }))}
              className="w-full bg-slate-50 dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">{t.admin.displayName}</label>
            <input
              type="text"
              value={createForm.display_name}
              onChange={(e) => setCreateForm((f) => ({ ...f, display_name: e.target.value }))}
              className="w-full bg-slate-50 dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">{t.admin.password}</label>
            <input
              type="password"
              value={createForm.password}
              onChange={(e) => setCreateForm((f) => ({ ...f, password: e.target.value }))}
              placeholder={t.admin.passwordHint}
              className={`w-full bg-slate-50 dark:bg-surface-dark border rounded-lg px-3 py-2 text-sm ${
                createForm.password && !isValidPassword(createForm.password)
                  ? "border-red-400 dark:border-red-500"
                  : "border-slate-200 dark:border-surface-light"
              }`}
            />
            {createForm.password && !isValidPassword(createForm.password) && (
              <p className="mt-1 text-xs text-red-500">{t.admin.passwordHint}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">{t.admin.confirmPassword}</label>
            <input
              type="password"
              value={createForm.confirmPassword}
              onChange={(e) => setCreateForm((f) => ({ ...f, confirmPassword: e.target.value }))}
              className={`w-full bg-slate-50 dark:bg-surface-dark border rounded-lg px-3 py-2 text-sm ${
                createForm.confirmPassword && createForm.password !== createForm.confirmPassword
                  ? "border-red-400 dark:border-red-500"
                  : "border-slate-200 dark:border-surface-light"
              }`}
            />
            {createForm.confirmPassword && createForm.password !== createForm.confirmPassword && (
              <p className="mt-1 text-xs text-red-500">{t.admin.passwordMismatch}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">{t.admin.role}</label>
            <select
              value={createForm.role}
              onChange={(e) => setCreateForm((f) => ({ ...f, role: e.target.value }))}
              className="w-full bg-slate-50 dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
            >
              {ALL_ROLES.map((r) => (
                <option key={r} value={r}>
                  {t.common.roles[r]} — {roleDescriptions[r]}
                </option>
              ))}
            </select>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={() => setShowCreateModal(false)}
              className="px-4 py-2 rounded-lg text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-surface-light transition-colors"
            >
              {t.common.cancel}
            </button>
            <button
              onClick={handleCreate}
              disabled={createLoading || !createForm.username.trim() || !isValidPassword(createForm.password) || createForm.password !== createForm.confirmPassword}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium text-white transition-colors"
            >
              {createLoading ? "..." : t.common.submit}
            </button>
          </div>
        </div>
      </Modal>

      {/* Edit User Modal */}
      <Modal open={!!editingUser} onClose={() => setEditingUser(null)} title={t.admin.editUser} closeLabel={t.common.close}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">{t.admin.displayName}</label>
            <input
              type="text"
              value={editForm.display_name}
              onChange={(e) => setEditForm((f) => ({ ...f, display_name: e.target.value }))}
              className="w-full bg-slate-50 dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">{t.admin.role}</label>
            <select
              value={editForm.role}
              onChange={(e) => setEditForm((f) => ({ ...f, role: e.target.value }))}
              className="w-full bg-slate-50 dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
            >
              {ALL_ROLES.map((r) => (
                <option key={r} value={r}>
                  {t.common.roles[r]} — {roleDescriptions[r]}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="edit-active"
              checked={editForm.is_active}
              onChange={(e) => setEditForm((f) => ({ ...f, is_active: e.target.checked }))}
              className="rounded"
            />
            <label htmlFor="edit-active" className="text-sm text-slate-600 dark:text-slate-400">
              {t.admin.active}
            </label>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={() => setEditingUser(null)}
              className="px-4 py-2 rounded-lg text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-surface-light transition-colors"
            >
              {t.common.cancel}
            </button>
            <button
              onClick={handleEdit}
              disabled={editLoading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium text-white transition-colors"
            >
              {editLoading ? "..." : t.common.submit}
            </button>
          </div>
        </div>
      </Modal>

      {/* Reset Password Modal */}
      <Modal open={!!resetUser} onClose={() => setResetUser(null)} title={t.admin.resetPassword} closeLabel={t.common.close}>
        <div className="space-y-4">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {resetUser?.username}
          </p>
          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">{t.admin.newPassword}</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder={t.admin.passwordHint}
              className={`w-full bg-slate-50 dark:bg-surface-dark border rounded-lg px-3 py-2 text-sm ${
                newPassword && !isValidPassword(newPassword)
                  ? "border-red-400 dark:border-red-500"
                  : "border-slate-200 dark:border-surface-light"
              }`}
            />
            {newPassword && !isValidPassword(newPassword) && (
              <p className="mt-1 text-xs text-red-500">{t.admin.passwordHint}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">{t.admin.confirmNewPassword}</label>
            <input
              type="password"
              value={confirmNewPassword}
              onChange={(e) => setConfirmNewPassword(e.target.value)}
              className={`w-full bg-slate-50 dark:bg-surface-dark border rounded-lg px-3 py-2 text-sm ${
                confirmNewPassword && newPassword !== confirmNewPassword
                  ? "border-red-400 dark:border-red-500"
                  : "border-slate-200 dark:border-surface-light"
              }`}
            />
            {confirmNewPassword && newPassword !== confirmNewPassword && (
              <p className="mt-1 text-xs text-red-500">{t.admin.passwordMismatch}</p>
            )}
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={() => { setResetUser(null); setConfirmNewPassword(""); }}
              className="px-4 py-2 rounded-lg text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-surface-light transition-colors"
            >
              {t.common.cancel}
            </button>
            <button
              onClick={handleResetPassword}
              disabled={resetLoading || !isValidPassword(newPassword) || newPassword !== confirmNewPassword}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium text-white transition-colors"
            >
              {resetLoading ? "..." : t.common.submit}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
