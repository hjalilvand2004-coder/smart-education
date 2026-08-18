import axios from "axios";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000/api",
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