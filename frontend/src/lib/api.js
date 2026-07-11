import axios from 'axios';

const BACKEND = process.env.REACT_APP_BACKEND_URL;

export const api = axios.create({
  baseURL: `${BACKEND}/api`,
  withCredentials: true,
});

// Attach Bearer token if stored (helpful for testing / mobile clients)
api.interceptors.request.use((config) => {
  const t = typeof window !== 'undefined' ? window.localStorage.getItem('session_token') : null;
  if (t) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${t}`;
  }
  return config;
});

export const BACKEND_URL = BACKEND;
