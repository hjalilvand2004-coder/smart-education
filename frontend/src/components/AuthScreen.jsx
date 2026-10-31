import { useState } from "react";

import api, { getApiError, setToken } from "../api";

/*
  صفحهٔ ورود / ثبت‌نام — سامانه هوشمند آموزش
  نقش‌های قابل ثبت: مدیرگروه، استاد، دانشجو
  ثبت‌نام استاد و مدیرگروه نیازمند تایید است.
*/

const ROLE_OPTIONS = [
  {
    id: "student",
    label: "دانشجو",
    icon: "🎓",
    hint: "فعال‌سازی خودکار — بلافاصله وارد می‌شوید",
  },
  {
    id: "professor",
    label: "استاد",
    icon: "👨‍🏫",
    hint: "نیازمند تایید مدیر سامانه یا مدیرگروه",
  },
  {
    id: "group_manager",
    label: "مدیرگروه",
    icon: "🧑‍💼",
    hint: "نیازمند تایید مدیر سامانه",
  },
];

export default function AuthScreen({ onAuthSuccess }) {
  const [mode, setMode] = useState("login"); // login | register
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [loginForm, setLoginForm] = useState({
    username: "",
    password: "",
  });

  const [regForm, setRegForm] = useState({
    full_name: "",
    username: "",
    email: "",
    password: "",
    role: "student",
  });

  const handleLogin = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api.post("/auth/login", {
        username: loginForm.username,
        password: loginForm.password,
      });
      setToken(res.data.token);
      onAuthSuccess(res.data.user);
    } catch (err) {
      setError(getApiError(err));
    } finally {
      setBusy(false);
    }
  };

  const handleRegister = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const res = await api.post("/auth/register", regForm);
      if (res.data.requires_approval) {
        setMode("login");
        setNotice(res.data.message);
        setRegForm({
          full_name: "",
          username: "",
          email: "",
          password: "",
          role: "student",
        });
      } else {
        const loginRes = await api.post("/auth/login", {
          username: regForm.username,
          password: regForm.password,
        });
        setToken(loginRes.data.token);
        onAuthSuccess(loginRes.data.user);
      }
    } catch (err) {
      setError(getApiError(err));
    } finally {
      setBusy(false);
    }
  };

  const selectedRole = ROLE_OPTIONS.find((r) => r.id === regForm.role);

  return (
    <div className="auth-screen">
      <div className="auth-backdrop" aria-hidden="true"></div>

      <div className="auth-card">
        <div className="auth-brand">
          <div className="auth-logo">🎓</div>
          <h1>سامانه هوشمند آموزش و آزمون</h1>
          <p>تولید محتوای هوشمند، آزمون‌سازی و گزارش‌سازی چهارفرمتی</p>
        </div>

        <div className="auth-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "login"}
            className={mode === "login" ? "auth-tab active" : "auth-tab"}
            onClick={() => {
              setMode("login");
              setError("");
              setNotice("");
            }}
          >
            ورود به سامانه
          </button>

          <button
            type="button"
            role="tab"
            aria-selected={mode === "register"}
            className={mode === "register" ? "auth-tab active" : "auth-tab"}
            onClick={() => {
              setMode("register");
              setError("");
              setNotice("");
            }}
          >
            ثبت‌نام
          </button>
        </div>

        {error && <div className="auth-alert error">{error}</div>}
        {notice && <div className="auth-alert ok">{notice}</div>}

        {mode === "login" ? (
          <form className="auth-form" onSubmit={handleLogin}>
            <label>
              نام کاربری
              <input
                type="text"
                dir="ltr"
                autoComplete="username"
                value={loginForm.username}
                onChange={(e) =>
                  setLoginForm({ ...loginForm, username: e.target.value })
                }
                required
              />
            </label>

            <label>
              رمز عبور
              <input
                type="password"
                dir="ltr"
                autoComplete="current-password"
                value={loginForm.password}
                onChange={(e) =>
                  setLoginForm({ ...loginForm, password: e.target.value })
                }
                required
              />
            </label>

            <button type="submit" className="auth-submit" disabled={busy}>
              {busy ? "در حال ورود…" : "ورود"}
            </button>

            <div className="auth-hint">
              حساب پیش‌فرض مدیر سامانه: <code dir="ltr">admin / admin123</code>
              <br />
              (پس از اولین ورود، رمز را تغییر دهید)
            </div>
          </form>
        ) : (
          <form className="auth-form" onSubmit={handleRegister}>
            <label>
              نام و نام خانوادگی
              <input
                type="text"
                value={regForm.full_name}
                onChange={(e) =>
                  setRegForm({ ...regForm, full_name: e.target.value })
                }
                minLength={3}
                required
              />
            </label>

            <div className="auth-row">
              <label>
                نام کاربری
                <input
                  type="text"
                  dir="ltr"
                  autoComplete="off"
                  value={regForm.username}
                  onChange={(e) =>
                    setRegForm({ ...regForm, username: e.target.value })
                  }
                  minLength={3}
                  pattern="[A-Za-z0-9._]+"
                  title="فقط حروف انگلیسی، عدد، نقطه و زیرخط"
                  required
                />
              </label>

              <label>
                ایمیل (اختیاری)
                <input
                  type="email"
                  dir="ltr"
                  value={regForm.email}
                  onChange={(e) =>
                    setRegForm({ ...regForm, email: e.target.value })
                  }
                />
              </label>
            </div>

            <label>
              رمز عبور (حداقل ۶ نویسه)
              <input
                type="password"
                dir="ltr"
                autoComplete="new-password"
                value={regForm.password}
                onChange={(e) =>
                  setRegForm({ ...regForm, password: e.target.value })
                }
                minLength={6}
                required
              />
            </label>

            <div className="auth-roles">
              <span className="auth-roles-title">نقش کاربری:</span>
              <div className="auth-roles-grid">
                {ROLE_OPTIONS.map((role) => (
                  <button
                    key={role.id}
                    type="button"
                    className={
                      regForm.role === role.id
                        ? "auth-role active"
                        : "auth-role"
                    }
                    onClick={() => setRegForm({ ...regForm, role: role.id })}
                  >
                    <span className="auth-role-icon">{role.icon}</span>
                    <span>{role.label}</span>
                  </button>
                ))}
              </div>
              {selectedRole && (
                <small className="auth-role-hint">{selectedRole.hint}</small>
              )}
            </div>

            <button type="submit" className="auth-submit" disabled={busy}>
              {busy ? "در حال ثبت‌نام…" : "ثبت‌نام"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
