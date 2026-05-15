// src/store/searchStore.js
import { create } from 'zustand'
import client from '../api/client'

const useSearchStore = create((set) => ({
  query: '',
  results: [],
  loading: false,
  error: null,

  setQuery: (q) => set({ query: q }),

  search: async (q) => {
    if (!q.trim()) return set({ results: [], query: '' })
    set({ loading: true, error: null, query: q })
    try {
      const res = await client.get('/search/', { params: { q, page: 1 } })
      set({ results: res.data, loading: false })
    } catch {
      set({ error: 'Search failed', loading: false, results: [] })
    }
  },

  clearSearch: () => set({ query: '', results: [], error: null }),
}))

export default useSearchStore