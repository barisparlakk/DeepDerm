import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { useNotifications } from '../hooks/useNotifications';
import { formatDistanceToNow, formatDateTime } from '../utils/dateUtils';
import {
  Bell, AlertTriangle, ImageIcon, FileWarning, CheckCheck,
  ArrowRight, Filter, CheckCircle2, Loader2
} from 'lucide-react';

const TYPE_CONFIG = {
  emergency: {
    icon: AlertTriangle,
    color: 'text-red-600',
    bg: 'bg-red-100',
    label: 'Acil Uyarı',
    badge: 'badge-red',
  },
  photo: {
    icon: ImageIcon,
    color: 'text-blue-600',
    bg: 'bg-blue-100',
    label: 'Yeni Fotoğraf',
    badge: 'badge-blue',
  },
  side_effect: {
    icon: FileWarning,
    color: 'text-amber-600',
    bg: 'bg-amber-100',
    label: 'Yan Etki',
    badge: 'badge-yellow',
  },
};

const FILTER_OPTIONS = [
  { key: 'all', label: 'Tümü' },
  { key: 'emergency', label: 'Acil' },
  { key: 'photo', label: 'Fotoğraf' },
  { key: 'side_effect', label: 'Yan Etki' },
  { key: 'unread', label: 'Okunmamış' },
];

export default function NotificationsPage() {
  const navigate = useNavigate();
  const { notifications, loading, markRead, markAllRead, unreadCount } = useNotifications();
  const [filter, setFilter] = useState('all');
  const [markingAll, setMarkingAll] = useState(false);

  const filtered = notifications.filter((n) => {
    if (filter === 'all') return true;
    if (filter === 'unread') return !n.read;
    return n.type === filter;
  });

  const handleMarkAll = async () => {
    setMarkingAll(true);
    await markAllRead();
    setMarkingAll(false);
  };

  return (
    <Layout>
      <div className="page-header">
        <div>
          <h1 className="page-title">Bildirimler</h1>
          <p className="page-subtitle">
            {unreadCount > 0 ? `${unreadCount} okunmamış bildirim` : 'Tüm bildirimler okundu'}
          </p>
        </div>
        {unreadCount > 0 && (
          <button
            onClick={handleMarkAll}
            disabled={markingAll}
            className="btn-secondary"
            id="mark-all-read-btn"
          >
            {markingAll ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <CheckCheck size={15} />
            )}
            Tümünü Okundu İşaretle
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="card p-3 mb-5">
        <div className="flex items-center gap-2 flex-wrap">
          <Filter size={15} className="text-slate-400" />
          {FILTER_OPTIONS.map(({ key, label }) => {
            const count =
              key === 'all' ? notifications.length :
              key === 'unread' ? notifications.filter((n) => !n.read).length :
              notifications.filter((n) => n.type === key).length;

            return (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 ${
                  filter === key ? 'bg-blue-700 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {label}
                {count > 0 && (
                  <span className={`text-xs px-1.5 py-0.5 rounded-full font-bold ${
                    filter === key ? 'bg-white/20 text-white' : 'bg-white text-slate-600'
                  }`}>
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* List */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="p-12 flex justify-center">
            <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-700 rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center py-20 text-slate-400">
            <CheckCircle2 size={44} className="mb-3 text-emerald-400" />
            <p className="font-medium text-slate-600">Bildirim bulunamadı</p>
            <p className="text-sm mt-1">Bu filtreye uygun bildirim yok</p>
          </div>
        ) : (
          <div>
            {filtered.map((n) => {
              const config = TYPE_CONFIG[n.type] || TYPE_CONFIG.photo;
              const Icon = config.icon;
              return (
                <div
                  key={n.id}
                  className={`notification-item ${!n.read ? 'bg-blue-50/40' : ''}`}
                  onClick={async () => {
                    if (!n.read) await markRead(n.id);
                    if (n.patient_id) navigate(`/patients/${n.patient_id}`);
                  }}
                >
                  <div className="flex items-start gap-4">
                    {/* Icon */}
                    <div className={`w-10 h-10 rounded-xl ${config.bg} flex items-center justify-center flex-shrink-0`}>
                      <Icon size={18} className={config.color} />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-0.5">
                        <span className={`badge ${config.badge}`}>{config.label}</span>
                        <span className="font-semibold text-slate-900 text-sm">{n.patient_name}</span>
                        {!n.read && (
                          <span className="w-2 h-2 rounded-full bg-blue-600 flex-shrink-0" />
                        )}
                      </div>
                      <p className="text-sm text-slate-600 line-clamp-2">{n.message}</p>
                      <p className="text-xs text-slate-400 mt-1.5">
                        {formatDistanceToNow(n.sent_at)} • {formatDateTime(n.sent_at)}
                      </p>
                    </div>

                    {/* Action */}
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {!n.read && (
                        <button
                          onClick={async (e) => { e.stopPropagation(); await markRead(n.id); }}
                          className="btn-secondary text-xs"
                        >
                          Okundu
                        </button>
                      )}
                      <ArrowRight size={15} className="text-slate-300" />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Layout>
  );
}
