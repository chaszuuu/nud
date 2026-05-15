// src/pages/Search.jsx
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Navbar from '../components/Navbar'
import ContentGrid from '../components/ContentGrid'
import useSearchStore from '../store/searchStore'

const GENRES = [
  { id: 'all',      label: 'All' },
  { id: 'anime',    label: 'Anime' },
  { id: 'kdrama',   label: 'K-Drama' },
  { id: 'movie',    label: 'Movies' },
  { id: 'action',   label: 'Action' },
  { id: 'romance',  label: 'Romance' },
  { id: 'thriller', label: 'Thriller' },
  { id: 'fantasy',  label: 'Fantasy' },
]

export default function Search() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { results, loading, search, clearSearch } = useSearchStore()
  const [activeGenre, setActiveGenre] = useState(searchParams.get('genre') || 'all')
  const q = searchParams.get('q') || ''

  useEffect(() => {
    if (q) {
      search(q)
    } else if (activeGenre && activeGenre !== 'all') {
      search(activeGenre)
    } else {
      search('popular')
    }
    return () => clearSearch()
  }, [q, activeGenre])

  const handleGenre = (id) => {
    setActiveGenre(id)
    const params = {}
    if (id !== 'all') params.genre = id
    setSearchParams(params)
  }

  return (
    <div className="min-h-screen bg-bg">
      <Navbar />
      <div className="max-w-screen-xl mx-auto px-6 md:px-12 pt-28 pb-20">

        {/* header */}
        <div className="mb-8">
          {q ? (
            <div>
              <p className="text-gray-500 text-sm mb-1">Search results for</p>
              <h1 className="text-2xl font-bold text-white">"{q}"</h1>
            </div>
          ) : (
            <h1 className="text-2xl font-bold text-white">Browse</h1>
          )}
        </div>

        {/* genre filter */}
        {!q && (
          <div className="flex flex-wrap gap-2 mb-8">
            {GENRES.map((g) => (
              <button
                key={g.id}
                onClick={() => handleGenre(g.id)}
                className={`px-4 py-2 rounded-full text-xs border transition-all ${
                  activeGenre === g.id
                    ? 'accent-gradient text-[#0a0800] font-bold border-transparent'
                    : 'bg-surface border-surface-border text-gray-400 hover:text-white hover:border-white/20'
                }`}
              >
                {g.label}
              </button>
            ))}
          </div>
        )}

        {/* results count */}
        {!loading && results.length > 0 && (
          <p className="text-gray-600 text-xs mb-4">{results.length} titles found</p>
        )}

        <ContentGrid items={results} loading={loading} />
      </div>
    </div>
  )
}