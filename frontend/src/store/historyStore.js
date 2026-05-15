// src/store/historyStore.js
import { create } from 'zustand'
import client from '../api/client'

const useHistoryStore = create((set, get) => ({
  history: [],
  loading: false,

  fetchHistory: async () => {
    set({ loading: true })
    try {
      const res = await client.get('/history/')
      set({ history: res.data, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  upsertHistory: async (payload) => {
    try {
      const res = await client.post('/history/', payload)
      const updated = get().history.map((h) =>
        h.id === res.data.id ? res.data : h
      )
      const exists = get().history.find((h) => h.id === res.data.id)
      set({ history: exists ? updated : [res.data, ...get().history] })
    } catch {
      // silent — history is non-critical
    }
  },

  deleteHistory: async (id) => {
    try {
      await client.delete(`/history/${id}`)
      set({ history: get().history.filter((h) => h.id !== id) })
    } catch {}
  },

  clearHistory: () => set({ history: [] }),
}))

export default useHistoryStore