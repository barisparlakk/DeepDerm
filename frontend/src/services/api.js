import axios from 'axios';

axios.interceptors.request.use(config => {
  const token = localStorage.getItem('deepderm_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ─── Dashboard ───────────────────────────────────────────────────────────────
export const apiGetDashboard = async () => {
  return { totalPatients: 0, pendingReviews: 0, newPhotos: 0, emergencyAlerts: 0 };
};

// ─── Patients ────────────────────────────────────────────────────────────────
export const apiGetPatients = async () => (await axios.get('/api/patients')).data;
export const apiGetPatient = async (id) => (await axios.get(`/api/patients/${id}`)).data;

// ─── Photos ──────────────────────────────────────────────────────────────────
export const apiGetPhotos = async (patientId) => (await axios.get(`/api/patients/${patientId}/photos`)).data;

// ─── Medications ─────────────────────────────────────────────────────────────
export const apiGetMedications = async (patientId) => (await axios.get(`/api/patients/${patientId}/medications`)).data;
export const apiAddMedication = async (patientId, data) => (await axios.post(`/api/patients/${patientId}/medications`, data)).data;
export const apiDeleteMedication = async (patientId, medicationId) => {
   // Optional implementation later
   return { success: true };
};

// ─── Side Effects ────────────────────────────────────────────────────────────
export const apiGetSideEffects = async (patientId) => (await axios.get(`/api/patients/${patientId}/side-effects`)).data;

// ─── Emergency Alerts ────────────────────────────────────────────────────────
export const apiGetEmergencyAlerts = async (patientId) => (await axios.get(`/api/patients/${patientId}/emergency-alerts`)).data;
export const apiResolveAlert = async (alertId, patientId) => { return { success: true }; };

// ─── Notes ───────────────────────────────────────────────────────────────────
export const apiGetNotes = async (patientId) => (await axios.get(`/api/patients/${patientId}/notes`)).data;
export const apiAddNote = async (patientId, noteText) => (await axios.post(`/api/patients/${patientId}/notes`, { noteText })).data;

// ─── Notifications ───────────────────────────────────────────────────────────
export const apiGetNotifications = async () => [];
export const apiMarkNotificationRead = async (id) => { return { success: true }; };
export const apiMarkAllRead = async () => { return { success: true }; };

// ─── AI Labels ───────────────────────────────────────────────────────────────
export const apiAddAiLabel = async (photoId, label, parametricValues) => {
   return { success: true };
};
