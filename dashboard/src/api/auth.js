import axios from 'axios'

// In dev: Vite proxy forwards /auth, /shorten, /stats → http://127.0.0.1:8000
// In prod: set VITE_API_URL to your deployed backend URL
const BASE = import.meta.env.VITE_API_URL || ''

const api = axios.create({ baseURL: BASE })

// Attach token to every request automatically
api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Auto-refresh on 401
api.interceptors.response.use(
  res => res,
  async err => {
    if (err.response?.status === 401) {
      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        try {
          const { data } = await axios.post(`${BASE}/auth/refresh`, { refresh_token: refresh })
          localStorage.setItem('access_token', data.access_token)
          localStorage.setItem('refresh_token', data.refresh_token)
          err.config.headers.Authorization = `Bearer ${data.access_token}`
          return axios(err.config)
        } catch {
          localStorage.clear()
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(err)
  }
)

export default api

export function getToken() {
  return localStorage.getItem('access_token')
}

export function logout() {
  localStorage.clear()
  window.location.href = '/login'
}
