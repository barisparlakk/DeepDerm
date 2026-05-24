-- DeepDerm Demo Seed
-- Çalıştırma: psql -U postgres -d deepderm -f /Users/barisparlak/Desktop/DeepDerm/backend/src/main/resources/db/seed_demo.sql
--
-- Doktor : ayse.kaya@deripoliklinigi.com  /  DeepDerm2024!
-- Hasta 1: ahmet.yilmaz@demo.com          /  Demo1234!
-- Hasta 2: fatma.demir@demo.com           /  Demo1234!

DO $$
DECLARE
    v_doctor_id   UUID;
    v_patient1_id UUID;
    v_patient2_id UUID;
    v_photo1_id   UUID;
    v_photo2_id   UUID;
    v_photo3_id   UUID;
BEGIN

-- ── Doktoru bul ───────────────────────────────────────────────────────────────
SELECT id INTO v_doctor_id
FROM doctor WHERE email = 'ayse.kaya@deripoliklinigi.com' LIMIT 1;

IF v_doctor_id IS NULL THEN
    RAISE EXCEPTION 'Demo doktor bulunamadı. Önce V1 migration çalıştırın.';
END IF;

-- ── Hasta 1 — Ahmet Yılmaz ───────────────────────────────────────────────────
SELECT id INTO v_patient1_id
FROM patient WHERE email = 'ahmet.yilmaz@demo.com' LIMIT 1;

IF v_patient1_id IS NULL THEN
    INSERT INTO patient (name, surname, age, gender, email, password_hash, photo_upload_period_days, doctor_id)
    VALUES ('Ahmet', 'Yılmaz', 24, 'Erkek',
            'ahmet.yilmaz@demo.com',
            '$2a$12$7gkBJvBH7wQkH3tC5Xzs5.vLVs0VGZXhH7kF8mRqJ3p0wX1aL7u3e',
            14, v_doctor_id)
    RETURNING id INTO v_patient1_id;
END IF;

-- ── Hasta 2 — Fatma Demir ────────────────────────────────────────────────────
SELECT id INTO v_patient2_id
FROM patient WHERE email = 'fatma.demir@demo.com' LIMIT 1;

IF v_patient2_id IS NULL THEN
    INSERT INTO patient (name, surname, age, gender, email, password_hash, photo_upload_period_days, doctor_id)
    VALUES ('Fatma', 'Demir', 19, 'Kadın',
            'fatma.demir@demo.com',
            '$2a$12$7gkBJvBH7wQkH3tC5Xzs5.vLVs0VGZXhH7kF8mRqJ3p0wX1aL7u3e',
            7, v_doctor_id)
    RETURNING id INTO v_patient2_id;
END IF;

-- ── İlaçlar — Hasta 1 ────────────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM medication WHERE patient_id = v_patient1_id AND drug_name = 'Doksisiklin') THEN
    INSERT INTO medication (patient_id, drug_name, dosage, frequency, duration, instructions)
    VALUES (v_patient1_id, 'Doksisiklin', '100mg', 'Günde 1 kez', '3 ay',
            'Yemekten sonra bol su ile alınız. Güneşten korunun.');
END IF;

IF NOT EXISTS (SELECT 1 FROM medication WHERE patient_id = v_patient1_id AND drug_name = 'Adapalen Jel %0.1') THEN
    INSERT INTO medication (patient_id, drug_name, dosage, frequency, duration, instructions)
    VALUES (v_patient1_id, 'Adapalen Jel %0.1', 'İnce tabaka', 'Gece 1 kez (temiz cilde)', '3 ay',
            'Sadece sivilce olan bölgelere ince tabaka halinde uygulayın. Tahriş olursa gün aşırı kullanın.');
END IF;

-- ── İlaçlar — Hasta 2 ────────────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM medication WHERE patient_id = v_patient2_id AND drug_name = 'İzotretinoin') THEN
    INSERT INTO medication (patient_id, drug_name, dosage, frequency, duration, instructions)
    VALUES (v_patient2_id, 'İzotretinoin', '20mg', 'Günde 2 kez', '6 ay',
            'Yağlı yemeklerle birlikte alın. Aylık kan tahlili gereklidir.');
