import axios from 'axios';
import client from './client';

// Direct client for DermAI — no auth needed, bypasses Spring Boot for speed
const dermaiClient = axios.create({
  baseURL: process.env.EXPO_PUBLIC_DERMAI_URL || 'http://192.168.1.36:8000',
  timeout: 30000,
});


// ─── Profile ─────────────────────────────────────────────────────────────────
export const getProfile = async () => {
  const { data } = await client.get('/patients/me');
  return data;
};

export const changePassword = async (currentPassword: string, newPassword: string) => {
  const { data } = await client.put('/patients/me/password', { currentPassword, newPassword });
  return data;
};

export const deleteAccount = async () => {
  const { data } = await client.delete('/patients/me');
  return data;
};

// ─── Medications ─────────────────────────────────────────────────────────────
export const getMedications = async () => {
  const { data } = await client.get('/patients/me/medications');
  return data;
};

export const confirmMedication = async (medicationId: string) => {
  const { data } = await client.post('/patients/me/medication-confirm', { medicationId });
  return data;
};

// ─── Doctor Notes ─────────────────────────────────────────────────────────────
export const getDoctorNotes = async () => {
  const { data } = await client.get('/patients/me/doctor-notes');
  return data;
};

export const getUnreadNoteCount = async (): Promise<{ unreadCount: number }> => {
  const { data } = await client.get('/patients/me/doctor-notes/unread-count');
  return data;
};

export const markNoteRead = async (noteId: string) => {
  const { data } = await client.post(`/patients/me/doctor-notes/${noteId}/read`);
  return data;
};

// ─── Photos ──────────────────────────────────────────────────────────────────
export const getPhotos = async () => {
  const { data } = await client.get('/patients/me/photos');
  return data;
};

export const uploadPhoto = async (fileUri: string, angle: 'front' | 'right' | 'left') => {
  const formData = new FormData();
  const filename = fileUri.split('/').pop() || 'photo.jpg';
  const type = filename.endsWith('.png') ? 'image/png' : 'image/jpeg';
  // @ts-ignore — RN FormData accepts this shape
  formData.append('file', { uri: fileUri, name: filename, type });
  formData.append('angle', angle);
  const { data } = await client.post('/patients/me/photos', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};

export const checkPhotoAngle = async (fileUri: string, angle: 'front' | 'right' | 'left') => {
  // Call DermAI directly — skips the Spring Boot proxy hop, no auth required.
  // DermAI field name is "target_angle", not "angle".
  const formData = new FormData();
  const filename = fileUri.split('/').pop() || 'photo.jpg';
  const type = filename.endsWith('.png') ? 'image/png' : 'image/jpeg';
  // @ts-ignore — RN FormData accepts this shape
  formData.append('file', { uri: fileUri, name: filename, type });
  formData.append('target_angle', angle);
  const { data } = await dermaiClient.post('/quality/check-angle', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};

// ─── Side Effects ─────────────────────────────────────────────────────────────
export const getSideEffects = async () => {
  const { data } = await client.get('/patients/me/side-effects');
  return data;
};

export const reportSideEffect = async (drugName: string, description: string) => {
  const { data } = await client.post('/patients/me/side-effects', { drugName, description });
  return data;
};

// ─── Emergency Alert ─────────────────────────────────────────────────────────
export const getEmergencyStatus = async (): Promise<{
  canSend: boolean;
  usedThisMonth: number;
  monthlyLimit: number;
}> => {
  const { data } = await client.get('/patients/me/emergency-alert/status');
  return data;
};

export const sendEmergencyAlert = async (message: string) => {
  const { data } = await client.post('/patients/me/emergency-alert', { message });
  return data;
};
