import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import Footer from './components/Footer'
import Home from './pages/Home'
import Search from './pages/Search'
import Movie from './pages/Movie'
import Series from './pages/Series'
import Watch from './pages/Watch'
import Login from './pages/Login'

function Layout() {
  const location = useLocation()
  const hideFooter = location.pathname.startsWith('/watch')

  return (
    <>
      <Routes>
        <Route path="/"              element={<Home />} />
        <Route path="/search"        element={<Search />} />
        <Route path="/movie/:id"     element={<Movie />} />
        <Route path="/series/:id"    element={<Series />} />
        <Route path="/watch/:id"     element={<Watch />} />
        <Route path="/login"         element={<Login />} />
        <Route path="/auth/callback" element={<Login />} />
      </Routes>
      {!hideFooter && <Footer />}
    </>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Layout />
    </BrowserRouter>
  )
}

export default App