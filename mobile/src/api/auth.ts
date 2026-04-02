import client from './client';

export interface LoginResponse {
  token: string;
  patientId: string;
  name: string;
  surname: string;
  email: string;
  photoUploadPeriodDays: number;
}

export const authLogin = async (email: string, password: string): Promise<LoginResponse> => {
  const { data } = await client.post('/auth/patient/login', { email, password });
  return data;
};

export const authRegister = async (payload: {
  name: string;
  surname: string;
  age: number;
  gender: string;
  email: string;
  password: string;
  kvkkConsent: boolean;
}): Promise<LoginResponse> => {
  const { data } = await client.post('/auth/patient/register', payload);
  return data;
};
