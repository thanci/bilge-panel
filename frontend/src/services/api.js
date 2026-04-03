/**
 * src/services/api.js — Axios instance ve JWT interceptor'ları.
 *
 * Düzeltmeler (Bug-Fix Patch):
 *   1. tokenStorage null-guard: "undefined"/"null" string değerleri
 *      Authorization header'a eklenmez.
 *   2. Refresh token response: data.data.access_token → data.access_token
 *      fallback eklendi (her iki format'a dayanıklı).
 *   3. Request interceptor: boş string token'ları da filtreler.
 */

import axios  from 'axios'
import router from '@/router'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

// ─── Axios instance ────────────────────────────────────────
const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// ─── Token yönetimi yardımcıları ──────────────────────────
const TOKEN_KEY         = 'bv_access_token'
const REFRESH_TOKEN_KEY = 'bv_refresh_token'

const INVALID_VALUES = new Set(['', 'undefined', 'null', 'false'])

function isValidToken(val) {
  return typeof val === 'string' && val.length > 10 && !INVALID_VALUES.has(val)
}

export const tokenStorage = {
  getAccess() {
    const v = localStorage.getItem(TOKEN_KEY)
    return isValidToken(v) ? v : null
  },
  getRefresh() {
    const v = localStorage.getItem(REFRESH_TOKEN_KEY)
    return isValidToken(v) ? v : null
  },
  setAccess(token) {
    if (isValidToken(token)) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  },
  setRefresh(token) {
    if (isValidToken(token)) localStorage.setItem(REFRESH_TOKEN_KEY, token)
    else localStorage.removeItem(REFRESH_TOKEN_KEY)
  },
  setTokens(access, refresh) {
    this.setAccess(access)
    this.setRefresh(refresh)
  },
  clearAll() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  },
}

// ─── Request Interceptor: Her isteğe JWT header ekle ──────
api.interceptors.request.use(
  (config) => {
    const token = tokenStorage.getAccess()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// ─── Response Interceptor: 401'de token yenile ─────────────
let _isRefreshing = false
let _refreshQueue = []

function _processQueue(error, token = null) {
  _refreshQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error)
    else resolve(token)
  })
  _refreshQueue = []
}

api.interceptors.response.use(
  (response) => response,

  async (error) => {
    const original = error.config

    if (error.response?.status === 401 && !original._retried) {
      const refreshToken = tokenStorage.getRefresh()
      if (!refreshToken) {
        _clearAndRedirect()
        return Promise.reject(error)
      }

      if (_isRefreshing) {
        return new Promise((resolve, reject) => {
          _refreshQueue.push({ resolve, reject })
        }).then(token => {
          original.headers.Authorization = `Bearer ${token}`
          return api(original)
        })
      }

      original._retried = true
      _isRefreshing     = true

      try {
        const { data } = await axios.post(`${BASE_URL}/auth/refresh`, null, {
          headers: { Authorization: `Bearer ${refreshToken}` },
        })

        // Backend formatına dayanıklı çıkarım: data.data.access_token veya data.access_token
        const newToken =
          data?.data?.access_token ??
          data?.access_token

        if (!isValidToken(newToken)) {
          throw new Error('Refresh yanıtında geçerli token yok')
        }

        tokenStorage.setAccess(newToken)
        _processQueue(null, newToken)

        original.headers.Authorization = `Bearer ${newToken}`
        return api(original)

      } catch (refreshError) {
        _processQueue(refreshError, null)
        _clearAndRedirect()
        return Promise.reject(refreshError)
      } finally {
        _isRefreshing = false
      }
    }

    return Promise.reject(error)
  },
)

function _clearAndRedirect() {
  tokenStorage.clearAll()
  router.push({ name: 'login' })
}

export default api