END IF;

IF NOT EXISTS (SELECT 1 FROM medication WHERE patient_id = v_patient2_id AND drug_name = 'Benzoil Peroksit Jel %5') THEN
    INSERT INTO medication (patient_id, drug_name, dosage, frequency, duration, instructions)
    VALUES (v_patient2_id, 'Benzoil Peroksit Jel %5', 'Mercimek tanesi', 'Günde 2 kez', '3 ay',
            'Sabah ve akşam temiz cilde uygulayın. Kıyafetlerinizi renklendirebilir.');
END IF;

-- ── Doktor Notları — Hasta 1 ─────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM doctor_note WHERE patient_id = v_patient1_id AND note_text LIKE 'Tedavinin 2. haftasında%') THEN
    INSERT INTO doctor_note (patient_id, doctor_id, note_text)
    VALUES (v_patient1_id, v_doctor_id,
            'Tedavinin 2. haftasında minimal yanma bildirdi. Adapalen kullanımını günaşırıya düşürüyoruz. 4 hafta sonra kontrol fotoğrafı bekliyorum.');
END IF;

IF NOT EXISTS (SELECT 1 FROM doctor_note WHERE patient_id = v_patient1_id AND note_text LIKE '1. ay AI analiz%') THEN
    INSERT INTO doctor_note (patient_id, doctor_id, note_text)
    VALUES (v_patient1_id, v_doctor_id,
            '1. ay AI analiz sonuçlarına göre papül sayısı %40 azalmış. Tedaviye devam. Güneş koruyucu kullanımını hatırlatın.');
END IF;

-- ── Doktor Notları — Hasta 2 ─────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM doctor_note WHERE patient_id = v_patient2_id AND note_text LIKE 'İzotretinoin başlangıç%') THEN
    INSERT INTO doctor_note (patient_id, doctor_id, note_text)
    VALUES (v_patient2_id, v_doctor_id,
            'İzotretinoin başlangıç dozunu 20mg olarak ayarladım. İlk 3 ayda kötüleşme olabilir, hasta bilgilendirildi. Aylık takip fotoğrafı zorunlu.');
END IF;

-- ── Yan Etki Bildirimleri ─────────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM side_effect_report WHERE patient_id = v_patient1_id AND drug_name = 'Adapalen Jel %0.1') THEN
    INSERT INTO side_effect_report (patient_id, drug_name, description)
    VALUES (v_patient1_id, 'Adapalen Jel %0.1',
            'İlk haftada ciltte hafif yanma ve kızarıklık oluştu, özellikle yanaklar bölgesinde.');
END IF;

IF NOT EXISTS (SELECT 1 FROM side_effect_report WHERE patient_id = v_patient2_id AND drug_name = 'İzotretinoin') THEN
    INSERT INTO side_effect_report (patient_id, drug_name, description)
    VALUES (v_patient2_id, 'İzotretinoin',
            'Dudaklarda aşırı kuruluk başladı, günde 3-4 kez nemlendirici sürüyorum. Burun içi de kuruydu ancak biraz geçti.');
END IF;

-- ── Acil Bildirim (çözümlenmiş) — Hasta 2 ────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM emergency_alert WHERE patient_id = v_patient2_id) THEN
    INSERT INTO emergency_alert (patient_id, message, resolved)
    VALUES (v_patient2_id,
            'Dudaklarımda çatlama ve kanama başladı, ayrıca gözlerimde kuruluk ve kızarıklık var. İzotretinoin yan etkisi mi olduğunu bilmiyorum.',
            TRUE);
END IF;

