import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TextInput,
  TouchableOpacity, Alert, RefreshControl, StatusBar,
} from 'react-native';
import { getMedications, getSideEffects, reportSideEffect } from '../api/patient';
import { Card } from '../components/Card';
import { Button } from '../components/Button';
import { colors, spacing, radius } from '../utils/theme';
import { formatDateTime } from '../utils/dateUtils';

interface Medication { id: string; drugName: string; }
interface SideEffect { id: string; drugName: string; description: string; reportedAt: string; }

export default function SideEffectScreen() {
  const [meds, setMeds]             = useState<Medication[]>([]);
  const [sideEffects, setSideEffects] = useState<SideEffect[]>([]);
  const [selectedDrug, setSelectedDrug] = useState('');
  const [description, setDescription]   = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    try {
      const [m, se] = await Promise.all([getMedications(), getSideEffects()]);
      setMeds(m);
      setSideEffects(se);
    } catch {}
  };

  useEffect(() => { load(); }, []);

  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  const handleSubmit = async () => {
    if (!selectedDrug) { Alert.alert('Hata', 'Lütfen bir ilaç seçin.'); return; }
    if (!description.trim()) { Alert.alert('Hata', 'Lütfen yan etkiyi açıklayın.'); return; }
    setSubmitting(true);
    try {
      const se = await reportSideEffect(selectedDrug, description.trim());
      setSideEffects(prev => [se, ...prev]);
      setSelectedDrug('');
      setDescription('');
      Alert.alert('Gönderildi', 'Yan etki bildiriminiz doktorunuza iletildi.');
    } catch {
      Alert.alert('Hata', 'Bildirim gönderilemedi. Lütfen tekrar deneyin.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <View style={styles.screen}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.background} />
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
      >
        <Text style={styles.pageTitle}>⚠️ Yan Etki Bildir</Text>
        <Text style={styles.pageDesc}>Yaşadığınız yan etkileri doktorunuza bildirin.</Text>

        {/* Form */}
        <Card>
          <Text style={styles.sectionTitle}>Yeni Bildirim</Text>

          <Text style={styles.label}>İlaç Seçin</Text>
          <View style={styles.drugList}>
            {meds.length === 0 && (
              <Text style={styles.noMeds}>İlaç bulunamadı.</Text>
            )}
            {meds.map(med => (
              <TouchableOpacity
                key={med.id}
                style={[styles.drugChip, selectedDrug === med.drugName && styles.drugChipActive]}
                onPress={() => setSelectedDrug(med.drugName)}
              >
                <Text style={[styles.drugChipText, selectedDrug === med.drugName && styles.drugChipTextActive]}>
                  {med.drugName}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={[styles.label, { marginTop: spacing.md }]}>Yan Etki Açıklaması</Text>
          <TextInput
            style={styles.textArea}
            placeholder="Yaşadığınız yan etkiyi detaylıca açıklayın..."
            placeholderTextColor={colors.textMuted}
            value={description}
            onChangeText={setDescription}
            multiline
            numberOfLines={4}
            textAlignVertical="top"
          />

          <Button
            title="Bildir"
            onPress={handleSubmit}
            loading={submitting}
            fullWidth
            style={{ marginTop: spacing.md }}
          />
        </Card>

        {/* History */}
        <Text style={styles.historyTitle}>Geçmiş Bildirimler</Text>
        {sideEffects.length === 0 ? (
          <Card style={styles.emptyCard}>
            <Text style={styles.emptyText}>Henüz yan etki bildirimi bulunmuyor.</Text>
          </Card>
        ) : (
          sideEffects.map(se => (
            <Card key={se.id} style={styles.seCard}>
              <View style={styles.seHeader}>
                <View style={styles.drugTag}>
                  <Text style={styles.drugTagText}>{se.drugName}</Text>
                </View>
                <Text style={styles.seDate}>{formatDateTime(se.reportedAt)}</Text>
              </View>
              <Text style={styles.seDesc}>{se.description}</Text>
            </Card>
          ))
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen:  { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl },
  pageTitle: { fontSize: 24, fontWeight: '800', color: colors.text },
  pageDesc:  { fontSize: 13, color: colors.textSecond, marginBottom: spacing.lg, marginTop: 4 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: spacing.md },
  label:  { fontSize: 13, fontWeight: '600', color: colors.text, marginBottom: 8 },
  drugList: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  noMeds: { color: colors.textMuted, fontSize: 13 },
  drugChip: {
    paddingHorizontal: 14, paddingVertical: 7,
    borderRadius: radius.full,
    borderWidth: 1.5, borderColor: colors.border,
    backgroundColor: colors.background,
  },
  drugChipActive:    { backgroundColor: colors.warningLight, borderColor: colors.warning },
  drugChipText:      { fontSize: 13, color: colors.textSecond, fontWeight: '500' },
  drugChipTextActive:{ color: colors.warning, fontWeight: '700' },
  textArea: {
    backgroundColor: colors.background,
    borderRadius: radius.md,
    borderWidth: 1.5,
    borderColor: colors.border,
    padding: spacing.md,
    fontSize: 14,
    color: colors.text,
    minHeight: 100,
  },
  historyTitle:{ fontSize: 16, fontWeight: '700', color: colors.text, marginTop: spacing.lg, marginBottom: spacing.sm },
  emptyCard:   { alignItems: 'center', padding: spacing.xl },
  emptyText:   { color: colors.textSecond, textAlign: 'center' },
  seCard:      { marginBottom: spacing.sm },
  seHeader:    { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.xs },
  drugTag:     { backgroundColor: colors.warningLight, paddingHorizontal: 10, paddingVertical: 3, borderRadius: radius.full },
  drugTagText: { fontSize: 12, fontWeight: '700', color: colors.warning },
  seDate:      { fontSize: 12, color: colors.textMuted },
  seDesc:      { fontSize: 14, color: colors.text, lineHeight: 20 },
});
