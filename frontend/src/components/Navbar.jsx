// src/components/Navbar.jsx
import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import useSearchStore from '../store/searchStore'

export default function Navbar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, clearAuth } = useAuthStore()
  const { query, search, clearSearch } = useSearchStore()
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const searchRef = useRef(null)
  const debounceRef = useRef(null)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    if (searchOpen && searchRef.current) {
      searchRef.current.focus()
    }
  }, [searchOpen])

  const handleSearch = (e) => {
    const val = e.target.value
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      if (val.trim()) {
        search(val)
        navigate(`/search?q=${encodeURIComponent(val)}`)
      } else {
        clearSearch()
      }
    }, 400)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      setSearchOpen(false)
      clearSearch()
    }
  }

  const navLinks = [
    { label: 'Home',    path: '/' },
    { label: 'Movies',  path: '/search?type=movie' },
    { label: 'Series',  path: '/search?type=series' },
    { label: 'Anime',   path: '/search?genre=anime' },
    { label: 'K-Drama', path: '/search?genre=kdrama' },
  ]

  return (
    <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
      scrolled ? 'bg-bg/95 backdrop-blur-sm border-b border-surface-border' : 'bg-transparent'
    }`}>
      <div className="max-w-screen-xl mx-auto px-4 md:px-8 h-16 flex items-center justify-between gap-4">

        {/* logo */}
        <Link to="/" className="text-accent-gradient font-extrabold text-2xl tracking-tighter shrink-0">
          nud
        </Link>

        {/* desktop nav links */}
        <div className="hidden md:flex items-center gap-6">
          {navLinks.map((l) => (
            <Link
              key={l.path}
              to={l.path}
              className={`text-sm transition-colors duration-200 ${
                location.pathname === l.path
                  ? 'text-white font-medium'
                  : 'text-gray-500 hover:text-white'
              }`}
            >
              {l.label}
            </Link>
          ))}
        </div>

        {/* right side */}
        <div className="flex items-center gap-3">

          {/* search */}
          <div className="relative">
            {searchOpen ? (
              <div className="flex items-center gap-2 bg-surface border border-surface-border rounded-full px-4 py-2">
                <svg className="w-3.5 h-3.5 text-gray-500 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                </svg>
                <input
                  ref={searchRef}
                  defaultValue={query}
                  onChange={handleSearch}
                  onKeyDown={handleKeyDown}
                  placeholder="Search titles..."
                  className="bg-transparent outline-none text-sm text-white placeholder-gray-600 w-40 md:w-52"
                />
                <button onClick={() => { setSearchOpen(false); clearSearch() }} className="text-gray-600 hover:text-white">
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M18 6 6 18M6 6l12 12"/>
                  </svg>
                </button>
              </div>
            ) : (
              <button
                onClick={() => setSearchOpen(true)}
                className="w-9 h-9 flex items-center justify-center rounded-full bg-surface border border-surface-border text-gray-400 hover:text-white hover:border-accent/40 transition-all"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                </svg>
              </button>
            )}
          </div>

          {/* auth */}
          {user ? (
            <div className="relative group">
              <button className="flex items-center gap-2">
                <img
                  src={user.avatar_url || `https://ui-avatars.com/api/?name=${user.display_name}&background=facc15&color=0a0800`}
                  alt={user.display_name}
                  className="w-8 h-8 rounded-full object-cover border border-accent/30"
                />
              </button>
              {/* dropdown */}
              <div className="absolute right-0 top-10 w-44 bg-surface border border-surface-border rounded-xl overflow-hidden opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 shadow-xl">
                <div className="px-4 py-3 border-b border-surface-border">
                  <p className="text-sm font-medium text-white truncate">{user.display_name}</p>
                  <p className="text-xs text-gray-500 truncate">{user.email}</p>
                </div>
                <button
                  onClick={() => { clearAuth(); navigate('/') }}
                  className="w-full px-4 py-2.5 text-left text-sm text-gray-400 hover:text-white hover:bg-surface-hover transition-colors"
                >
                  Sign out
                </button>
              </div>
            </div>
          ) : (
            <Link
              to="/login"
              className="hidden md:block accent-gradient text-[#0a0800] text-sm font-bold px-5 py-2 rounded-full hover:opacity-90 transition-opacity"
            >
              Sign in
            </Link>
          )}

          {/* mobile hamburger */}
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="md:hidden w-9 h-9 flex items-center justify-center rounded-full bg-surface border border-surface-border text-gray-400"
          >
            {menuOpen ? (
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6 6 18M6 6l12 12"/>
              </svg>
            ) : (
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 12h18M3 6h18M3 18h18"/>
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* mobile menu */}
      {menuOpen && (
        <div className="md:hidden bg-bg/98 border-t border-surface-border px-4 py-4 flex flex-col gap-1">
          {navLinks.map((l) => (
            <Link
              key={l.path}
              to={l.path}
              onClick={() => setMenuOpen(false)}
              className={`px-4 py-3 rounded-lg text-sm transition-colors ${
                location.pathname === l.path
                  ? 'bg-accent-muted text-accent font-medium'
                  : 'text-gray-400 hover:text-white hover:bg-surface'
              }`}
            >
              {l.label}
            </Link>
          ))}
          {!user && (
            <Link
              to="/login"
              onClick={() => setMenuOpen(false)}
              className="mt-2 accent-gradient text-[#0a0800] text-sm font-bold px-4 py-3 rounded-lg text-center"
            >
              Sign in with Google
            </Link>
          )}
        </div>
      )}
    </nav>
  )
}