import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout.jsx';
import LoginPage from './pages/LoginPage.jsx';
import ChatPage from './pages/ChatPage.jsx';
import ReportsPage from './pages/ReportsPage.jsx';
import ReportDetailsPage from './pages/ReportDetailsPage.jsx';
import PopularPage from './pages/PopularPage.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import ChatHistoryPage from './pages/ChatHistoryPage.jsx';
import AIInsights from './pages/AIInsights.jsx';


const ProtectedRoute = ({ isAuthenticated, children }) => {
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return children;
};

function App() {
  // Persist auth + role in localStorage so they survive re-renders / hot-reload
  const [isAuthenticated, setIsAuthenticated] = React.useState(
    () => localStorage.getItem('app_auth') === 'true'
  );
  const [userRole, setUserRole] = React.useState(
    () => localStorage.getItem('app_role') || 'user'
  );

  const handleLogin = (role = 'user') => {
    localStorage.setItem('app_auth', 'true');
    localStorage.setItem('app_role', role);
    setIsAuthenticated(true);
    setUserRole(role);
  };

  const isAdmin = userRole === 'admin';

  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<LoginPage onLogin={handleLogin} />} />
      <Route
        path="/chat"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <Layout isAdmin={isAdmin}><ChatPage isAdmin={isAdmin} /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/popular"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <Layout isAdmin={isAdmin}><PopularPage /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <Layout isAdmin={isAdmin}><DashboardPage /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/reports"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <Layout isAdmin={isAdmin}><ReportsPage /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/reports/:id"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <Layout isAdmin={isAdmin}><ReportDetailsPage /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/history"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <Layout isAdmin={isAdmin}><ChatHistoryPage /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/insights"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <Layout isAdmin={isAdmin}><AIInsights /></Layout>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

export default App;
