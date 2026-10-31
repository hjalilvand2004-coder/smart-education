import { useCallback, useEffect, useMemo, useState } from "react";

import api, { getApiError } from "../api";

/*
  مدیریت کاربران و سطوح دسترسی
  - مدیر سامانه: همهٔ کاربران + تغییر نقش + حذف
  - مدیرگروه: فقط استاد و دانشجو (تایید/رد/غیرفعال/بازنشانی رمز)
*/

const ROLE_LABELS = {
  admin: "مدیر سامانه",
  group_manager: "مدیرگروه",
  professor: "استاد",
  student: "دانشجو",
};

const STATUS_LABELS = {
  pending: "در انتظار تایید",
  active: "فعال",
  rejected: "رد شده",
  disabled: "غیرفعال",
};

const STATUS_CLASSES = {
  pending: "warn",
  active: "ok",
  rejected: "err",
  disabled: "muted",
};

const ROLE_FILTERS = [
  { id: "", label: "همهٔ نقش‌ها" },
  { id: "admin", label: "مدیر سامانه" },
  { id: "group_manager", label: "مدیرگروه" },
  { id: "professor", label: "استاد" },
  { id: "student", label: "دانشجو" },
];

const STATUS_FILTERS = [
  { id: "", label: "همهٔ وضعیت‌ها" },
  { id: "pending", label: "در انتظار تایید" },
  { id: "active", label: "فعال" },
  { id: "rejected", label: "رد شده" },
  { id: "disabled", label: "غیرفعال" },
];

