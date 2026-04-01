import { useState, useEffect, useCallback } from 'react';
import { apiGetNotifications, apiMarkNotificationRead, apiMarkAllRead } from '../services/api';
import { MOCK_NOTIFICATIONS } from '../data/mockData';

export function useNotifications() {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const data = await apiGetNotifications();
    setNotifications(data);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    // Poll every 30s to pick up mock changes
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, [load]);

  const markRead = async (id) => {
    await apiMarkNotificationRead(id);
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  };

  const markAllRead = async () => {
    await apiMarkAllRead();
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  const unreadCount = notifications.filter((n) => !n.read).length;
  const emergencyCount = notifications.filter((n) => n.type === 'emergency' && !n.read).length;

  return { notifications, loading, markRead, markAllRead, unreadCount, emergencyCount, reload: load };
}
