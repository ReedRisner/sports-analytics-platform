import axios from 'axios'

// @ts-ignore - Vite env variable
const API_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8000'

/**
 * Axios instance with base configuration
 */
export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000, // 10 second timeout
})

/**
 * Request interceptor: Add auth token to all requests
 */
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

/**
 * Response interceptor: Handle auth errors globally
 */
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // If 401 Unauthorized, clear token and redirect to login
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    
    // Log errors in development (except expected 404s)
    const isDev = process.env.NODE_ENV === 'development'
    if (isDev) {
      const is404 = error.response?.status === 404
      const isExpectedMissing = error.config?.url?.includes('/game-log')
      
      // Don't log 404s for endpoints we know don't exist yet
      if (!is404 || !isExpectedMissing) {
        console.error('API Error:', error.response?.data || error.message)
      }
    }
    
    return Promise.reject(error)
  }
)