import axios from 'axios';
import {
  MOCK_PATIENTS,
  MOCK_PHOTOS,
  MOCK_MEDICATIONS,
  MOCK_SIDE_EFFECTS,
  MOCK_EMERGENCY_ALERTS,
  MOCK_NOTES,
  MOCK_NOTIFICATIONS,
  MOCK_DASHBOARD_STATS,
} from '../data/mockData';

const delay = (ms = 400) => new Promise((r) => setTimeout(r, ms));

// ─── Auth ────────────────────────────────────────────────────────────────────
export const apiLogin = async (email, password) => {
  await delay();
  return { token: 'mock_jwt_token' };
};

// ─── Dashboard ───────────────────────────────────────────────────────────────
export const apiGetDashboard = async () => {
  await delay();
  return MOCK_DASHBOARD_STATS;
};

// ─── Patients ────────────────────────────────────────────────────────────────
export const apiGetPatients = async () => {
  await delay();
  return [...MOCK_PATIENTS];
};

export const apiGetPatient = async (id) => {
  await delay();
  const p = MOCK_PATIENTS.find((p) => p.id === id);
  if (!p) throw new Error('Hasta bulunamadı');
  return p;
};

// ─── Photos ──────────────────────────────────────────────────────────────────
export const apiGetPhotos = async (patientId) => {
  await delay();
  return MOCK_PHOTOS[patientId] || [];
};

// ─── Medications ─────────────────────────────────────────────────────────────
export const apiGetMedications = async (patientId) => {
  await delay();
  return MOCK_MEDICATIONS[patientId] || [];
};

export const apiAddMedication = async (patientId, data) => {
  await delay(600);
  const newMed = {
    id: 'med-' + Date.now(),
    patient_id: patientId,
    ...data,
    created_at: new Date().toISOString(),
  };
  if (!MOCK_MEDICATIONS[patientId]) MOCK_MEDICATIONS[patientId] = [];
  MOCK_MEDICATIONS[patientId].unshift(newMed);
  return newMed;
};

export const apiDeleteMedication = async (patientId, medicationId) => {
  await delay(400);
  if (MOCK_MEDICATIONS[patientId]) {
    MOCK_MEDICATIONS[patientId] = MOCK_MEDICATIONS[patientId].filter(
      (m) => m.id !== medicationId
    );
  }
  return { success: true };
};

// ─── Side Effects ────────────────────────────────────────────────────────────
export const apiGetSideEffects = async (patientId) => {
  await delay();
  return MOCK_SIDE_EFFECTS[patientId] || [];
};

// ─── Emergency Alerts ────────────────────────────────────────────────────────
export const apiGetEmergencyAlerts = async (patientId) => {
  await delay();
  return MOCK_EMERGENCY_ALERTS[patientId] || [];
};

export const apiResolveAlert = async (alertId, patientId) => {
  await delay(400);
  const alerts = MOCK_EMERGENCY_ALERTS[patientId];
  if (alerts) {
    const a = alerts.find((a) => a.id === alertId);
    if (a) a.resolved = true;
  }
  return { success: true };
};

// ─── Notes ───────────────────────────────────────────────────────────────────
export const apiGetNotes = async (patientId) => {
  await delay();
  return MOCK_NOTES[patientId] || [];
};

export const apiAddNote = async (patientId, noteText) => {
  await delay(600);
  const newNote = {
    id: 'note-' + Date.now(),
    patient_id: patientId,
    doctor_id: 'doc-001',
    note_text: noteText,
    created_at: new Date().toISOString(),
  };
  if (!MOCK_NOTES[patientId]) MOCK_NOTES[patientId] = [];
  MOCK_NOTES[patientId].unshift(newNote);
  return newNote;
};

// ─── Notifications ───────────────────────────────────────────────────────────
export const apiGetNotifications = async () => {
  await delay();
  return [...MOCK_NOTIFICATIONS].sort((a, b) => {
    if (a.type === 'emergency' && b.type !== 'emergency') return -1;
    if (b.type === 'emergency' && a.type !== 'emergency') return 1;
    return new Date(b.sent_at) - new Date(a.sent_at);
  });
};

export const apiMarkNotificationRead = async (id) => {
  await delay(300);
  const n = MOCK_NOTIFICATIONS.find((n) => n.id === id);
  if (n) n.read = true;
  return { success: true };
};

export const apiMarkAllRead = async () => {
  await delay(400);
  MOCK_NOTIFICATIONS.forEach((n) => (n.read = true));
  return { success: true };
};

// ─── AI Labels ───────────────────────────────────────────────────────────────
export const apiAddAiLabel = async (photoId, label, parametricValues) => {
  await delay(700);
  return {
    id: 'label-' + Date.now(),
    photo_id: photoId,
    label,
    parametric_values: parametricValues,
    labeled_at: new Date().toISOString(),
  };
};
