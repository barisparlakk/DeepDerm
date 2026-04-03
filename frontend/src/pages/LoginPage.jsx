import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Eye, EyeOff, Activity, Lock, Mail, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';

export default function LoginPage() {
  const [email, setEmail] = useState('ayse.kaya@deripoliklinigi.com');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error('Lütfen tüm alanları doldurun.');
      return;
    }
    setLoading(true);
    const result = await login(email, password);
    setLoading(false);
    if (result.success) {
      toast.success('Hoş geldiniz!');
      navigate('/dashboard');
    } else {
      toast.error(result.message || 'Giriş başarısız.');
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left Panel */}
      <div className="hidden lg:flex flex-col justify-between w-[45%] bg-gradient-to-br from-blue-900 via-blue-800 to-indigo-900 p-12 relative overflow-hidden">
        {/* Background decoration */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-20 -left-20 w-80 h-80 bg-blue-400/10 rounded-full blur-3xl" />
          <div className="absolute bottom-10 right-10 w-60 h-60 bg-indigo-400/10 rounded-full blur-3xl" />
          <div className="absolute top-1/2 left-1/4 w-40 h-40 bg-cyan-400/10 rounded-full blur-2xl" />
        </div>

        {/* Logo */}
        <div className="flex items-center gap-3 relative z-10">
          <div className="w-11 h-11 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center shadow-lg">
            <Activity size={22} className="text-white" />
          </div>
          <div>
            <span className="text-2xl font-bold text-white">Deep</span>
            <span className="text-2xl font-bold text-blue-300">Derm</span>
          </div>
        </div>

        {/* Quote */}
        <div className="relative z-10">
          <div className="grid grid-cols-3 gap-4 mb-10">
            {[
              { value: '6+', label: 'Aktif Hasta' },
              { value: '%94', label: 'Memnuniyet' },
              { value: '24/7', label: 'İzleme' },
            ].map(({ value, label }) => (
              <div key={label} className="bg-white/10 backdrop-blur rounded-xl p-4 text-center border border-white/10">
                <p className="text-2xl font-bold text-white">{value}</p>
                <p className="text-blue-200 text-xs mt-1">{label}</p>
              </div>
            ))}
          </div>

          <blockquote className="text-white/90 text-lg leading-relaxed font-light italic">
            "Uzaktan tedavi takibi ile hastalarınızın iyileşme sürecini her adımda yönetin."
          </blockquote>
          <p className="text-blue-300 text-sm mt-4 font-medium">— DeepDerm Dermatoloji Platformu</p>
        </div>
      </div>

      {/* Right Panel */}
      <div className="flex-1 flex items-center justify-center p-6 bg-slate-50">
        <div className="w-full max-w-md">
          {/* Mobile Logo */}
          <div className="flex items-center gap-2 mb-8 lg:hidden">
            <div className="w-9 h-9 rounded-xl bg-blue-700 flex items-center justify-center">
              <Activity size={18} className="text-white" />
            </div>
            <span className="text-xl font-bold text-slate-900">Deep<span className="text-blue-700">Derm</span></span>
          </div>

          <div className="mb-8">
            <h1 className="text-3xl font-bold text-slate-900">Doktor Girişi</h1>
            <p className="text-slate-500 mt-2">Bu panel yalnızca kayıtlı doktorlar içindir.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="label">E-posta Adresi</label>
              <div className="relative">
                <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  id="email-input"
                  type="email"
                  className="input pl-10"
                  placeholder="doktor@hastane.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                />
              </div>
            </div>

            <div>
              <label className="label">Şifre</label>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  id="password-input"
                  type={showPass ? 'text' : 'password'}
                  className="input pl-10 pr-10"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPass(!showPass)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between text-sm">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" className="rounded border-slate-300 text-blue-600" />
                <span className="text-slate-600">Beni hatırla</span>
              </label>
              <button type="button" className="text-blue-700 hover:underline font-medium">
                Şifremi unuttum
              </button>
            </div>

            <button
              id="login-button"
              type="submit"
              disabled={loading}
              className="btn-primary w-full justify-center py-2.5 text-base"
            >
              {loading ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  <span>Giriş yapılıyor...</span>
                </>
              ) : (
                'Giriş Yap'
              )}
            </button>
          </form>

          <div className="mt-6 p-4 bg-blue-50 rounded-xl border border-blue-100">
            <p className="text-xs text-blue-700 font-medium mb-1">Doktor Hesabı</p>
            <p className="text-xs text-blue-600">E-posta: ayse.kaya@deripoliklinigi.com</p>
            <p className="text-xs text-blue-600">Şifre: password123</p>
          </div>

          <p className="text-center text-xs text-slate-400 mt-8">
            KVKK kapsamında verileriniz güvende. © 2024 DeepDerm
          </p>
        </div>
      </div>
    </div>
  );
}
