import React, { useRef, useState } from 'react';
import {
  View, Text, StyleSheet, Alert, TouchableOpacity,
  ActivityIndicator, StatusBar,
} from 'react-native';
import { Camera, useCameraDevice, useCameraPermission } from 'react-native-vision-camera';
import { uploadPhoto, checkPhotoAngle } from '../api/patient';
import { Button } from '../components/Button';
import { colors, spacing, radius } from '../utils/theme';

type Angle = 'front' | 'right' | 'left';

const ANGLES: { key: Angle; label: string; instruction: string }[] = [
  { key: 'front', label: 'Ön Görünüm',  instruction: 'Kameranıza düz bakın, yüzünüz ortada olsun.' },
  { key: 'left',  label: 'Sağ Yanak',   instruction: 'Başınızı hafifçe sola çevirin (sağ yanağınız görünsün).' },
  { key: 'right', label: 'Sol Yanak',   instruction: 'Başınızı hafifçe sağa çevirin (sol yanağınız görünsün).' },
];

export default function PhotoUploadScreen({ navigation }: any) {
  const { hasPermission, requestPermission } = useCameraPermission();
  const device = useCameraDevice('back');
  const cameraRef = useRef<any>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [captured, setCaptured] = useState<{ [k in Angle]?: string }>({});
  const [uploading, setUploading] = useState(false);
  const [checkingAngle, setCheckingAngle] = useState(false);
  const [done, setDone] = useState(false);

  const angle = ANGLES[currentStep];

  if (!hasPermission) {
    return (
      <View style={styles.center}>
        <Text style={styles.permText}>Kamera izni gereklidir.</Text>
        <Button title="İzin Ver" onPress={requestPermission} style={{ marginTop: spacing.md }} />
      </View>
    );
  }

  const takePicture = async () => {
    if (!cameraRef.current) return;
    try {
      setCheckingAngle(true);
      const photo = await cameraRef.current.takePhoto({
        qualityPrioritization: 'speed',
        flash: 'off',
        skipMetadata: true,
      });
      if (!photo) {
        setCheckingAngle(false);
        return;
      }
      
      const fileUri = `file://${photo.path}`;

      // Check angle on backend
      const result = await checkPhotoAngle(fileUri, angle.key);
      setCheckingAngle(false);

      if (!result.valid) {
        Alert.alert('Hatalı Açı', result.message || 'Lütfen açıyı düzeltip tekrar çekin.');
        return;
      }
      setCaptured(prev => ({ ...prev, [angle.key]: fileUri }));
      if (currentStep < ANGLES.length - 1) {
        setTimeout(() => setCurrentStep(s => s + 1), 300);
      }
    } catch (err: any) {
      setCheckingAngle(false);
      const data = err?.response?.data;
      const msg = typeof data === 'string'
        ? data
        : data?.error || data?.message || err?.message || 'Fotoğraf çekilemedi veya açı doğrulanamadı.';
      Alert.alert('Hata', msg);
    }
  };

  const retake = () => {
    setCaptured(prev => { const n = { ...prev }; delete n[angle.key]; return n; });
  };

  const uploadAll = async () => {
    const allAngles: Angle[] = ['front', 'right', 'left'];
    const missing = allAngles.filter(a => !captured[a]);
    if (missing.length) {
      Alert.alert('Eksik Fotoğraf', 'Tüm açılar için fotoğraf çekmeniz gerekmektedir.');
      return;
    }
    setUploading(true);
    try {
      for (const a of allAngles) {
        await uploadPhoto(captured[a]!, a);
      }
      setDone(true);
    } catch (err: any) {
      const msg = err?.response?.data || 'Yükleme başarısız.';
      Alert.alert('Yükleme Hatası', typeof msg === 'string' ? msg : 'Yükleme başarısız.');
    } finally {
      setUploading(false);
    }
  };

  if (done) {
    return (
      <View style={styles.center}>
        <Text style={styles.doneIcon}>✅</Text>
        <Text style={styles.doneTitle}>Fotoğraflar Yüklendi!</Text>
        <Text style={styles.doneDesc}>Doktorunuz en kısa sürede değerlendirecektir.</Text>
        <Button title="Ana Sayfaya Dön" onPress={() => navigation.goBack()}
          style={{ marginTop: spacing.lg, width: 220 }} />
      </View>
    );
  }

  const isCaptured = !!captured[angle.key];

  return (
    <View style={styles.screen}>
      <StatusBar barStyle="light-content" backgroundColor="#000" />

      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.back}>← Geri</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Fotoğraf Yükleme</Text>
        <Text style={styles.step}>{currentStep + 1} / {ANGLES.length}</Text>
      </View>

      {/* Step indicator */}
      <View style={styles.steps}>
        {ANGLES.map((a, i) => (
          <View key={a.key} style={styles.stepItem}>
            <View style={[
              styles.stepDot,
              i < currentStep  && styles.stepDone,
              i === currentStep && styles.stepActive,
              captured[a.key] && i < currentStep && styles.stepDone,
            ]}>
              {captured[a.key] && i <= currentStep
                ? <Text style={styles.stepCheck}>✓</Text>
                : <Text style={[styles.stepNum, i === currentStep && { color: '#fff' }]}>{i + 1}</Text>
              }
            </View>
            <Text style={[styles.stepLabel, i === currentStep && { color: colors.primary }]}>
              {a.label}
            </Text>
          </View>
        ))}
      </View>

      {/* Camera */}
      <View style={styles.cameraContainer}>
        {device ? (
            <Camera
              ref={cameraRef as any}
              style={StyleSheet.absoluteFill}
              device={device}
              isActive={!isCaptured && !uploading && !done}
              photo={true}
            />
        ) : (
          <View style={styles.center}><ActivityIndicator color="#fff" /></View>
        )}

        {/* Overlay guide */}
        <View style={styles.overlay}>
          <View style={styles.faceGuide} />
          {/* Corner brackets */}
          <View style={[styles.corner, styles.cornerTL]} />
          <View style={[styles.corner, styles.cornerTR]} />
          <View style={[styles.corner, styles.cornerBL]} />
          <View style={[styles.corner, styles.cornerBR]} />
        </View>
      </View>

      {/* Instruction */}
      <View style={styles.instructionBox}>
        <Text style={styles.angleTitle}>{angle.label}</Text>
        <Text style={styles.instruction}>{angle.instruction}</Text>
      </View>

      {/* Controls */}
      <View style={styles.controls}>
        {!isCaptured ? (
          <TouchableOpacity style={styles.captureBtn} onPress={takePicture} disabled={checkingAngle}>
            {checkingAngle ? (
              <ActivityIndicator color="#fff" size="large" />
            ) : (
              <View style={styles.captureBtnInner} />
            )}
          </TouchableOpacity>
        ) : (
          <View style={styles.capturedControls}>
            <Text style={styles.capturedText}>✅ Fotoğraf çekildi</Text>
            <TouchableOpacity onPress={retake} style={styles.retakeBtn}>
              <Text style={styles.retakeText}>Tekrar Çek</Text>
            </TouchableOpacity>
            {currentStep < ANGLES.length - 1 && (
              <Button
                title={`Sonraki: ${ANGLES[currentStep + 1].label} →`}
                onPress={() => setCurrentStep(s => s + 1)}
                style={styles.nextBtn}
              />
            )}
          </View>
        )}

        {Object.keys(captured).length === ANGLES.length && (
          <Button
            title="Tüm Fotoğrafları Yükle"
            onPress={uploadAll}
            loading={uploading}
            variant="primary"
            fullWidth
            style={styles.uploadBtn}
          />
        )}
      </View>
    </View>
  );
}

