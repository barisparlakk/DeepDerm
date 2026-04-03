import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { apiGetPatients } from '../services/api';
import { formatDate } from '../utils/dateUtils';
import { Search, Filter, UserPlus, ChevronRight, Users } from 'lucide-react';

const STATUS_OPTIONS = ['Tümü', 'Aktif Tedavi', 'İzleme', 'Takip Bekleniyor'];
const GENDER_OPTIONS = ['Tümü', 'Erkek', 'Kadın'];

export default function PatientListPage() {
  const navigate = useNavigate();
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('Tümü');
  const [genderFilter, setGenderFilter] = useState('Tümü');

  useEffect(() => {
    apiGetPatients().then((data) => {
      setPatients(data);
      setLoading(false);
    });
  }, []);

  const filtered = patients.filter((p) => {
    const search = query.toLowerCase();
    const matchQ =
      !query ||
      `${p.name} ${p.surname}`.toLowerCase().includes(search) ||
      p.email?.toLowerCase().includes(search) ||
      p.phone?.includes(search);
    const matchS = statusFilter === 'Tümü' || p.status === statusFilter;
    const matchG = genderFilter === 'Tümü' || p.gender === genderFilter;
    return matchQ && matchS && matchG;
  });

  const statusBadge = (status) => {
    const map = {
      'Aktif Tedavi': 'badge-blue',
      'İzleme': 'badge-green',
      'Takip Bekleniyor': 'badge-yellow',
    };
    return map[status] || 'badge-gray';
  };

  return (
    <Layout>
      <div className="page-header">
        <div>
          <h1 className="page-title">Hastalar</h1>
          <p className="page-subtitle">Atanmış tüm hastalarınızı görüntüleyin ve yönetin</p>
        </div>
        <button className="btn-primary" id="add-patient-btn" onClick={() => alert('Hastalar doğrudan mobil uygulama üzerinden e-posta adresinizle size kayıt olmaktadır. Hasta ekleme yönergesini hastanıza iletiniz.')}>
          <UserPlus size={16} />
          Hasta Ekle
        </button>
      </div>

      {/* Filters */}
      <div className="card p-4 mb-6">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              id="patient-search"
              type="text"
              className="input pl-10"
              placeholder="İsim, e-posta veya telefon ara..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Filter size={15} className="text-slate-400 flex-shrink-0" />
            <div className="flex gap-1.5 flex-wrap">
              {STATUS_OPTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    statusFilter === s
                      ? 'bg-blue-700 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
            <div className="w-px h-5 bg-slate-200 hidden sm:block" />
            <div className="flex gap-1.5">
              {GENDER_OPTIONS.map((g) => (
                <button
                  key={g}
                  onClick={() => setGenderFilter(g)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    genderFilter === g
                      ? 'bg-blue-700 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {g}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="p-8 flex justify-center">
            <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-700 rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center py-16 text-slate-400">
            <Users size={40} className="mb-3 text-slate-300" />
            <p className="font-medium">Sonuç bulunamadı</p>
            <p className="text-sm mt-1">Arama kriterlerinizi değiştirin</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="table-th">Hasta</th>
                  <th className="table-th">Yaş / Cinsiyet</th>
                  <th className="table-th">Durum</th>
                  <th className="table-th hidden md:table-cell">Son Fotoğraf</th>
                  <th className="table-th hidden lg:table-cell">Başlangıç Tarihi</th>
                  <th className="table-th" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((p) => (
                  <tr
                    key={p.id}
                    onClick={() => navigate(`/patients/${p.id}`)}
                    className="hover:bg-blue-50/50 cursor-pointer transition-colors group"
                  >
                    <td className="table-td">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-sm font-semibold flex-shrink-0">
                          {p.name[0]}{p.surname[0]}
                        </div>
                        <div>
                          <p className="font-semibold text-slate-900">{p.name} {p.surname}</p>
                          <p className="text-xs text-slate-400">{p.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="table-td">
                      <span className="font-medium">{p.age}</span>
                      <span className="text-slate-400"> • </span>
                      <span>{p.gender}</span>
                    </td>
                    <td className="table-td">
                      <span className={statusBadge(p.status)}>{p.status}</span>
                    </td>
                    <td className="table-td hidden md:table-cell text-slate-500">
                      {formatDate(p.updatedAt)}
                    </td>
                    <td className="table-td hidden lg:table-cell text-slate-500">
                      {formatDate(p.createdAt)}
                    </td>
                    <td className="table-td">
                      <ChevronRight
                        size={16}
                        className="text-slate-300 group-hover:text-blue-600 transition-colors"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Footer */}
        {!loading && (
          <div className="px-4 py-3 border-t border-slate-100 bg-slate-50 text-xs text-slate-400">
            {filtered.length} hasta gösteriliyor
            {filtered.length !== patients.length && ` (toplam ${patients.length} içinden)`}
          </div>
        )}
      </div>
    </Layout>
  );
}
