import { useAuth } from '../context/AuthContext';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Users, Bell, LogOut, Activity,
  ChevronRight, Menu, X, Moon, Sun
} from 'lucide-react';
import { useState, useEffect } from 'react';
import { useNotifications } from '../hooks/useNotifications';

const navItems = [
  { path: '/dashboard', label: 'Panel', icon: LayoutDashboard },
  { path: '/patients', label: 'Hastalar', icon: Users },
  { path: '/notifications', label: 'Bildirimler', icon: Bell },
];

export default function Sidebar() {
  const { doctor, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const { unreadCount } = useNotifications();
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark');

  useEffect(() => {
    if (dark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [dark]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside
      className={`
        flex flex-col bg-white border-r border-slate-200 h-screen sticky top-0
        transition-all duration-300 flex-shrink-0
        ${collapsed ? 'w-16' : 'w-64'}
      `}
    >
      {/* Logo / Header */}
      {collapsed ? (
        <div className="flex flex-col items-center py-4 border-b border-slate-100 gap-2">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-600 to-blue-800 flex items-center justify-center shadow-md">
            <Activity size={18} className="text-white" />
          </div>
          <button
            onClick={() => setCollapsed(false)}
            className="p-1 rounded-lg hover:bg-slate-100 text-slate-500 transition-colors"
            title="Menüyü Aç"
          >
            <Menu size={16} />
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-3 px-4 py-5 border-b border-slate-100">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-600 to-blue-800 flex items-center justify-center flex-shrink-0 shadow-md">
            <Activity size={18} className="text-white" />
          </div>
          <div>
            <span className="text-lg font-bold text-slate-900 dark:text-white">Deep</span>
            <span className="text-lg font-bold text-blue-500">Derm</span>
            <p className="text-[10px] text-slate-400 -mt-0.5 tracking-wide uppercase">Dermatoloji Paneli</p>
          </div>
          <button
            onClick={() => setCollapsed(true)}
            className="ml-auto p-1 rounded-lg hover:bg-slate-100 text-slate-500 transition-colors"
            title="Menüyü Kapat"
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Nav Links */}
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map(({ path, label, icon: Icon }) => {
          const isActive = location.pathname.startsWith(path);
          return (
            <button
              key={path}
              onClick={() => navigate(path)}
              className={`w-full ${isActive ? 'sidebar-link-active' : 'sidebar-link-inactive'} ${collapsed ? 'justify-center px-2' : ''}`}
              title={collapsed ? label : undefined}
            >
              <div className="relative">
                <Icon size={18} />
                {path === '/notifications' && unreadCount > 0 && (
                  <span className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-red-500 text-white rounded-full text-[9px] font-bold flex items-center justify-center">
                    {unreadCount > 9 ? '9+' : unreadCount}
                  </span>
                )}
              </div>
              {!collapsed && <span>{label}</span>}
              {!collapsed && path === '/notifications' && unreadCount > 0 && (
                <span className="ml-auto px-1.5 py-0.5 bg-red-500 text-white rounded-full text-[10px] font-bold">
                  {unreadCount}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Doctor Info / Logout */}
      <div className={`p-3 border-t border-slate-100 ${collapsed ? 'flex flex-col items-center gap-2' : ''}`}>
        {!collapsed && doctor && (
          <div className="flex items-center gap-3 px-2 py-2 mb-2">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
              {doctor.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-slate-900 truncate">{doctor.name}</p>
              <p className="text-xs text-slate-500 truncate">{doctor.specialty}</p>
            </div>
          </div>
        )}
        <button
          onClick={() => setDark(d => !d)}
          className={`w-full sidebar-link-inactive text-slate-600 hover:bg-slate-100 mb-1 ${collapsed ? 'justify-center px-2' : ''}`}
          title={dark ? 'Aydınlık Mod' : 'Karanlık Mod'}
        >
          {dark ? <Sun size={18} /> : <Moon size={18} />}
          {!collapsed && <span>{dark ? 'Aydınlık Mod' : 'Karanlık Mod'}</span>}
        </button>
        <button
          onClick={handleLogout}
          className={`w-full sidebar-link-inactive text-red-600 hover:bg-red-50 hover:text-red-700 ${collapsed ? 'justify-center px-2' : ''}`}
          title="Çıkış Yap"
        >
          <LogOut size={18} />
          {!collapsed && <span>Çıkış Yap</span>}
        </button>
      </div>
    </aside>
  );
}
