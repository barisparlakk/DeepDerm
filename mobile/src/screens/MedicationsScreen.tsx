import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  Alert, RefreshControl, StatusBar,
} from 'react-native';
import { getMedications, confirmMedication } from '../api/patient';
import { Card } from '../components/Card';
import { colors, spacing, radius } from '../utils/theme';

interface Medication {
  id: string;
  drugName: string;
  dosage: string;
  frequency: string;
  duration: string;
  instructions?: string;
  createdAt: string;
}

export default function MedicationsScreen() {
  const [meds, setMeds]         = useState<Medication[]>([]);
  const [loading, setLoading]   = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [confirmed, setConfirmed]   = useState<Set<string>>(new Set());

  const load = async () => {
    try {
      const data = await getMedications();
      setMeds(data);
    } catch { } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const handleConfirm = async (med: Medication) => {
    Alert.alert(
      'İlaç Onayı',
      `"${med.drugName}" ilacını bugün aldınız mı?`,
      [
        { text: 'İptal', style: 'cancel' },
        {
          text: 'Evet, Aldım',
          onPress: async () => {
            try {
              await confirmMedication(med.id);
              setConfirmed(prev => new Set(prev).add(med.id));
              Alert.alert('✅', 'İlaç alındı olarak kaydedildi.');
            } catch (err: any) {
              const msg = err?.response?.data || 'İşlem başarısız.';
              Alert.alert('Hata', typeof msg === 'string' ? msg : 'İşlem başarısız.');
            }
          }
        }
      ]
    );
  };

  if (loading) {
    return <View style={styles.center}><Text style={styles.loadingText}>Yükleniyor...</Text></View>;
  }

  return (
    <View style={styles.screen}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.background} />
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
      >
        <Text style={styles.pageTitle}>💊 İlaçlarım</Text>
        <Text style={styles.pageDesc}>Doktorunuzun önerdiği ilaçlar ve kullanım bilgileri</Text>

        {meds.length === 0 ? (
          <Card style={styles.emptyCard}>
            <Text style={styles.emptyText}>Henüz ilaç kaydınız bulunmamaktadır.</Text>
          </Card>
        ) : (
          meds.map((med) => {
            const isConfirmed = confirmed.has(med.id);
            return (
              <Card key={med.id} style={styles.medCard}>
                <View style={styles.medHeader}>
                  <View style={styles.medIconBox}>
                    <Text style={styles.medIcon}>💊</Text>
                  </View>
                  <View style={styles.medInfo}>
                    <Text style={styles.drugName}>{med.drugName}</Text>
                    <Text style={styles.dosage}>{med.dosage}</Text>
                  </View>
                </View>

                <View style={styles.metaRow}>
                  <MetaItem icon="🔁" label="Sıklık" value={med.frequency} />
                  <MetaItem icon="📅" label="Süre" value={med.duration} />
                </View>

                {med.instructions ? (
                  <View style={styles.instructionBox}>
                    <Text style={styles.instructionLabel}>ℹ️ Kullanım Talimatı</Text>
                    <Text style={styles.instructionText}>{med.instructions}</Text>
                  </View>
                ) : null}

                <TouchableOpacity
                  style={[styles.confirmBtn, isConfirmed && styles.confirmBtnDone]}
                  onPress={() => !isConfirmed && handleConfirm(med)}
                  disabled={isConfirmed}
                  activeOpacity={0.8}
                >
                  <Text style={[styles.confirmBtnText, isConfirmed && styles.confirmBtnTextDone]}>
                    {isConfirmed ? '✅ Bugün Alındı' : 'İlacımı Aldım'}
                  </Text>
                </TouchableOpacity>
              </Card>
            );
          })
        )}
      </ScrollView>
    </View>
  );
}

function MetaItem({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <View style={styles.meta}>
      <Text style={styles.metaIcon}>{icon}</Text>
      <View>
        <Text style={styles.metaLabel}>{label}</Text>
        <Text style={styles.metaValue}>{value}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl },
  center:  { flex: 1, alignItems: 'center', justifyContent: 'center' },
  loadingText: { color: colors.textSecond },
  pageTitle: { fontSize: 24, fontWeight: '800', color: colors.text },
  pageDesc:  { fontSize: 13, color: colors.textSecond, marginBottom: spacing.lg, marginTop: 4 },
  emptyCard: { alignItems: 'center', padding: spacing.xl },
  emptyText: { color: colors.textSecond, textAlign: 'center' },
  medCard:   { marginBottom: spacing.md },
  medHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.md },
  medIconBox:{ width: 48, height: 48, borderRadius: 14, backgroundColor: colors.accentLight, alignItems: 'center', justifyContent: 'center' },
  medIcon:   { fontSize: 24 },
  medInfo:   { flex: 1 },
  drugName:  { fontSize: 16, fontWeight: '700', color: colors.text },
  dosage:    { fontSize: 13, color: colors.textSecond, marginTop: 2 },
  metaRow:   { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.sm },
  meta:      { flex: 1, flexDirection: 'row', alignItems: 'center', gap: spacing.xs, backgroundColor: colors.background, padding: spacing.sm, borderRadius: radius.sm },
  metaIcon:  { fontSize: 16 },
  metaLabel: { fontSize: 11, color: colors.textMuted },
  metaValue: { fontSize: 13, fontWeight: '600', color: colors.text },
  instructionBox: { backgroundColor: colors.primaryLight, borderRadius: radius.sm, padding: spacing.sm, marginBottom: spacing.sm },
  instructionLabel:{ fontSize: 12, fontWeight: '700', color: colors.primaryDark, marginBottom: 2 },
  instructionText: { fontSize: 13, color: colors.primaryDark, lineHeight: 18 },
  confirmBtn: {
    paddingVertical: 12, borderRadius: radius.md,
    backgroundColor: colors.accent, alignItems: 'center', marginTop: spacing.xs,
  },
  confirmBtnDone:     { backgroundColor: colors.accentLight },
  confirmBtnText:     { color: '#fff', fontWeight: '700', fontSize: 15 },
  confirmBtnTextDone: { color: colors.accent },
});