const GUIDE = 220;
const CORNER = 24;

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#0a0a0a' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.lg, backgroundColor: colors.background },
  permText: { fontSize: 16, color: colors.text, textAlign: 'center' },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: spacing.lg, paddingTop: 52, paddingBottom: spacing.sm,
  },
  back: { color: colors.primary, fontSize: 15, fontWeight: '600' },
  headerTitle: { color: '#fff', fontSize: 16, fontWeight: '700' },
  step: { color: colors.textMuted, fontSize: 13 },
  steps: {
    flexDirection: 'row', justifyContent: 'center', gap: spacing.xl,
    paddingVertical: spacing.md,
  },
  stepItem: { alignItems: 'center', gap: 4 },
  stepDot: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: '#333', alignItems: 'center', justifyContent: 'center',
  },
  stepActive: { backgroundColor: colors.primary },
  stepDone:   { backgroundColor: colors.accent },
  stepNum:    { color: colors.textMuted, fontWeight: '700', fontSize: 14 },
  stepCheck:  { color: '#fff', fontWeight: '700', fontSize: 14 },
  stepLabel:  { color: colors.textMuted, fontSize: 11 },
  cameraContainer: { flex: 1, backgroundColor: '#000' },
  camera: { flex: 1 },
  overlay: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center' },
  faceGuide: {
    width: GUIDE, height: GUIDE * 1.25,
    borderRadius: GUIDE / 2,
    borderWidth: 2, borderColor: 'rgba(255,255,255,0.35)',
    backgroundColor: 'transparent',
  },
  faceGuideCorrect: { borderColor: colors.accent, borderWidth: 3 },
  corner: { position: 'absolute', width: CORNER, height: CORNER, borderColor: colors.primary },
  cornerCorrect: { borderColor: colors.accent },
  cornerTL: { top: '50%', left: '50%',
    marginTop: -(GUIDE * 0.625 + 4), marginLeft: -(GUIDE / 2 + 4),
    borderTopWidth: 3, borderLeftWidth: 3, borderTopLeftRadius: 4 },
  cornerTR: { top: '50%', right: '50%',
    marginTop: -(GUIDE * 0.625 + 4), marginRight: -(GUIDE / 2 + 4),
    borderTopWidth: 3, borderRightWidth: 3, borderTopRightRadius: 4 },
  cornerBL: { bottom: '50%', left: '50%',
    marginBottom: -(GUIDE * 0.625 + 4), marginLeft: -(GUIDE / 2 + 4),
    borderBottomWidth: 3, borderLeftWidth: 3, borderBottomLeftRadius: 4 },
  cornerBR: { bottom: '50%', right: '50%',
    marginBottom: -(GUIDE * 0.625 + 4), marginRight: -(GUIDE / 2 + 4),
    borderBottomWidth: 3, borderRightWidth: 3, borderBottomRightRadius: 4 },
  instructionBox: {
    backgroundColor: '#1a1a1a', padding: spacing.md,
    borderTopWidth: 1, borderTopColor: '#333',
  },
  angleTitle:  { color: '#fff', fontWeight: '700', fontSize: 15 },
  instruction: { color: colors.textMuted, fontSize: 13, marginTop: 4, lineHeight: 18 },
  controls: {
    backgroundColor: '#0a0a0a', paddingHorizontal: spacing.lg,
    paddingBottom: 36, paddingTop: spacing.md, alignItems: 'center',
  },
  captureBtn: {
    width: 72, height: 72, borderRadius: 36,
    borderWidth: 3, borderColor: '#fff',
    alignItems: 'center', justifyContent: 'center',
  },
  captureBtnInner: { width: 56, height: 56, borderRadius: 28, backgroundColor: '#fff' },
  capturedControls: { alignItems: 'center', gap: spacing.sm, width: '100%' },
  capturedText: { color: colors.accent, fontWeight: '700', fontSize: 15 },
  retakeBtn: { paddingVertical: 8, paddingHorizontal: 20, borderRadius: radius.md, backgroundColor: '#333' },
  retakeText: { color: '#fff', fontWeight: '600' },
  nextBtn:    { marginTop: 4, width: '100%' },
  uploadBtn:  { marginTop: spacing.sm },
  doneIcon:   { fontSize: 56, marginBottom: spacing.md },
  doneTitle:  { fontSize: 22, fontWeight: '800', color: colors.text },
  doneDesc:   { fontSize: 14, color: colors.textSecond, marginTop: spacing.sm, textAlign: 'center' },
});
