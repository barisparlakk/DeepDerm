import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  Modal, TextInput, Alert, ActivityIndicator, StatusBar,
} from 'react-native';
import { getEmergencyStatus, sendEmergencyAlert } from '../api/patient';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { colors, spacing, radius, shadow } from '../utils/theme';

export default function EmergencyScreen({ navigation }: any) {
  const [status, setStatus] = useState<{ canSend: boolean; usedThisMonth: number; monthlyLimit: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);

  const load = async () => {
    try {
      const s = await getEmergencyStatus();
      setStatus(s);
    } catch {} finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleSend = async () => {
    if (!message.trim()) {
      Alert.alert('Hata', 'Lütfen durumu kısaca açıklayın.');
      return;
    }
    setSending(true);
    try {
      await sendEmergencyAlert(message.trim());
      setModalVisible(false);
      setMessage('');
      setStatus(prev => prev ? { ...prev, canSend: false, usedThisMonth: 1 } : prev);
      Alert.alert('✅ Gönderildi', 'Acil bildiriminiz doktorunuza iletildi. En kısa sürede size dönecektir.');
    } catch (err: any) {
      const msg = err?.response?.data || 'Bildirim gönderilemedi.';
      Alert.alert('Hata', typeof msg === 'string' ? msg : 'Bildirim gönderilemedi.');
      setModalVisible(false);
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return <View style={styles.center}><ActivityIndicator color={colors.danger} size="large" /></View>;
  }

  return (
    <View style={styles.screen}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.background} />
      <ScrollView contentContainerStyle={styles.content}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.back}>
          <Text style={styles.backText}>← Geri</Text>
        </TouchableOpacity>

        {/* Status */}
        <Card style={[styles.statusCard, status?.canSend ? styles.statusCardOk : styles.statusCardUsed]}>
          <Text style={styles.statusIcon}>{status?.canSend ? '🟢' : '🔴'}</Text>
          <Text style={styles.statusTitle}>
            {status?.canSend ? 'Acil Bildirim Hakkınız Mevcut' : 'Hakkınız Kullanıldı'}
          </Text>
          <Text style={styles.statusDesc}>
            {status?.canSend
              ? 'Bu ay acil bildirim gönderebilirsiniz. Sadece gerçek acil durumlarda kullanın.'
              : 'Bu ay acil bildirim hakkınızı kullandınız. Bir sonraki ay yenilenecektir.'}
          </Text>
          <View style={styles.quotaRow}>
            <View style={styles.quotaDot} />
            <Text style={styles.quotaText}>Kullanım: {status?.usedThisMonth ?? 0} / {status?.monthlyLimit ?? 1}</Text>
          </View>
        </Card>

        {/* Big Emergency Button */}
        {status?.canSend && (
          <TouchableOpacity
            style={styles.bigBtn}
            onPress={() => setModalVisible(true)}
            activeOpacity={0.85}
          >
            <Text style={styles.bigBtnIcon}>🚨</Text>
            <Text style={styles.bigBtnTitle}>ACİL BİLDİRİM GÖNDER</Text>
            <Text style={styles.bigBtnSub}>Doktorunuza yüksek öncelikli bildirim gönderir</Text>
          </TouchableOpacity>
        )}

        {/* Info */}
        <Card style={styles.infoCard}>
          <Text style={styles.infoTitle}>ℹ️ Önemli Bilgi</Text>
          <Text style={styles.infoText}>
            • Bu buton yalnızca tıbbi acil durumlarda kullanılmalıdır.{'\n'}
            • Ayda 1 kez kullanım hakkınız vardır.{'\n'}
            • Gerçek bir acil durumda 112'yi arayın.{'\n'}
            • Doktorunuz en kısa sürede size geri dönecektir.
          </Text>
        </Card>
      </ScrollView>

      {/* Confirmation Modal */}
      <Modal
        visible={modalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalBox}>
            <Text style={styles.modalTitle}>🚨 Acil Bildirim</Text>
            <Text style={styles.modalDesc}>
              Doktorunuza yüksek öncelikli bir bildirim göndereceksiniz. Durumu kısaca açıklayın:
            </Text>
            <TextInput
              style={styles.modalInput}
              placeholder="Örn: Yüzümde ani şişlik ve kızarıklık oluştu..."
              placeholderTextColor={colors.textMuted}
              value={message}
              onChangeText={setMessage}
              multiline
              numberOfLines={3}
              textAlignVertical="top"
            />
            <View style={styles.modalActions}>
              <Button
                title="İptal"
                onPress={() => setModalVisible(false)}
                variant="outline"
                style={styles.modalBtn}
              />
              <Button
                title="Gönder"
                onPress={handleSend}
                loading={sending}
                variant="danger"
                style={styles.modalBtn}
              />
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  screen:  { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl },
  center:  { flex: 1, alignItems: 'center', justifyContent: 'center' },
  back: { marginBottom: spacing.lg },
  backText: { color: colors.primary, fontSize: 15, fontWeight: '600' },
  statusCard: { marginBottom: spacing.lg, alignItems: 'center' },
  statusCardOk:   { borderColor: colors.accent,  borderWidth: 1.5, backgroundColor: colors.accentLight },
  statusCardUsed: { borderColor: colors.danger,  borderWidth: 1.5, backgroundColor: colors.dangerLight },
  statusIcon:  { fontSize: 32, marginBottom: spacing.sm },
  statusTitle: { fontSize: 16, fontWeight: '700', color: colors.text, textAlign: 'center' },
  statusDesc:  { fontSize: 13, color: colors.textSecond, textAlign: 'center', lineHeight: 18, marginTop: spacing.xs },
  quotaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: spacing.sm },
  quotaDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.primary },
  quotaText:{ fontSize: 12, color: colors.textSecond, fontWeight: '600' },
  bigBtn: {
    backgroundColor: colors.danger,
    borderRadius: radius.xl,
    padding: spacing.xl,
    alignItems: 'center',
    marginBottom: spacing.lg,
    ...shadow.md,
    shadowColor: colors.danger,
    shadowOpacity: 0.4,
  },
  bigBtnIcon:  { fontSize: 48, marginBottom: spacing.sm },
  bigBtnTitle: { color: '#fff', fontSize: 20, fontWeight: '900', letterSpacing: 0.5 },
  bigBtnSub:   { color: 'rgba(255,255,255,0.8)', fontSize: 12, marginTop: 4, textAlign: 'center' },
  infoCard:  { backgroundColor: colors.primaryLight, borderColor: colors.primary, borderWidth: 1 },
  infoTitle: { fontSize: 14, fontWeight: '700', color: colors.primaryDark, marginBottom: spacing.sm },
  infoText:  { fontSize: 13, color: colors.primaryDark, lineHeight: 20 },
  modalOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'flex-end',
  },
  modalBox: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 24, borderTopRightRadius: 24,
    padding: spacing.lg,
    paddingBottom: 40,
  },
  modalTitle:  { fontSize: 20, fontWeight: '800', color: colors.text, marginBottom: spacing.sm },
  modalDesc:   { fontSize: 13, color: colors.textSecond, lineHeight: 18, marginBottom: spacing.md },
  modalInput: {
    backgroundColor: colors.background,
    borderRadius: radius.md,
    borderWidth: 1.5,
    borderColor: colors.border,
    padding: spacing.md,
    fontSize: 14,
    color: colors.text,
    minHeight: 80,
    marginBottom: spacing.md,
  },
  modalActions: { flexDirection: 'row', gap: spacing.sm },
  modalBtn: { flex: 1 },
});
