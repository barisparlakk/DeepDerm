import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, Alert,
  Modal, TouchableOpacity, StatusBar,
} from 'react-native';
import { useAuth } from '../context/AuthContext';
import { changePassword, deleteAccount } from '../api/patient';
import { Card } from '../components/Card';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { colors, spacing, radius } from '../utils/theme';

export default function ProfileScreen() {
  const { patient, logout } = useAuth();
  const [showChangePwd, setShowChangePwd] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [currentPwd, setCurrentPwd] = useState('');
  const [newPwd, setNewPwd]         = useState('');
  const [pwdLoading, setPwdLoading] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const handleChangePwd = async () => {
    if (!currentPwd || !newPwd) { Alert.alert('Hata', 'Tüm alanları doldurun.'); return; }
    if (newPwd.length < 6) { Alert.alert('Hata', 'Yeni şifre en az 6 karakter olmalıdır.'); return; }
    setPwdLoading(true);
    try {
      await changePassword(currentPwd, newPwd);
      setShowChangePwd(false);
      setCurrentPwd(''); setNewPwd('');
      Alert.alert('✅', 'Şifreniz başarıyla güncellendi.');
    } catch (err: any) {
      const msg = err?.response?.data || 'Şifre değiştirilemedi.';
      Alert.alert('Hata', typeof msg === 'string' ? msg : 'Şifre değiştirilemedi.');
    } finally { setPwdLoading(false); }
  };

  const handleDeleteAccount = async () => {
    setDeleteLoading(true);
    try {
      await deleteAccount();
      await logout();
    } catch {
      Alert.alert('Hata', 'Hesap silinemedi. Lütfen tekrar deneyin.');
      setDeleteLoading(false);
    }
  };

  return (
    <View style={styles.screen}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.background} />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.pageTitle}>👤 Profilim</Text>

        {/* Avatar */}
        <View style={styles.avatarSection}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>
              {patient?.name?.charAt(0)}{patient?.surname?.charAt(0)}
            </Text>
          </View>
          <Text style={styles.fullName}>{patient?.name} {patient?.surname}</Text>
          <Text style={styles.email}>{patient?.email}</Text>
        </View>

        {/* Info Card */}
        <Card style={styles.infoCard}>
          <Text style={styles.sectionTitle}>Kişisel Bilgiler</Text>
          <InfoRow label="E-posta" value={patient?.email ?? '—'} />
          <InfoRow label="Fotoğraf Periyodu" value={`Her ${patient?.photoUploadPeriodDays ?? 30} günde bir`} />
        </Card>

        {/* Security */}
        <Card>
          <Text style={styles.sectionTitle}>Güvenlik</Text>
          <TouchableOpacity
            style={styles.menuRow}
            onPress={() => setShowChangePwd(!showChangePwd)}
          >
            <Text style={styles.menuRowText}>🔑 Şifre Değiştir</Text>
            <Text style={styles.chevron}>{showChangePwd ? '▲' : '▼'}</Text>
          </TouchableOpacity>

          {showChangePwd && (
            <View style={styles.pwdForm}>
              <Input
                label="Mevcut Şifre"
                placeholder="••••••"
                value={currentPwd}
                onChangeText={setCurrentPwd}
                secureTextEntry
              />
              <Input
                label="Yeni Şifre"
                placeholder="En az 6 karakter"
                value={newPwd}
                onChangeText={setNewPwd}
                secureTextEntry
              />
              <Button
                title="Şifreyi Güncelle"
                onPress={handleChangePwd}
                loading={pwdLoading}
                fullWidth
              />
            </View>
          )}
        </Card>

        {/* Actions */}
        <Button
          title="Çıkış Yap"
          onPress={() => Alert.alert('Çıkış', 'Çıkış yapmak istediğinize emin misiniz?', [
            { text: 'İptal', style: 'cancel' },
            { text: 'Çıkış Yap', onPress: logout },
          ])}
          variant="outline"
          fullWidth
          style={{ marginTop: spacing.lg }}
        />

        <Button
          title="Hesabımı Sil"
          onPress={() => setShowDeleteModal(true)}
          variant="ghost"
          fullWidth
          style={{ marginTop: spacing.sm }}
          textStyle={{ color: colors.danger }}
        />
        <Text style={styles.kvkkNote}>
          KVKK kapsamında hesap silme talebiniz kalıcı olarak gerçekleştirilir ve geri alınamaz.
        </Text>
      </ScrollView>

      {/* Delete Confirmation Modal */}
      <Modal
        visible={showDeleteModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowDeleteModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalBox}>
            <Text style={styles.modalIcon}>⚠️</Text>
            <Text style={styles.modalTitle}>Hesabı Sil</Text>
            <Text style={styles.modalDesc}>
              Hesabınızı silmek istediğinize emin misiniz? Bu işlem geri alınamaz.
              Tüm verileriniz kalıcı olarak silinecektir (KVKK gereği).
            </Text>
            <View style={styles.modalActions}>
              <Button
                title="Vazgeç"
                onPress={() => setShowDeleteModal(false)}
                variant="outline"
                style={styles.modalBtn}
              />
              <Button
                title="Silmeyi Onayla"
                onPress={handleDeleteAccount}
                loading={deleteLoading}
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

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen:  { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl },
  pageTitle: { fontSize: 24, fontWeight: '800', color: colors.text, marginBottom: spacing.lg },
  avatarSection: { alignItems: 'center', marginBottom: spacing.lg },
  avatar: {
    width: 80, height: 80, borderRadius: 40,
    backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center',
    marginBottom: spacing.sm,
    shadowColor: colors.primary, shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3, shadowRadius: 8, elevation: 6,
  },
  avatarText:  { color: '#fff', fontSize: 28, fontWeight: '800' },
  fullName:    { fontSize: 20, fontWeight: '700', color: colors.text },
  email:       { fontSize: 13, color: colors.textSecond, marginTop: 2 },
  infoCard:    { marginBottom: spacing.md },
  sectionTitle:{ fontSize: 15, fontWeight: '700', color: colors.text, marginBottom: spacing.md },
  infoRow:     { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.borderLight },
  infoLabel:   { fontSize: 13, color: colors.textSecond },
  infoValue:   { fontSize: 13, fontWeight: '600', color: colors.text },
  menuRow:     { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: spacing.sm },
  menuRowText: { fontSize: 14, color: colors.text, fontWeight: '600' },
  chevron:     { color: colors.textMuted },
  pwdForm:     { paddingTop: spacing.md },
  kvkkNote:    { fontSize: 11, color: colors.textMuted, textAlign: 'center', marginTop: spacing.sm, lineHeight: 16 },
  modalOverlay:{ flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'center', padding: spacing.lg },
  modalBox:    { backgroundColor: colors.surface, borderRadius: radius.xl, padding: spacing.lg },
  modalIcon:   { fontSize: 36, textAlign: 'center', marginBottom: spacing.sm },
  modalTitle:  { fontSize: 20, fontWeight: '800', color: colors.text, textAlign: 'center', marginBottom: spacing.sm },
  modalDesc:   { fontSize: 13, color: colors.textSecond, textAlign: 'center', lineHeight: 18, marginBottom: spacing.lg },
  modalActions:{ flexDirection: 'row', gap: spacing.sm },
  modalBtn:    { flex: 1 },
});
