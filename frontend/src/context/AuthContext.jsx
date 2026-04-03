import { createContext, useContext, useState, useEffect } from 'react';
import { MOCK_DOCTOR } from '../data/mockData';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [doctor, setDoctor] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('deepderm_token');
    // Şimdilik token varsa Dr. Ayşe olarak doğrudan geri açabilir, çünkü token korumalı.
    if (stored) {
      setDoctor({ id: '7d3eb756-c061-431c-82c0-5ce4d7c0285c', name: 'Dr. Ayşe Kaya', email: 'ayse.kaya@deripoliklinigi.com', specialty: 'Dermatoloji Uzmanı' });
    }
    setLoading(false);
  }, []);

  const login = async (email, password) => {
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem('deepderm_token', data.token);
        setDoctor({ id: data.doctorId, name: data.name, email: data.email, specialty: 'Dermatoloji Uzmanı' });
        return { success: true };
      } else {
         return { success: false, message: 'Geçersiz kimlik bilgileri.' };
      }
    } catch(err) {
      return { success: false, message: 'Bağlantı hatası.' };
    }
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
