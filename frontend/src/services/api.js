import axios from 'axios';

axios.interceptors.request.use(config => {
  const token = localStorage.getItem('deepderm_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ─── Dashboard ───────────────────────────────────────────────────────────────
export const apiGetDashboard = async () => (await axios.get('/api/dashboard')).data;
export const apiGetSeverityDistribution = async () => (await axios.get('/api/dashboard/severity-distribution')).data;
export const apiGetRecentPhotos = async () => (await axios.get('/api/dashboard/recent-photos')).data;

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
export const apiResolveAlert = async (alertId, patientId) => (await axios.patch(`/api/patients/${patientId}/emergency-alerts/${alertId}/resolve`)).data;

// ─── Notes ───────────────────────────────────────────────────────────────────
export const apiGetNotes = async (patientId) => (await axios.get(`/api/patients/${patientId}/notes`)).data;
export const apiAddNote = async (patientId, noteText) => (await axios.post(`/api/patients/${patientId}/notes`, { noteText })).data;

// ─── Notifications ───────────────────────────────────────────────────────────
export const apiGetNotifications = async () => (await axios.get('/api/notifications')).data;
export const apiMarkNotificationRead = async (id) => (await axios.patch(`/api/notifications/${id}/read`)).data;
export const apiMarkAllRead = async () => (await axios.post('/api/notifications/read-all')).data;

// ─── AI Labels ───────────────────────────────────────────────────────────────
export const apiAddAiLabel = async (photoId, label, parametricValues) => {
   return { success: true };
};

// ─── AI Analysis Results ──────────────────────────────────────────────────────
// Fetches the DermAI detection result for a given photo.
// Returns null (not throws) when no analysis exists yet.
export const apiGetAiResults = async (photoId) => {
  try {
    return (await axios.get(`/api/ai/results/${photoId}`)).data;
  } catch (err) {
    if (err?.response?.status === 404) return null;
    throw err;
  }
};

export const apiGetAiTimeline = async (patientId) => {
  return (await axios.get(`/api/ai/results/patient/${patientId}/timeline`)).data;
};

export const apiCompareAiResults = async (previousPhotoId, currentPhotoId) => {
  return (await axios.get('/api/ai/compare', {
    params: { previousPhotoId, currentPhotoId },
  })).data;
};
