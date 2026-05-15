// src/store/authStore.js
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const useAuthStore = create(
  persist(
    (set) => ({
      user: null,
      token: null,

      setAuth: (user, token) => {
        localStorage.setItem('nud_token', token)
        set({ user, token })
      },

      clearAuth: () => {
        localStorage.removeItem('nud_token')
        set({ user: null, token: null })
      },

      isLoggedIn: () => {
        const state = useAuthStore.getState()
        return !!state.token && !!state.user
      },
    }),
    {
      name: 'nud_auth',
      partialize: (state) => ({ user: state.user, token: state.token }),
    }
  )
)

export default useAuthStore