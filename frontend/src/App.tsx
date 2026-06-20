/**
 * Component/Module: App
 * Path: frontend/src/App.tsx
 *
 * Descripcion:
 *   Raiz del arbol de componentes. Define las rutas de la aplicacion
 *   con React Router v6. Cada ruta corresponde a una pantalla del TFG:
 *
 *   /           -> NickPage    (pantalla de bienvenida, introduce nickname)
 *   /benchmark  -> BenchmarkPage  (formulario + tarjetas LLM en paralelo)
 *   /evaluar/:evaluacionId -> EvaluationPage (valoracion de respuestas)
 *   /historial  -> HistorialPage  (historial de evaluaciones, vista user/admin)
 *   /dashboard  -> DashboardPage  (graficas y metricas agregadas)
 *
 * Sprint: Sprint 3
 */
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import Layout from '@/components/shared/Layout'
import NickPage from '@/pages/NickPage'
import BenchmarkPage from '@/pages/BenchmarkPage'
import EvaluationPage from '@/pages/EvaluationPage'
import HistorialPage from '@/pages/HistorialPage'
import DashboardPage from '@/pages/DashboardPage'
import { useUsuarioStore } from '@/store/usuarioStore'
import { useAdminStore } from '@/store/adminStore'

/** Redirige a / si no hay sesion activa (usuario web o administrador). */
function RutaProtegida() {
  const tokenUsuario = useUsuarioStore((s) => s.token)
  const tokenAdmin = useAdminStore((s) => s.token)
  if (!tokenUsuario && !tokenAdmin) return <Navigate to="/" replace />
  return <Outlet />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Pantalla de entrada: sin layout (pantalla completa centrada) */}
        <Route path="/" element={<NickPage />} />

        {/* Pantallas protegidas: requieren sesion de usuario web o admin */}
        <Route element={<RutaProtegida />}>
          <Route element={<Layout />}>
            <Route path="/benchmark" element={<BenchmarkPage />} />
            <Route path="/evaluar/:evaluacionId" element={<EvaluationPage />} />
            <Route path="/historial" element={<HistorialPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
          </Route>
        </Route>

        {/* Cualquier ruta desconocida vuelve al inicio */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
