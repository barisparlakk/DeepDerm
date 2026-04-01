export function formatDistanceToNow(dateStr) {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diff = Math.floor((now - date) / 1000);

  if (diff < 60) return 'Az önce';
  if (diff < 3600) return `${Math.floor(diff / 60)} dakika önce`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} saat önce`;
  if (diff < 2592000) return `${Math.floor(diff / 86400)} gün önce`;
  if (diff < 31536000) return `${Math.floor(diff / 2592000)} ay önce`;
  return `${Math.floor(diff / 31536000)} yıl önce`;
}

export function formatDate(dateStr) {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleDateString('tr-TR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  });
}

export function formatDateTime(dateStr) {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleString('tr-TR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function groupByDate(items, dateKey) {
  const groups = {};
  for (const item of items) {
    const d = new Date(item[dateKey]).toLocaleDateString('tr-TR', {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
    });
    if (!groups[d]) groups[d] = [];
    groups[d].push(item);
  }
  return groups;
}
