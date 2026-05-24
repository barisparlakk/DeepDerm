import { useState } from 'react';
import { FileDown, Loader2 } from 'lucide-react';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

export default function PdfExportButton({ patient, photos, elementId }) {
  const [loading, setLoading] = useState(false);

  async function exportPdf() {
    setLoading(true);
    try {
      const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
      const W = 210, margin = 15;
      let y = margin;

      // ── Header ──
      pdf.setFillColor(79, 70, 229); // indigo
      pdf.rect(0, 0, W, 28, 'F');
      pdf.setTextColor(255, 255, 255);
      pdf.setFontSize(16);
      pdf.setFont('helvetica', 'bold');
      pdf.text('DeepDerm — Hasta Raporu', margin, 12);
      pdf.setFontSize(9);
      pdf.setFont('helvetica', 'normal');
      pdf.text(`Rapor tarihi: ${new Date().toLocaleDateString('tr-TR')}`, margin, 20);
      pdf.setTextColor(0, 0, 0);
      y = 36;

      // ── Patient info ──
      pdf.setFontSize(13);
      pdf.setFont('helvetica', 'bold');
      pdf.text(`${patient.name} ${patient.surname}`, margin, y);
      y += 7;
      pdf.setFontSize(9);
      pdf.setFont('helvetica', 'normal');
      pdf.setTextColor(80, 80, 80);
      const info = [
        `Yaş: ${patient.age}`,
        `Cinsiyet: ${patient.gender === 'male' ? 'Erkek' : patient.gender === 'female' ? 'Kadın' : patient.gender}`,
        `E-posta: ${patient.email || '—'}`,
      ].join('     ');
      pdf.text(info, margin, y);
      y += 10;
      pdf.setTextColor(0, 0, 0);

      // ── Divider ──
      pdf.setDrawColor(200, 200, 220);
      pdf.line(margin, y, W - margin, y);
      y += 6;

      // ── Photos with AI analysis ──
      pdf.setFontSize(11);
      pdf.setFont('helvetica', 'bold');
      pdf.text('Analiz Sonuçları', margin, y);
      y += 6;

      for (const photo of photos) {
        if (y > 250) { pdf.addPage(); y = margin; }

        // Photo image
        try {
          const imgEl = document.createElement('img');
          imgEl.crossOrigin = 'anonymous';
          imgEl.src = `http://localhost:8080${photo.fileUrl}`;
          await new Promise((res, rej) => { imgEl.onload = res; imgEl.onerror = rej; setTimeout(rej, 4000); });
          const canvas = document.createElement('canvas');
          canvas.width = imgEl.naturalWidth; canvas.height = imgEl.naturalHeight;
          canvas.getContext('2d').drawImage(imgEl, 0, 0);
          const imgData = canvas.toDataURL('image/jpeg', 0.7);
          const maxW = 55, maxH = 55;
          const ratio = Math.min(maxW / canvas.width, maxH / canvas.height);
          const iw = canvas.width * ratio, ih = canvas.height * ratio;
          pdf.addImage(imgData, 'JPEG', margin, y, iw, ih);
        } catch {}

        // Text next to photo
        const tx = margin + 60;
        pdf.setFontSize(9);
        pdf.setFont('helvetica', 'bold');
        const angleLabel = { front: 'Ön Görünüm', right: 'Sağ Yanak', left: 'Sol Yanak' }[photo.angle] || photo.angle;
        pdf.text(angleLabel, tx, y + 5);
        pdf.setFont('helvetica', 'normal');
        pdf.setTextColor(80, 80, 80);
        pdf.text(`Tarih: ${new Date(photo.uploadedAt).toLocaleDateString('tr-TR')}`, tx, y + 11);

        // Inline AI result fetch
        try {
          const token = localStorage.getItem('deepderm_token');
          const res = await fetch(`http://localhost:8080/ai/results/${photo.id}`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          if (res.ok) {
            const ai = await res.json();
            const sev = ai.severity?.label_tr || '—';
            const total = ai.total_lesion_count ?? 0;
            const counts = ai.counts || {};
            pdf.text(`Lezyon: ${total} | Şiddet: ${sev}`, tx, y + 17);
            const detail = [
              counts.papule   && `Papül:${counts.papule}`,
              counts.pustule  && `Püstül:${counts.pustule}`,
              counts.comedone && `Komedon:${counts.comedone}`,
              counts.nodule   && `Nodül:${counts.nodule}`,
            ].filter(Boolean).join('  ');
            if (detail) pdf.text(detail, tx, y + 23);

            // Annotated image
            if (ai.annotated_image_url) {
              try {
                const aEl = document.createElement('img');
                aEl.crossOrigin = 'anonymous';
                aEl.src = `http://localhost:8000${ai.annotated_image_url}`;
                await new Promise((res, rej) => { aEl.onload = res; aEl.onerror = rej; setTimeout(rej, 4000); });
                const ac = document.createElement('canvas');
                ac.width = aEl.naturalWidth; ac.height = aEl.naturalHeight;
                ac.getContext('2d').drawImage(aEl, 0, 0);
                const ad = ac.toDataURL('image/jpeg', 0.7);
                const aratio = Math.min(55 / ac.width, 55 / ac.height);
                pdf.addImage(ad, 'JPEG', tx, y + 27, ac.width * aratio, ac.height * aratio);
              } catch {}
            }
          }
        } catch {}

        pdf.setTextColor(0, 0, 0);
        y += 62;
        pdf.setDrawColor(230, 230, 240);
        pdf.line(margin, y - 2, W - margin, y - 2);
      }

      // ── Footer ──
      const pageCount = pdf.internal.getNumberOfPages();
      for (let i = 1; i <= pageCount; i++) {
        pdf.setPage(i);
        pdf.setFontSize(8);
        pdf.setTextColor(160, 160, 160);
        pdf.text(`DeepDerm — Gizli Tıbbi Rapor — Sayfa ${i}/${pageCount}`, margin, 290);
      }

      const filename = `deepderm_${patient.surname}_${patient.name}_${new Date().toISOString().slice(0,10)}.pdf`;
      pdf.save(filename);
    } catch (err) {
      console.error('PDF export failed', err);
      alert('PDF oluşturulurken hata oluştu.');
    }
    setLoading(false);
  }

  return (
    <button
      onClick={exportPdf}
      disabled={loading}
      className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-800 text-white text-sm font-medium rounded-xl transition-colors disabled:opacity-60"
      title="PDF Raporu İndir"
    >
      {loading ? <Loader2 size={15} className="animate-spin" /> : <FileDown size={15} />}
      {loading ? 'Hazırlanıyor…' : 'PDF Rapor'}
    </button>
  );
}
