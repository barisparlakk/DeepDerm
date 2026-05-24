import { useRef, useState, useEffect, useCallback } from 'react';
import { Pencil, Square, Circle, Type, Trash2, Save, RotateCcw, Palette } from 'lucide-react';
import axios from 'axios';

const TOOLS = [
  { id: 'rect',     icon: Square,    label: 'Dikdörtgen' },
  { id: 'circle',   icon: Circle,    label: 'Daire' },
  { id: 'freehand', icon: Pencil,    label: 'Serbest Çizim' },
  { id: 'text',     icon: Type,      label: 'Metin' },
];

const COLORS = ['#ef4444','#f97316','#eab308','#22c55e','#3b82f6','#a855f7','#ffffff'];

export default function PhotoAnnotator({ photo, imageUrl, onClose }) {
  const canvasRef = useRef(null);
  const imgRef    = useRef(null);
  const [tool, setTool]         = useState('rect');
  const [color, setColor]       = useState('#ef4444');
  const [shapes, setShapes]     = useState([]);
  const [drawing, setDrawing]   = useState(false);
  const [current, setCurrent]   = useState(null);
  const [saving, setSaving]     = useState(false);
  const [saved, setSaved]       = useState(false);
  const [imgLoaded, setImgLoaded] = useState(false);
  const [textInput, setTextInput] = useState('');
  const [pendingText, setPendingText] = useState(null); // {x,y}

  // Load existing annotations
  useEffect(() => {
    axios.get(`/api/photos/${photo.id}/annotations`)
      .then(r => {
        try {
          const data = typeof r.data.data === 'string'
            ? JSON.parse(r.data.data)
            : r.data.data;
          if (Array.isArray(data)) setShapes(data);
        } catch {}
      }).catch(() => {});
  }, [photo.id]);

  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    const img    = imgRef.current;
    if (!canvas || !img || !imgLoaded) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    const allShapes = current ? [...shapes, current] : shapes;
    allShapes.forEach(s => drawShape(ctx, s));
  }, [shapes, current, imgLoaded]);

  useEffect(() => { redraw(); }, [redraw]);

  function drawShape(ctx, s) {
    ctx.strokeStyle = s.color;
    ctx.fillStyle   = s.color;
    ctx.lineWidth   = 2.5;
    ctx.font        = 'bold 14px sans-serif';

    if (s.type === 'rect') {
      ctx.strokeRect(s.x, s.y, s.w, s.h);
    } else if (s.type === 'circle') {
      ctx.beginPath();
      ctx.ellipse(s.x + s.w / 2, s.y + s.h / 2, Math.abs(s.w / 2), Math.abs(s.h / 2), 0, 0, 2 * Math.PI);
      ctx.stroke();
    } else if (s.type === 'freehand' && s.points?.length > 1) {
      ctx.beginPath();
      ctx.moveTo(s.points[0].x, s.points[0].y);
      s.points.slice(1).forEach(p => ctx.lineTo(p.x, p.y));
      ctx.stroke();
    } else if (s.type === 'text') {
      ctx.fillText(s.text, s.x, s.y);
    }
  }

  function getPos(e) {
    const rect = canvasRef.current.getBoundingClientRect();
    const scaleX = canvasRef.current.width  / rect.width;
    const scaleY = canvasRef.current.height / rect.height;
    const src = e.touches ? e.touches[0] : e;
    return {
      x: (src.clientX - rect.left) * scaleX,
      y: (src.clientY - rect.top)  * scaleY,
    };
  }

  function onMouseDown(e) {
    if (tool === 'text') {
      const pos = getPos(e);
      setPendingText(pos);
      return;
    }
    const pos = getPos(e);
    setDrawing(true);
    if (tool === 'freehand') {
      setCurrent({ type: 'freehand', color, points: [pos] });
    } else {
      setCurrent({ type: tool, color, x: pos.x, y: pos.y, w: 0, h: 0 });
    }
  }

  function onMouseMove(e) {
    if (!drawing || !current) return;
    const pos = getPos(e);
    if (tool === 'freehand') {
      setCurrent(c => ({ ...c, points: [...c.points, pos] }));
    } else {
      setCurrent(c => ({ ...c, w: pos.x - c.x, h: pos.y - c.y }));
    }
  }

  function onMouseUp() {
    if (!drawing || !current) return;
    setShapes(s => [...s, current]);
    setCurrent(null);
    setDrawing(false);
  }

  function addText() {
    if (!textInput.trim() || !pendingText) return;
    setShapes(s => [...s, { type: 'text', color, x: pendingText.x, y: pendingText.y + 14, text: textInput }]);
    setTextInput('');
    setPendingText(null);
  }

  function undo() {
    setShapes(s => s.slice(0, -1));
  }

  function clear() {
    setShapes([]);
  }

  async function save() {
    setSaving(true);
    try {
      await axios.post(`/api/photos/${photo.id}/annotations`, { data: JSON.stringify(shapes) });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      console.error('Save failed', err);
    }
    setSaving(false);
  }

  return (
    <div className="fixed inset-0 bg-black/85 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl flex flex-col overflow-hidden" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
          <p className="font-semibold text-slate-800 text-sm">Medikal Annotasyon</p>
          <div className="flex items-center gap-2">
            <button onClick={undo} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500" title="Geri Al"><RotateCcw size={15}/></button>
            <button onClick={clear} className="p-1.5 rounded-lg hover:bg-red-50 text-red-400" title="Temizle"><Trash2 size={15}/></button>
            <button
              onClick={save}
              disabled={saving}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${saved ? 'bg-emerald-100 text-emerald-700' : 'bg-blue-600 hover:bg-blue-700 text-white'}`}
            >
              <Save size={14}/>
              {saving ? 'Kaydediliyor…' : saved ? 'Kaydedildi!' : 'Kaydet'}
            </button>
            <button onClick={onClose} className="ml-1 w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200 text-xs font-bold">✕</button>
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-2 px-5 py-2 border-b border-slate-100 bg-slate-50 flex-wrap">
          <div className="flex gap-1">
            {TOOLS.map(t => (
              <button
                key={t.id}
                onClick={() => setTool(t.id)}
                title={t.label}
                className={`p-2 rounded-lg transition-colors ${tool === t.id ? 'bg-blue-600 text-white' : 'hover:bg-slate-200 text-slate-600'}`}
              >
                <t.icon size={16}/>
              </button>
            ))}
          </div>
          <div className="w-px h-6 bg-slate-200 mx-1"/>
          <div className="flex items-center gap-1">
            <Palette size={14} className="text-slate-400"/>
            {COLORS.map(c => (
              <button
                key={c}
                onClick={() => setColor(c)}
                style={{ backgroundColor: c }}
                className={`w-5 h-5 rounded-full border-2 transition-transform hover:scale-110 ${color === c ? 'border-slate-700 scale-125' : 'border-slate-300'}`}
              />
            ))}
          </div>
        </div>

        {/* Canvas */}
        <div className="relative flex-1 bg-slate-900 flex items-center justify-center p-4" style={{ minHeight: 380 }}>
          <div className="relative">
            <img
              ref={imgRef}
              src={imageUrl}
              alt=""
              crossOrigin="anonymous"
              style={{ display: 'none' }}
              onLoad={() => {
                const img = imgRef.current;
                const canvas = canvasRef.current;
                if (canvas && img) {
                  canvas.width  = img.naturalWidth  || 640;
                  canvas.height = img.naturalHeight || 640;
                }
                setImgLoaded(true);
              }}
            />
            <canvas
              ref={canvasRef}
              style={{ maxHeight: 440, maxWidth: '100%', cursor: tool === 'text' ? 'text' : 'crosshair' }}
              className="rounded-lg"
              onMouseDown={onMouseDown}
              onMouseMove={onMouseMove}
              onMouseUp={onMouseUp}
              onMouseLeave={onMouseUp}
            />
          </div>
        </div>

        {/* Text input (when text tool clicked on canvas) */}
        {pendingText && (
          <div className="flex items-center gap-2 px-5 py-2 border-t border-slate-100 bg-slate-50">
            <input
              autoFocus
              value={textInput}
              onChange={e => setTextInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addText()}
              placeholder="Metin yazın, Enter ile ekleyin…"
              className="flex-1 text-sm border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
            <button onClick={addText} className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">Ekle</button>
            <button onClick={() => setPendingText(null)} className="px-3 py-1.5 bg-slate-200 text-slate-600 rounded-lg text-sm hover:bg-slate-300">İptal</button>
          </div>
        )}
      </div>
    </div>
  );
}
