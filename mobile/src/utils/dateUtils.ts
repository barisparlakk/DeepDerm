export const formatDate = (iso: string): string => {
  const d = new Date(iso);
  return d.toLocaleDateString('tr-TR', { day: '2-digit', month: 'long', year: 'numeric' });
};

export const formatDateTime = (iso: string): string => {
  const d = new Date(iso);
  return d.toLocaleDateString('tr-TR', {
    day: '2-digit', month: 'long', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
};

export const daysUntil = (targetDate: Date): number => {
  const now = new Date();
  const diff = targetDate.getTime() - now.getTime();
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
};

export const nextUploadDate = (lastUploadIso: string | null, periodDays: number): Date | null => {
  if (!lastUploadIso) return null;
  const last = new Date(lastUploadIso);
  const next = new Date(last.getTime() + periodDays * 24 * 60 * 60 * 1000);
  return next;
};
