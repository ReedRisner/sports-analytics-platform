import { apiClient } from '../client'
import type { AuthResponse, User } from '../types'

/**
 * Auth API endpoints
 */
export const authAPI = {
  /**
   * Login with email and password
   */
  login: async (email: string, password: string): Promise<AuthResponse> => {
    const { data } = await apiClient.post('/auth/login', {
      email,
      password,
    })
    
    // Store token in localStorage
    if (data.access_token) {
      localStorage.setItem('token', data.access_token)
    }
    
    return data
  },

  /**
   * Register new user
   */
  register: async (email: string, password: string): Promise<AuthResponse> => {
    const { data } = await apiClient.post('/auth/register', {
      email,
      password,
    })
    
    // Store token in localStorage
    if (data.access_token) {
      localStorage.setItem('token', data.access_token)
    }
    
    return data
  },

  /**
   * Logout (clear token)
   */
  logout: () => {
    localStorage.removeItem('token')
  },

  /**
   * Get current user profile
   */
  getCurrentUser: async (): Promise<User> => {
    const { data } = await apiClient.get('/auth/me')
    return data
  },

  /**
   * Check if user has valid token
   */
  isAuthenticated: (): boolean => {
    return !!localStorage.getItem('token')
  },
}