-- ── Fotoğraf kayıtları — Hasta 1 ─────────────────────────────────────────────
-- Her seferinde önce var mı bak, yoksa ekle; ID'yi her zaman SELECT ile al.
SELECT id INTO v_photo1_id FROM photo
WHERE patient_id = v_patient1_id AND angle = 'front' LIMIT 1;
IF v_photo1_id IS NULL THEN
    INSERT INTO photo (patient_id, angle, file_url, quality_approved)
    VALUES (v_patient1_id, 'front', '/uploads/demo/ahmet_front.jpg', true)
    RETURNING id INTO v_photo1_id;
END IF;

SELECT id INTO v_photo2_id FROM photo
WHERE patient_id = v_patient1_id AND angle = 'right' LIMIT 1;
IF v_photo2_id IS NULL THEN
    INSERT INTO photo (patient_id, angle, file_url, quality_approved)
    VALUES (v_patient1_id, 'right', '/uploads/demo/ahmet_right.jpg', true)
    RETURNING id INTO v_photo2_id;
END IF;

SELECT id INTO v_photo3_id FROM photo
WHERE patient_id = v_patient1_id AND angle = 'left' LIMIT 1;
IF v_photo3_id IS NULL THEN
    INSERT INTO photo (patient_id, angle, file_url, quality_approved)
    VALUES (v_patient1_id, 'left', '/uploads/demo/ahmet_left.jpg', true)
    RETURNING id INTO v_photo3_id;
END IF;

-- ── AI Analiz Sonucu — Hasta 1 Ön Fotoğraf ───────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM ai_analiz_sonuclari WHERE photo_id = v_photo1_id) THEN
    INSERT INTO ai_analiz_sonuclari (
        id,
        photo_id, patient_id,
        detections, total_lesion_count,
        counts, severity, quality,
        inflammatory_total, weighted_score,
        clinical_summary, annotated_image_url, model_version
    ) VALUES (
        gen_random_uuid(),
        v_photo1_id, v_patient1_id,
        '[
            {"label":"Papül","label_en":"Papule","confidence":0.87,"bbox":{"x":112,"y":198,"w":42,"h":45}},
            {"label":"Papül","label_en":"Papule","confidence":0.81,"bbox":{"x":245,"y":310,"w":38,"h":40}},
            {"label":"Püstül","label_en":"Pustule","confidence":0.79,"bbox":{"x":180,"y":155,"w":35,"h":37}},
            {"label":"Papül","label_en":"Papule","confidence":0.74,"bbox":{"x":320,"y":280,"w":40,"h":43}},
            {"label":"Komedon","label_en":"Comedone","confidence":0.68,"bbox":{"x":95,"y":360,"w":28,"h":30}},
            {"label":"Komedon","label_en":"Comedone","confidence":0.65,"bbox":{"x":290,"y":410,"w":25,"h":27}},
            {"label":"Papül","label_en":"Papule","confidence":0.62,"bbox":{"x":155,"y":440,"w":36,"h":38}}
        ]'::jsonb,
        7,
        '{"papule":4,"pustule":1,"nodule":0,"comedone":2,"unknown":0,"inflammatory_total":5,"total":7,"weighted_score":6.5}'::jsonb,
        '{"scale":"hayashi","label":"mild","label_tr":"Hafif","score":1}'::jsonb,
        '{"quality_passed":true,"quality_score":0.87,"flags":[],"metrics":{"width":1280,"height":960,"brightness":0.61,"contrast":0.18,"blur_score":142.3,"skin_coverage":0.52}}'::jsonb,
        5, 6.5,
        '5 inflamatuar lezyon saptandı Hayashi kriterine göre şiddet düzeyi: Hafif. 2 komedon görsel raporda ayrıca işaretlendi.',
        '/uploads/demo/ahmet_front_annotated.jpg',
        'best-v1'
    );
END IF;

RAISE NOTICE '✅ Demo seed tamamlandı.';
RAISE NOTICE '   Doktor  : ayse.kaya@deripoliklinigi.com  /  DeepDerm2024!';
RAISE NOTICE '   Hasta 1 : ahmet.yilmaz@demo.com          /  Demo1234!';
RAISE NOTICE '   Hasta 2 : fatma.demir@demo.com            /  Demo1234!';

END $$;
