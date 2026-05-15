// src/api/client.js
import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: 10000,
})

// attach JWT to every request if present
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('nud_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// handle 401 globally — clear token and redirect to home
client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('nud_token')
      window.location.href = '/'
    }
    return Promise.reject(err)
  }
)

export default client