import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ children }) {
  const { doctor, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-slate-100">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 border-4 border-blue-200 border-t-blue-700 rounded-full animate-spin" />
          <p className="text-slate-500 text-sm">Yükleniyor...</p>
        </div>
      </div>
    );
  }

  if (!doctor) {
    return <Navigate to="/login" replace />;
  }

  return children;
}
