import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { authLogin, authRegister, LoginResponse } from '../api/auth';

interface PatientUser {
  patientId: string;
  name: string;
  surname: string;
  email: string;
  photoUploadPeriodDays: number;
}

interface AuthContextType {
  patient: PatientUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: {
    name: string;
    surname: string;
    age: number;
    gender: string;
    email: string;
    password: string;
    kvkkConsent: boolean;
  }) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

const TOKEN_KEY = 'deepderm_patient_token';
const USER_KEY  = 'deepderm_patient_user';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [patient, setPatient] = useState<PatientUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const stored = await AsyncStorage.getItem(USER_KEY);
        if (stored) setPatient(JSON.parse(stored));
      } catch (_) {}
      finally { setLoading(false); }
    })();
  }, []);

  const persist = async (resp: LoginResponse) => {
    await AsyncStorage.setItem(TOKEN_KEY, resp.token);
    const user: PatientUser = {
      patientId: resp.patientId,
      name: resp.name,
      surname: resp.surname,
      email: resp.email,
      photoUploadPeriodDays: resp.photoUploadPeriodDays,
    };
    await AsyncStorage.setItem(USER_KEY, JSON.stringify(user));
    setPatient(user);
  };

  const login = async (email: string, password: string) => {
    const resp = await authLogin(email, password);
    await persist(resp);
  };

  const register = async (payload: Parameters<typeof authRegister>[0]) => {
    const resp = await authRegister(payload);
    await persist(resp);
  };

  const logout = async () => {
    await AsyncStorage.multiRemove([TOKEN_KEY, USER_KEY]);
    setPatient(null);
  };

  return (
    <AuthContext.Provider value={{ patient, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};
