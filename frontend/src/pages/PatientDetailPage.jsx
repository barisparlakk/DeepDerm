import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import {
  apiGetPatient, apiGetPhotos, apiGetMedications, apiAddMedication,
  apiDeleteMedication, apiGetSideEffects, apiGetEmergencyAlerts,
  apiResolveAlert, apiGetNotes, apiAddNote,
} from '../services/api';
import { formatDate, formatDateTime, formatDistanceToNow, groupByDate } from '../utils/dateUtils';
import {
  ArrowLeft, User, ImageIcon, Pill, AlertTriangle, FileText,
  Plus, X, ZoomIn, ChevronDown, ChevronUp, CheckCircle2,
  Loader2, Camera, StickyNote, Trash2, ArrowLeftRight, Tag
} from 'lucide-react';
import toast from 'react-hot-toast';

const ANGLE_LABELS = { front: 'Ön Görünüm', right: 'Sağ Yanak', left: 'Sol Yanak' };

// ─── Sub-components ──────────────────────────────────────────────────────────

function SectionHeader({ icon: Icon, title, count, open, onToggle, action }) {
  return (
    <div
      className="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-slate-50 transition-colors select-none border-b border-slate-100"
      onClick={onToggle}
    >
      <Icon size={18} className="text-blue-700 flex-shrink-0" />
      <h2 className="font-semibold text-slate-900 flex-1">{title}</h2>
      {count !== undefined && (
        <span className="badge badge-gray">{count}</span>
      )}
      {action && <div onClick={(e) => e.stopPropagation()}>{action}</div>}
      {open ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
    </div>
  );
}

function PhotoViewer({ photos }) {
  const [selected, setSelected] = useState(null);
  const [compareMode, setCompareMode] = useState(false);
  const [compareA, setCompareA] = useState(null);
  const [compareB, setCompareB] = useState(null);

  const grouped = groupByDate(photos, 'uploaded_at');
  const dateKeys = Object.keys(grouped);

  return (
    <div className="p-5">
      {photos.length === 0 ? (
        <div className="flex flex-col items-center py-10 text-slate-400">
          <Camera size={32} className="mb-2 text-slate-300" />
          <p className="text-sm">Henüz fotoğraf yüklenmedi</p>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-slate-500">{photos.length} fotoğraf</p>
            <button
              onClick={() => setCompareMode(!compareMode)}
              className={`btn-secondary text-xs gap-1.5 ${compareMode ? 'bg-blue-50 border-blue-200 text-blue-700' : ''}`}
            >
              <ArrowLeftRight size={13} />
              {compareMode ? 'Karşılaştırmayı Kapat' : 'Karşılaştır'}
            </button>
          </div>

          {compareMode ? (
            <div className="space-y-4">
              <p className="text-xs text-slate-500 bg-blue-50 px-3 py-2 rounded-lg border border-blue-100">
                Karşılaştırmak için iki fotoğraf seçin (önceki ve sonraki)
              </p>
              <div className="grid grid-cols-4 gap-2">
                {photos.map((ph) => {
                  const isA = compareA?.id === ph.id;
                  const isB = compareB?.id === ph.id;
                  return (
                    <div
                      key={ph.id}
                      onClick={() => {
                        if (isA) { setCompareA(null); return; }
                        if (isB) { setCompareB(null); return; }
                        if (!compareA) { setCompareA(ph); return; }
                        if (!compareB) { setCompareB(ph); return; }
                      }}
                      className={`relative aspect-square cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${isA ? 'border-blue-500' : isB ? 'border-emerald-500' : 'border-transparent hover:border-slate-300'
                        }`}
                    >
                      <img src={ph.file_url} alt="" className="w-full h-full object-cover" />
                      {isA && <div className="absolute top-1 left-1 bg-blue-500 text-white text-[10px] px-1.5 py-0.5 rounded font-bold">ÖNCEKİ</div>}
                      {isB && <div className="absolute top-1 left-1 bg-emerald-500 text-white text-[10px] px-1.5 py-0.5 rounded font-bold">SONRAKİ</div>}
                    </div>
                  );
                })}
              </div>
              {compareA && compareB && (
                <div className="grid grid-cols-2 gap-4 mt-4">
                  <div>
                    <p className="text-xs font-medium text-blue-700 mb-2">Önceki — {ANGLE_LABELS[compareA.angle]}</p>
                    <img src={compareA.file_url} alt="Önceki" className="w-full rounded-xl border border-slate-200" />
                    <p className="text-xs text-slate-400 mt-1 text-center">{formatDate(compareA.uploaded_at)}</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-emerald-700 mb-2">Sonraki — {ANGLE_LABELS[compareB.angle]}</p>
                    <img src={compareB.file_url} alt="Sonraki" className="w-full rounded-xl border border-slate-200" />
                    <p className="text-xs text-slate-400 mt-1 text-center">{formatDate(compareB.uploaded_at)}</p>
                  </div>
                </div>
              )}
            </div>
          ) : (
            dateKeys.map((dateKey) => (
              <div key={dateKey} className="mb-6">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                  {dateKey}
                </p>
                <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                  {grouped[dateKey].map((ph) => (
                    <div
                      key={ph.id}
                      onClick={() => setSelected(ph)}
                      className="relative group aspect-square rounded-xl overflow-hidden border border-slate-200 cursor-zoom-in hover:shadow-md transition-all"
                    >
                      <img src={ph.file_url} alt={ANGLE_LABELS[ph.angle]} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                        <ZoomIn size={20} className="text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-2">
                        <p className="text-white text-[10px] font-medium">{ANGLE_LABELS[ph.angle]}</p>
                      </div>
                      {!ph.quality_approved && (
                        <div className="absolute top-1.5 right-1.5 bg-amber-500 text-white text-[9px] px-1.5 py-0.5 rounded font-bold">DÜŞÜK KALİTE</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </>
      )}

      {/* Lightbox */}
      {selected && (
        <div
          className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
          onClick={() => setSelected(null)}
        >
          <div className="max-w-2xl w-full" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-white font-semibold">{ANGLE_LABELS[selected.angle]}</p>
                <p className="text-slate-400 text-sm">{formatDateTime(selected.uploaded_at)}</p>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="w-9 h-9 rounded-full bg-white/10 text-white flex items-center justify-center hover:bg-white/20 transition-colors"
              >
                <X size={18} />
              </button>
            </div>
            <img src={selected.file_url} alt="" className="w-full rounded-xl" />
          </div>
        </div>
      )}
    </div>
  );
}

function MedicationSection({ patientId }) {
  const [meds, setMeds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ drug_name: '', dosage: '', frequency: '', duration: '', instructions: '' });

  useEffect(() => {
    apiGetMedications(patientId).then((d) => { setMeds(d); setLoading(false); });
  }, [patientId]);

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!form.drug_name || !form.dosage || !form.frequency || !form.duration) {
      toast.error('Lütfen zorunlu alanları doldurun.'); return;
    }
    setSaving(true);
    const newMed = await apiAddMedication(patientId, form);
    setMeds((prev) => [newMed, ...prev]);
    setForm({ drug_name: '', dosage: '', frequency: '', duration: '', instructions: '' });
    setAdding(false);
    setSaving(false);
    toast.success('İlaç eklendi.');
  };

  const handleDelete = async (id) => {
    await apiDeleteMedication(patientId, id);
    setMeds((prev) => prev.filter((m) => m.id !== id));
    toast.success('İlaç silindi.');
  };

  if (loading) return <div className="p-5 flex justify-center"><div className="w-6 h-6 border-4 border-blue-100 border-t-blue-600 rounded-full animate-spin" /></div>;

  return (
    <div className="p-5">
      {meds.length === 0 && !adding ? (
        <div className="flex flex-col items-center py-8 text-slate-400">
          <Pill size={28} className="mb-2 text-slate-300" />
          <p className="text-sm">Henüz ilaç eklenmedi</p>
        </div>
      ) : (
        <div className="space-y-3 mb-4">
          {meds.map((m) => (
            <div key={m.id} className="bg-slate-50 rounded-xl p-4 border border-slate-200 flex items-start gap-3">
              <div className="w-9 h-9 rounded-lg bg-blue-100 flex items-center justify-center flex-shrink-0">
                <Pill size={16} className="text-blue-700" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-slate-900">{m.drug_name}</p>
                <div className="flex flex-wrap gap-2 mt-1">
                  <span className="badge badge-blue">{m.dosage}</span>
                  <span className="badge badge-gray">{m.frequency}</span>
                  <span className="badge badge-gray">{m.duration}</span>
                </div>
                {m.instructions && (
                  <p className="text-xs text-slate-500 mt-2 italic">"{m.instructions}"</p>
                )}
                <p className="text-xs text-slate-400 mt-1">{formatDate(m.created_at)}</p>
              </div>
              <button
                onClick={() => handleDelete(m.id)}
                className="text-slate-300 hover:text-red-500 transition-colors p-1"
                title="İlacı Sil"
              >
                <Trash2 size={15} />
              </button>
            </div>
          ))}
        </div>
      )}

      {adding ? (
        <form onSubmit={handleAdd} className="bg-blue-50 rounded-xl p-4 border border-blue-100 space-y-3">
          <p className="font-semibold text-slate-800 text-sm mb-2">Yeni İlaç Ekle</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">İlaç Adı *</label>
              <input className="input" placeholder="ör. Isotretinoin" value={form.drug_name} onChange={(e) => setForm({ ...form, drug_name: e.target.value })} />
            </div>
            <div>
              <label className="label">Doz *</label>
              <input className="input" placeholder="ör. 20mg" value={form.dosage} onChange={(e) => setForm({ ...form, dosage: e.target.value })} />
            </div>
            <div>
              <label className="label">Kullanım Sıklığı *</label>
              <input className="input" placeholder="ör. Günde 1 kez" value={form.frequency} onChange={(e) => setForm({ ...form, frequency: e.target.value })} />
            </div>
            <div>
              <label className="label">Süre *</label>
              <input className="input" placeholder="ör. 3 ay" value={form.duration} onChange={(e) => setForm({ ...form, duration: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="label">Talimatlar</label>
            <textarea className="input resize-none" rows={2} placeholder="Yemeklerle birlikte alınız..." value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })} />
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={saving} className="btn-primary">
              {saving ? <Loader2 size={14} className="animate-spin" /> : null} Kaydet
            </button>
            <button type="button" onClick={() => setAdding(false)} className="btn-secondary">İptal</button>
          </div>
        </form>
      ) : (
        <button onClick={() => setAdding(true)} className="btn-secondary w-full justify-center gap-2 text-blue-700 border-blue-200 hover:bg-blue-50">
          <Plus size={15} /> İlaç Ekle
        </button>
      )}
    </div>
  );
}

function NotesSection({ patientId }) {
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiGetNotes(patientId).then((d) => { setNotes(d); setLoading(false); });
  }, [patientId]);

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!text.trim()) { toast.error('Not metni boş olamaz.'); return; }
    setSaving(true);
    const newNote = await apiAddNote(patientId, text.trim());
    setNotes((prev) => [newNote, ...prev]);
    setText('');
    setSaving(false);
    toast.success('Not kaydedildi.');
  };

  if (loading) return <div className="p-5 flex justify-center"><div className="w-6 h-6 border-4 border-blue-100 border-t-blue-600 rounded-full animate-spin" /></div>;

  return (
    <div className="p-5 space-y-4">
      <form onSubmit={handleAdd} className="space-y-2">
        <label className="label">Yeni Not Ekle</label>
        <textarea
          className="input resize-none"
          rows={3}
          placeholder="Hasta değerlendirmesi, tedavi gözlemi yazın..."
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <button type="submit" disabled={saving} className="btn-primary">
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
          Notu Kaydet
        </button>
      </form>

      {notes.length === 0 ? (
        <div className="flex flex-col items-center py-6 text-slate-400">
          <StickyNote size={28} className="mb-2 text-slate-300" />
          <p className="text-sm">Henüz not eklenmedi</p>
        </div>
      ) : (
        <div className="space-y-3">
          {notes.map((n) => (
            <div key={n.id} className="bg-amber-50 p-4 rounded-xl border border-amber-100">
              <p className="text-sm text-slate-800 leading-relaxed">{n.note_text}</p>
              <p className="text-xs text-slate-400 mt-2">{formatDateTime(n.created_at)}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SideEffectsSection({ patientId }) {
  const [effects, setEffects] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGetSideEffects(patientId).then((d) => { setEffects(d); setLoading(false); });
  }, [patientId]);

  const severityBadge = (s) => {
    const map = { Hafif: 'badge-green', Orta: 'badge-yellow', Şiddetli: 'badge-red' };
    return map[s] || 'badge-gray';
  };

  if (loading) return <div className="p-5 flex justify-center"><div className="w-6 h-6 border-4 border-blue-100 border-t-blue-600 rounded-full animate-spin" /></div>;

  return (
    <div className="p-5">
      {effects.length === 0 ? (
        <div className="flex flex-col items-center py-8 text-slate-400">
          <CheckCircle2 size={28} className="mb-2 text-emerald-400" />
          <p className="text-sm">Yan etki bildirimi yok</p>
        </div>
      ) : (
        <div className="space-y-3">
          {effects.map((e) => (
            <div key={e.id} className="bg-slate-50 rounded-xl p-4 border border-slate-200">
              <div className="flex items-start justify-between gap-2 mb-2">
                <p className="font-medium text-slate-900 text-sm">{e.drug_name}</p>
                <span className={severityBadge(e.severity)}>{e.severity}</span>
              </div>
              <p className="text-sm text-slate-700">{e.description}</p>
              <p className="text-xs text-slate-400 mt-2">{formatDateTime(e.reported_at)}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function EmergencySection({ patientId }) {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGetEmergencyAlerts(patientId).then((d) => { setAlerts(d); setLoading(false); });
  }, [patientId]);

  const resolve = async (id) => {
    await apiResolveAlert(id, patientId);
    setAlerts((prev) => prev.map((a) => a.id === id ? { ...a, resolved: true } : a));
    toast.success('Uyarı çözüldü olarak işaretlendi.');
  };

  if (loading) return <div className="p-5 flex justify-center"><div className="w-6 h-6 border-4 border-blue-100 border-t-blue-600 rounded-full animate-spin" /></div>;

  return (
    <div className="p-5">
      {alerts.length === 0 ? (
        <div className="flex flex-col items-center py-8 text-slate-400">
          <CheckCircle2 size={28} className="mb-2 text-emerald-400" />
          <p className="text-sm">Acil uyarı yok</p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((a) => (
            <div key={a.id} className={`rounded-xl p-4 border ${a.resolved ? 'bg-slate-50 border-slate-200' : 'bg-red-50 border-red-200'}`}>
              <div className="flex items-start gap-3">
                <AlertTriangle size={18} className={a.resolved ? 'text-slate-400' : 'text-red-500'} />
                <div className="flex-1">
                  <p className={`text-sm font-medium ${a.resolved ? 'text-slate-600' : 'text-red-800'}`}>
                    {a.message}
                  </p>
                  <p className="text-xs text-slate-400 mt-1">{formatDateTime(a.sent_at)}</p>
                </div>
                {a.resolved ? (
                  <span className="badge badge-green">Çözüldü</span>
                ) : (
                  <button onClick={() => resolve(a.id)} className="btn-success text-xs flex-shrink-0">
                    <CheckCircle2 size={13} /> Çözüldü
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function PatientDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [patient, setPatient] = useState(null);
  const [photos, setPhotos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openSections, setOpenSections] = useState({
    photos: true, meds: true, notes: true, sideEffects: true, alerts: true,
  });

  useEffect(() => {
    Promise.all([apiGetPatient(id), apiGetPhotos(id)]).then(([p, ph]) => {
      setPatient(p);
      setPhotos(ph);
      setLoading(false);
    }).catch(() => {
      toast.error('Hasta bulunamadı.');
      navigate('/patients');
    });
  }, [id]);

  const toggle = (key) => setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));

  if (loading) {
    return (
      <Layout>
        <div className="flex justify-center items-center h-64">
          <div className="w-10 h-10 border-4 border-blue-200 border-t-blue-700 rounded-full animate-spin" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={() => navigate('/patients')}
          className="flex items-center gap-1.5 text-slate-500 hover:text-slate-900 transition-colors text-sm mb-4"
        >
          <ArrowLeft size={15} /> Hasta Listesine Dön
        </button>
        <div className="flex items-start gap-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-2xl font-bold shadow-md flex-shrink-0">
            {patient.name[0]}{patient.surname[0]}
          </div>
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-slate-900">{patient.name} {patient.surname}</h1>
            <div className="flex flex-wrap items-center gap-3 mt-1">
              <span className="text-slate-500 text-sm">{patient.age} yaş • {patient.gender}</span>
              <span className={`badge ${patient.status === 'Aktif Tedavi' ? 'badge-blue' : patient.status === 'İzleme' ? 'badge-green' : 'badge-yellow'}`}>
                {patient.status}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Info Card */}
      <div className="card p-5 mb-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Telefon', value: patient.phone || '-' },
            { label: 'E-posta', value: patient.email || '-' },
            { label: 'Kayıt Tarihi', value: formatDate(patient.created_at) },
            { label: 'Son Güncelleme', value: formatDistanceToNow(patient.updated_at) },
          ].map(({ label, value }) => (
            <div key={label}>
              <p className="text-xs text-slate-400 font-medium uppercase tracking-wide">{label}</p>
              <p className="text-sm font-medium text-slate-800 mt-0.5 truncate">{value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Sections */}
      <div className="space-y-4">
        {/* Photos */}
        <div className="card overflow-hidden">
          <SectionHeader
            icon={ImageIcon}
            title="Fotoğraflar"
            count={photos.length}
            open={openSections.photos}
            onToggle={() => toggle('photos')}
          />
          {openSections.photos && <PhotoViewer photos={photos} />}
        </div>

        {/* Medications */}
        <div className="card overflow-hidden">
          <SectionHeader
            icon={Pill}
            title="İlaç Tedavisi"
            open={openSections.meds}
            onToggle={() => toggle('meds')}
          />
          {openSections.meds && <MedicationSection patientId={id} />}
        </div>

        {/* Notes */}
        <div className="card overflow-hidden">
          <SectionHeader
            icon={FileText}
            title="Doktor Notları"
            open={openSections.notes}
            onToggle={() => toggle('notes')}
          />
          {openSections.notes && <NotesSection patientId={id} />}
        </div>

        {/* Side Effects */}
        <div className="card overflow-hidden">
          <SectionHeader
            icon={StickyNote}
            title="Yan Etki Bildirimleri"
            open={openSections.sideEffects}
            onToggle={() => toggle('sideEffects')}
          />
          {openSections.sideEffects && <SideEffectsSection patientId={id} />}
        </div>

        {/* Emergency Alerts */}
        <div className="card overflow-hidden">
          <SectionHeader
            icon={AlertTriangle}
            title="Acil Uyarılar"
            open={openSections.alerts}
            onToggle={() => toggle('alerts')}
          />
          {openSections.alerts && <EmergencySection patientId={id} />}
        </div>
      </div>
    </Layout>
  );
}
