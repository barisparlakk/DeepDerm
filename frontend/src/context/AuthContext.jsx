import { createContext, useContext, useState, useEffect } from 'react';
import { MOCK_DOCTOR } from '../data/mockData';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [doctor, setDoctor] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('deepderm_token');
    if (stored) {
      setDoctor(MOCK_DOCTOR);
    }
    setLoading(false);
  }, []);

  const login = async (email, password) => {
    // Mock auth — replace with real API call
    if (email && password.length >= 4) {
      const token = 'mock_jwt_token_' + Date.now();
      localStorage.setItem('deepderm_token', token);
      setDoctor(MOCK_DOCTOR);
      return { success: true };
    }
    return { success: false, message: 'E-posta veya şifre hatalı.' };
  };

  const logout = () => {
    localStorage.removeItem('deepderm_token');
    setDoctor(null);
  };

  return (
    <AuthContext.Provider value={{ doctor, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
