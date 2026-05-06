import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ToastProvider } from './hooks/useToast'
import { Login }     from './pages/Login'
import { Dashboard } from './pages/Dashboard'
import { Users }     from './pages/Users'
import { Providers } from './pages/Providers'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('admin_token')
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<RequireAuth><Dashboard /></RequireAuth>} />
          <Route path="/users" element={<RequireAuth><Users /></RequireAuth>} />
          <Route path="/providers" element={<RequireAuth><Providers /></RequireAuth>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  )
}
