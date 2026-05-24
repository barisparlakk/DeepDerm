import { useEffect, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer
} from 'recharts';
import { apiGetAiTimeline } from '../services/api';
import { TrendingUp } from 'lucide-react';

const SEVERITY_COLOR = { clear: '#22c55e', mild: '#eab308', moderate: '#f97316', severe: '#ef4444', 'very_severe': '#7c3aed' };

function formatDate(iso) {
  const d = new Date(iso);
  return `${d.getDate().toString().padStart(2,'0')}.${(d.getMonth()+1).toString().padStart(2,'0')}`;
}

export default function LesionTrendChart({ patientId }) {
  const [data, setData]     = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGetAiTimeline(patientId)
      .then(resp => {
        const results = resp.results || [];
        const points = results.map(r => ({
          date:      formatDate(r.analyzed_at),
          toplam:    r.total_lesion_count || 0,
          papül:     r.counts?.papule    || 0,
          püstül:    r.counts?.pustule   || 0,
          komedon:   r.counts?.comedone  || 0,
          nodül:     r.counts?.nodule    || 0,
          skor:      parseFloat((r.weighted_score || 0).toFixed(1)),
          severity:  r.severity?.label   || 'clear',
        }));
        setData(points);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [patientId]);

  if (loading) return <div className="h-40 flex items-center justify-center text-slate-400 text-sm">Yükleniyor…</div>;
  if (data.length < 1) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp size={16} className="text-violet-500" />
        <p className="text-sm font-semibold text-slate-700">Lezyon Trend Grafiği</p>
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
            formatter={(v, name) => [v, name]}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line type="monotone" dataKey="toplam"  stroke="#7c3aed" strokeWidth={2} dot={{ r: 3 }} name="Toplam" />
          <Line type="monotone" dataKey="papül"   stroke="#ef4444" strokeWidth={1.5} dot={{ r: 2 }} name="Papül" />
          <Line type="monotone" dataKey="püstül"  stroke="#f97316" strokeWidth={1.5} dot={{ r: 2 }} name="Püstül" />
          <Line type="monotone" dataKey="komedon" stroke="#22c55e" strokeWidth={1.5} dot={{ r: 2 }} name="Komedon" />
          <Line type="monotone" dataKey="nodül"   stroke="#3b82f6" strokeWidth={1.5} dot={{ r: 2 }} name="Nodül" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