export default function UserManagement({ currentUser }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [busyId, setBusyId] = useState(null);

  const isAdmin = currentUser?.role === "admin";
  const canManage = isAdmin || currentUser?.role === "group_manager";

  const loadUsers = useCallback(async () => {
    if (!canManage) return;
    setLoading(true);
    setError("");
    try {
      const params = {};
      if (roleFilter) params.role = roleFilter;
      if (statusFilter) params.status = statusFilter;
      if (search.trim()) params.q = search.trim();
      const res = await api.get("/users", { params });
      setUsers(res.data.users || []);
    } catch (err) {
      setError(getApiError(err));
    } finally {
      setLoading(false);
    }
  }, [canManage, roleFilter, statusFilter, search]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const act = async (userId, action, body = null) => {
    setBusyId(userId);
    setMessage("");
    setError("");
    try {
      const res = await api.post(`/users/${userId}/${action}`, body || {});
      setMessage(res.data.message || "انجام شد.");
      await loadUsers();
    } catch (err) {
      setError(getApiError(err));
    } finally {
      setBusyId(null);
    }
  };

  const changeRole = async (userId, role) => {
    setBusyId(userId);
    setMessage("");
    setError("");
    try {
      const res = await api.put(`/users/${userId}/role`, { role });
      setMessage(res.data.message || "نقش تغییر کرد.");
      await loadUsers();
    } catch (err) {
      setError(getApiError(err));
    } finally {
      setBusyId(null);
    }
  };

  const resetPassword = async (userId, fullName) => {
    const newPassword = window.prompt(
      `رمز عبور جدید برای «${fullName}» (حداقل ۶ نویسه):`
    );
    if (!newPassword) return;
    if (newPassword.length < 6) {
      setError("رمز عبور باید حداقل ۶ نویسه باشد.");
      return;
    }
    await act(userId, "reset-password", { new_password: newPassword });
  };

  const deleteUser = async (userId, fullName) => {
    if (
      !window.confirm(
        `حذف کاربر «${fullName}» قابل بازگشت نیست. مطمئن هستید؟`
      )
    ) {
      return;
    }
    setBusyId(userId);
    setMessage("");
    setError("");
    try {
      const res = await api.delete(`/users/${userId}`);
      setMessage(res.data.message || "کاربر حذف شد.");
      await loadUsers();
    } catch (err) {
      setError(getApiError(err));
    } finally {
      setBusyId(null);
    }
  };

  const pendingCount = useMemo(
    () => users.filter((u) => u.status === "pending").length,
    [users]
  );

  if (!canManage) {
    return (
      <div className="um-panel">
        <div className="app-message">
          این بخش فقط برای مدیر سامانه و مدیرگروه در دسترس است.
        </div>
      </div>
    );
  }

  return (
    <div className="um-panel">
      <div className="um-toolbar">
        <div className="um-filters">
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            aria-label="فیلتر نقش"
          >
            {ROLE_FILTERS.filter(
              (r) => isAdmin || r.id === "" || r.id === "professor" || r.id === "student"
            ).map((r) => (
              <option key={r.id} value={r.id}>
                {r.label}
              </option>
            ))}
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="فیلتر وضعیت"
          >
            {STATUS_FILTERS.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>

          <input
            type="search"
            placeholder="جستجوی نام یا نام کاربری…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <button
          type="button"
          className="um-refresh"
          onClick={loadUsers}
          disabled={loading}
        >
          {loading ? "…" : "⟳"} به‌روزرسانی
        </button>
      </div>

      {pendingCount > 0 && (
        <div className="um-pending-banner">
          {pendingCount} درخواست ثبت‌نام در انتظار تایید است.
        </div>
      )}

      {message && <div className="app-message ok">{message}</div>}
      {error && <div className="app-message error">{error}</div>}

      <div className="um-table-wrap">
        <table className="um-table">
          <thead>
            <tr>
              <th>کاربر</th>
              <th>نقش</th>
              <th>وضعیت</th>
              <th>تاریخ ثبت</th>
              <th>عملیات</th>
            </tr>
          </thead>
          <tbody>
            {users.length === 0 && !loading && (
              <tr>
                <td colSpan={5} className="um-empty">
                  کاربری یافت نشد.
                </td>
              </tr>
            )}
            {users.map((u) => {
              const isSelf = u.id === currentUser.id;
              const manageable =
                isAdmin || u.role === "professor" || u.role === "student";
              return (
                <tr key={u.id} className={busyId === u.id ? "busy" : ""}>
                  <td>
                    <div className="um-user-cell">
                      <div className="um-avatar">
                        {(u.full_name || "?").trim().charAt(0)}
                      </div>
                      <div>
                        <strong>
                          {u.full_name}
                          {isSelf && (
                            <span className="um-you"> (شما)</span>
                          )}
                        </strong>
                        <span dir="ltr" className="um-username">
                          @{u.username}
                        </span>
                      </div>
                    </div>
                  </td>
                  <td>
                    {isAdmin && !isSelf ? (
                      <select
                        className="um-role-select"
                        value={u.role}
                        onChange={(e) => changeRole(u.id, e.target.value)}
                        aria-label="تغییر نقش"
                      >
                        {Object.entries(ROLE_LABELS).map(([id, label]) => (
                          <option key={id} value={id}>
                            {label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className={`um-badge role-${u.role}`}>
                        {u.role_label || ROLE_LABELS[u.role]}
                      </span>
                    )}
                  </td>
                  <td>
                    <span className={`um-badge status-${STATUS_CLASSES[u.status]}`}>
                      {u.status_label || STATUS_LABELS[u.status]}
                    </span>
                  </td>
                  <td className="um-date">{(u.created_at || "").slice(0, 10) || "—"}</td>
                  <td>
                    <div className="um-actions">
                      {u.status === "pending" && manageable && (
                        <>
                          <button
                            type="button"
                            className="um-btn ok"
                            onClick={() => act(u.id, "approve")}
                          >
                            تایید
                          </button>
                          <button
                            type="button"
                            className="um-btn danger"
                            onClick={() => act(u.id, "reject")}
                          >
                            رد
                          </button>
                        </>
                      )}
                      {u.status === "active" && manageable && !isSelf && (
                        <button
                          type="button"
                          className="um-btn warn"
                          onClick={() => act(u.id, "disable")}
                        >
                          غیرفعال
                        </button>
                      )}
                      {u.status === "disabled" && manageable && (
                        <button
                          type="button"
                          className="um-btn ok"
                          onClick={() => act(u.id, "enable")}
                        >
                          فعال‌سازی
                        </button>
                      )}
                      {u.status === "rejected" && manageable && (
                        <button
                          type="button"
                          className="um-btn ok"
                          onClick={() => act(u.id, "approve")}
                        >
                          تایید مجدد
                        </button>
                      )}
                      {manageable && !isSelf && (
                        <button
                          type="button"
                          className="um-btn"
                          onClick={() => resetPassword(u.id, u.full_name)}
                        >
                          بازنشانی رمز
                        </button>
                      )}
                      {isAdmin && !isSelf && (
                        <button
                          type="button"
                          className="um-btn danger"
                          onClick={() => deleteUser(u.id, u.full_name)}
                        >
                          حذف
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="um-note">
        راهنما: ثبت‌نام «استاد» توسط مدیر سامانه یا مدیرگروه تایید می‌شود؛
        ثبت‌نام «مدیرگروه» فقط توسط مدیر سامانه. دانشجو به‌صورت خودکار فعال می‌شود.
      </p>
    </div>
  );
}
