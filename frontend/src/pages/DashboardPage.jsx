import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../hooks/useNotifications';
import {
  Users, Clock, ImageIcon, AlertTriangle, ChevronRight,
  TrendingUp, Activity, Bell, CheckCircle2
} from 'lucide-react';
import { apiGetDashboard, apiGetPatients, apiGetSeverityDistribution, apiGetRecentPhotos } from '../services/api';
import { formatDistanceToNow } from '../utils/dateUtils';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const SEVERITY_COLORS = {
  clear:      '#22c55e',
  mild:       '#eab308',
  moderate:   '#f97316',
  severe:     '#ef4444',
  very_severe:'#7c3aed',
};

const ANGLE_TR = { front: 'Ön', right: 'Sağ', left: 'Sol' };

export default function DashboardPage() {
  const { doctor } = useAuth();
  const navigate = useNavigate();
  const { notifications, markRead } = useNotifications();
  const [stats, setStats] = useState(null);
  const [patients, setPatients] = useState([]);
  const [loadingStats, setLoadingStats] = useState(true);
  const [severityData, setSeverityData] = useState([]);
  const [recentPhotos, setRecentPhotos] = useState([]);

  useEffect(() => {
    apiGetDashboard().then((s) => { setStats(s); setLoadingStats(false); });
    apiGetPatients().then(setPatients);
    apiGetSeverityDistribution().then(setSeverityData).catch(() => {});
    apiGetRecentPhotos().then(setRecentPhotos).catch(() => {});
  }, []);

  const unreadNotifs = notifications.filter((n) => !n.read).slice(0, 5);
  const emergencyAlerts = notifications.filter((n) => n.type === 'emergency' && !n.read);
  const recentPatients = patients.slice(0, 5);

  const statCards = stats
    ? [
        {
          label: 'Toplam Hasta',
          value: stats.totalPatients,
          icon: Users,
          color: 'bg-blue-100 text-blue-700',
          trend: '+2 bu ay',
          trendUp: true,
        },
        {
          label: 'İnceleme Bekleyen',
          value: stats.pendingReviews,
          icon: Clock,
          color: 'bg-amber-100 text-amber-700',
          trend: 'Güncelleme gerekiyor',
          trendUp: null,
        },
        {
          label: 'Yeni Fotoğraf',
          value: stats.newPhotos,
          icon: ImageIcon,
          color: 'bg-emerald-100 text-emerald-700',
          trend: 'Son 7 günde',
          trendUp: true,
        },
        {
          label: 'Acil Uyarı',
          value: stats.emergencyAlerts,
          icon: AlertTriangle,
          color: stats.emergencyAlerts > 0 ? 'bg-red-100 text-red-700' : 'bg-slate-100 text-slate-500',
          trend: stats.emergencyAlerts > 0 ? 'Hemen incele!' : 'Uyarı yok',
          trendUp: stats.emergencyAlerts === 0,
        },
      ]
    : [];

  return (
    <Layout>
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">
            Hoş geldiniz, {doctor?.name?.split(' ').slice(0, 2).join(' ')} 👋
          </h1>
          <p className="page-subtitle">
            {new Date().toLocaleDateString('tr-TR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
          </p>
        </div>
        <button
          onClick={() => navigate('/patients')}
          className="btn-primary"
          id="view-patients-btn"
        >
          <Users size={16} />
          Hastaları Görüntüle
        </button>
      </div>

      {/* Emergency Banner */}
      {emergencyAlerts.length > 0 && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3 animate-pulse-once">
          <AlertTriangle size={20} className="text-red-600 mt-0.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-red-800">
              {emergencyAlerts.length} Acil Uyarı Bekliyor
            </p>
            <p className="text-red-700 text-sm mt-0.5 truncate">
              {emergencyAlerts[0].message}
            </p>
          </div>
          <button
            onClick={() => navigate('/notifications')}
            className="btn-danger text-xs flex-shrink-0"
          >
            İncele <ChevronRight size={14} />
          </button>
        </div>
      )}

      {/* Stat Cards */}
      {loadingStats ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card p-5 animate-pulse">
              <div className="h-12 w-12 rounded-xl bg-slate-100 mb-4" />
              <div className="h-7 w-16 bg-slate-100 rounded mb-2" />
              <div className="h-4 w-24 bg-slate-100 rounded" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {statCards.map(({ label, value, icon: Icon, color, trend, trendUp }) => (
            <div key={label} className="stat-card hover:shadow-md transition-shadow">
              <div className={`stat-icon ${color}`}>
                <Icon size={22} />
              </div>
              <div>
                <p className="text-3xl font-bold text-slate-900">{value}</p>
                <p className="text-slate-500 text-sm mt-0.5">{label}</p>
                <p className={`text-xs mt-1 font-medium ${trendUp === true ? 'text-emerald-600' : trendUp === false ? 'text-red-600' : 'text-slate-400'}`}>
                  {trend}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Recent Photos Strip */}
      {recentPhotos.length > 0 && (
        <div className="card mb-6 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <ImageIcon size={16} className="text-blue-700" />
              <h2 className="font-semibold text-slate-900 text-sm">Son Yüklenen Fotoğraflar</h2>
            </div>
            <span className="text-xs text-slate-400">Hızlı inceleme için tıkla</span>
          </div>
          <div className="flex gap-3 p-4 overflow-x-auto">
            {recentPhotos.map((ph) => (
              <div
                key={ph.id}
                onClick={() => navigate(`/patients/${ph.patientId}`)}
                className="flex-shrink-0 cursor-pointer group"
              >
                <div className="w-20 h-20 rounded-xl overflow-hidden border-2 border-transparent group-hover:border-blue-400 transition-all shadow-sm">
                  <img
                    src={`http://localhost:8080${ph.fileUrl}`}
                    alt=""
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
                    onError={e => { e.target.style.display='none'; e.target.parentNode.classList.add('bg-slate-100'); }}
                  />
                </div>
                <p className="text-[10px] text-slate-600 text-center mt-1 font-medium truncate w-20">
                  {ph.patientName.split(' ')[0]}
                </p>
                <p className="text-[9px] text-slate-400 text-center">{ANGLE_TR[ph.angle] || ph.angle}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Patients */}
        <div className="card">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <Activity size={18} className="text-blue-700" />
              <h2 className="font-semibold text-slate-900">Son Hastalar</h2>
            </div>
            <button
              onClick={() => navigate('/patients')}
              className="text-sm text-blue-700 hover:underline font-medium flex items-center gap-1"
            >
              Tümü <ChevronRight size={14} />
            </button>
          </div>
          <div className="divide-y divide-slate-50">
            {recentPatients.map((p) => (
              <div
                key={p.id}
                onClick={() => navigate(`/patients/${p.id}`)}
                className="flex items-center gap-3 px-5 py-3.5 hover:bg-slate-50 cursor-pointer transition-colors"
              >
                <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center text-white text-sm font-semibold flex-shrink-0">
                  {p.name[0]}{p.surname[0]}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-slate-900 text-sm">{p.name} {p.surname}</p>
                  <p className="text-xs text-slate-500">{p.age} yaş • {p.gender}</p>
                </div>
                <div className="text-right flex-shrink-0">
                  <span className={`badge ${
                    p.status === 'Aktif Tedavi' ? 'badge-blue' :
                    p.status === 'İzleme' ? 'badge-green' : 'badge-yellow'
                  }`}>
                    {p.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Notifications */}
        <div className="card">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <Bell size={18} className="text-blue-700" />
              <h2 className="font-semibold text-slate-900">Son Bildirimler</h2>
            </div>
            <button
              onClick={() => navigate('/notifications')}
              className="text-sm text-blue-700 hover:underline font-medium flex items-center gap-1"
            >
              Tümü <ChevronRight size={14} />
            </button>
          </div>
          <div className="divide-y divide-slate-50">
            {unreadNotifs.length === 0 ? (
              <div className="flex flex-col items-center py-10 text-slate-400">
                <CheckCircle2 size={32} className="mb-2 text-emerald-400" />
                <p className="text-sm">Tüm bildirimler okundu</p>
              </div>
            ) : (
              unreadNotifs.map((n) => (
                <div
                  key={n.id}
                  onClick={async () => { await markRead(n.id); navigate('/notifications'); }}
                  className="notification-item"
                >
                  <div className="flex items-start gap-3">
                    <div className={`w-2.5 h-2.5 rounded-full mt-1.5 flex-shrink-0 ${
                      n.type === 'emergency' ? 'bg-red-500' :
                      n.type === 'photo' ? 'bg-blue-500' : 'bg-amber-500'
                    }`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-900">{n.title}</p>
                      <p className="text-xs text-slate-500 truncate mt-0.5">{n.message}</p>
                      <p className="text-xs text-slate-400 mt-1">{formatDistanceToNow(n.sent_at)}</p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Severity Distribution Donut */}
      {severityData.length > 0 && (
        <div className="card mt-6">
          <div className="flex items-center gap-2 px-5 py-4 border-b border-slate-100">
            <TrendingUp size={18} className="text-violet-600" />
            <h2 className="font-semibold text-slate-900">Lezyon Şiddet Dağılımı</h2>
            <span className="ml-auto text-xs text-slate-400">Tüm AI analizleri</span>
          </div>
          <div className="flex flex-col md:flex-row items-center gap-4 p-5">
            <ResponsiveContainer width={220} height={200}>
              <PieChart>
                <Pie
                  data={severityData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={3}
                  dataKey="count"
                  nameKey="labelTr"
                >
                  {severityData.map((entry, i) => (
                    <Cell
                      key={i}
                      fill={SEVERITY_COLORS[entry.label] || '#94a3b8'}
                    />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v, n) => [v + ' analiz', n]}
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
                />
              </PieChart>
            </ResponsiveContainer>

            <div className="flex flex-col gap-2 flex-1">
              {severityData.map((s) => {
                const total = severityData.reduce((acc, x) => acc + Number(x.count), 0);
                const pct = total > 0 ? Math.round((Number(s.count) / total) * 100) : 0;
                const color = SEVERITY_COLORS[s.label] || '#94a3b8';
                return (
                  <div key={s.label} className="flex items-center gap-3">
                    <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                    <span className="text-sm text-slate-700 flex-1">{s.labelTr}</span>
                    <div className="flex items-center gap-2 w-40">
                      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{ width: `${pct}%`, backgroundColor: color }}
                        />
                      </div>
                      <span className="text-xs font-semibold text-slate-600 w-8 text-right">{pct}%</span>
                    </div>
                    <span className="text-xs text-slate-400 w-10 text-right">{s.count} analiz</span>
                  </div>
                );
              })}
              <p className="text-xs text-slate-400 mt-2 pt-2 border-t border-slate-100">
                Toplam {severityData.reduce((a, x) => a + Number(x.count), 0)} AI analizi
              </p>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
