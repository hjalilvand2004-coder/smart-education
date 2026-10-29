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

const api = axios.create({
  baseURL: resolveBaseUrl(),
  timeout: 120000
});

export function getApiError(error) {
  return (
    error?.response?.data?.detail ||
    error?.message ||
    "خطای ناشناخته‌ای رخ داد"
  );
}

export default api;