import axios from "axios";

// آدرس پایهٔ API:
// - اگر VITE_API_BASE_URL تنظیم شده باشد از آن استفاده می‌شود
// - در حالت توسعه (پورت 5173) به بک‌اند روی 8000 وصل می‌شود
// - در حالت پرتابل/تولیدی، همان آدرسی که UI از آن سرو شده
//   (بدون هاردکد پورت — تا اجرای همزمان با سایر سامانه‌ها ممکن باشد)
function resolveBaseUrl() {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  if (typeof window !== "undefined" && window.location.port === "5173") {
    return "http://127.0.0.1:8000/api";
  }
  if (typeof window !== "undefined") {
    return window.location.origin + "/api";
  }
  return "http://127.0.0.1:8000/api";
}

const TOKEN_KEY = "smart_education_token";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || "";
  } catch (e) {
    return "";
  }
}

export function setToken(token) {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch (e) {
    /* ignore */
  }
}

const api = axios.create({
  baseURL: resolveBaseUrl(),
  timeout: 120000
});

// افزودن توکن نشست به همهٔ درخواست‌ها
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// در صورت منقضی شدن نشست، کاربر به صفحهٔ ورود برمی‌گردد
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error?.response?.status === 401 &&
      typeof window !== "undefined" &&
      !String(error?.config?.url || "").includes("/auth/")
    ) {
      setToken("");
      if (!window.location.hash.includes("auth-expired")) {
        window.location.hash = "auth-expired";
        window.location.reload();
      }
    }
    return Promise.reject(error);
  }
);

export function getApiError(error) {
  return (
    error?.response?.data?.detail ||
    error?.message ||
    "خطای ناشناخته‌ای رخ داد"
  );
}

export default api;
