import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AuthProvider, useAuth } from './context/AuthContext.js';
import Nav from './components/Nav.js';
import Login from './pages/Login.js';
import Home from './pages/Home.js';
import Voice from './pages/Voice.js';
import Ticket from './pages/Ticket.js';
import MyAppointments from './pages/MyAppointments.js';
import DoctorDashboard from './pages/DoctorDashboard.js';
import AdminDashboard from './pages/AdminDashboard.js';
import AdminUsers from './pages/AdminUsers.js';

function Protected({ children, roles }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center text-muted-foreground">
        Loading…
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
}

function ConditionalNav() {
  const location = useLocation();
  if (location.pathname === '/login') return null;
  return <Nav />;
}

function AppRouter() {
  return (
    <>
      <ConditionalNav />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Protected><Home /></Protected>} />
        <Route path="/talk" element={<Protected><Voice /></Protected>} />
        <Route path="/appointments" element={<Protected><MyAppointments /></Protected>} />
        <Route path="/ticket/:id" element={<Protected><Ticket /></Protected>} />
        <Route path="/doctor" element={<Protected roles={['doctor', 'admin']}><DoctorDashboard /></Protected>} />
        <Route path="/admin" element={<Protected roles={['admin']}><AdminDashboard /></Protected>} />
        <Route path="/admin/calendar" element={<Protected roles={['admin']}><AdminDashboard /></Protected>} />
        <Route path="/admin/users" element={<Protected roles={['admin']}><AdminUsers /></Protected>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRouter />
        <Toaster position="top-right" />
      </BrowserRouter>
    </AuthProvider>
  );
}
