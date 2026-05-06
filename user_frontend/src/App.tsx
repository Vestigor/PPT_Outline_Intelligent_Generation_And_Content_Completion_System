import { type ReactNode } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { ToastProvider } from './hooks/useToast'
import { Login }          from './pages/Login'
import { Register }       from './pages/Register'
import { ForgotPassword } from './pages/ForgotPassword'
import { Chat }           from './pages/Chat'
import { Knowledge }      from './pages/Knowledge'
import { Models }         from './pages/Models'

function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation()
  const token = localStorage.getItem('token')
  if (!token) return <Navigate to="/login" state={{ from: location }} replace />
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <Routes>
          <Route path="/login"           element={<Login />} />
          <Route path="/register"        element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/"                element={<RequireAuth><Chat /></RequireAuth>} />
          <Route path="/chat/:id"        element={<RequireAuth><Chat /></RequireAuth>} />
          <Route path="/knowledge"       element={<RequireAuth><Knowledge /></RequireAuth>} />
          <Route path="/models"          element={<RequireAuth><Models /></RequireAuth>} />
          <Route path="*"                element={<Navigate to="/" replace />} />
        </Routes>
      </ToastProvider>
    </BrowserRouter>
  )
}
