import axios from "axios";

const BASE_URL = "https://fire35club.duckdns.org/fire35";

const api = axios.create({ baseURL: BASE_URL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// При 401 — токен протух или невалидный → чистим и перезагружаем
// Mini App заново авторизуется через Telegram initData
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.reload();
    }
    return Promise.reject(error);
  }
);

export default api;