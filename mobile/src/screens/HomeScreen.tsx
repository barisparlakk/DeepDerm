import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  StatusBar, RefreshControl, Alert,
} from 'react-native';
import { useAuth } from '../context/AuthContext';
import { getUnreadNoteCount, getEmergencyStatus } from '../api/patient';
import { Card } from '../components/Card';
import { Button } from '../components/Button';
import { Badge } from '../components/Badge';
import { colors, spacing, radius, shadow } from '../utils/theme';

export default function HomeScreen({ navigation }: any) {
  const { patient } = useAuth();
  const [unreadNotes, setUnreadNotes] = useState(0);
  const [canSendEmergency, setCanSendEmergency] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    try {
      const [noteData, emergData] = await Promise.all([
        getUnreadNoteCount(),
        getEmergencyStatus(),
      ]);
      setUnreadNotes(noteData.unreadCount);
      setCanSendEmergency(emergData.canSend);
    } catch (_) {}
  };

  useEffect(() => { loadData(); }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return 'Günaydın';
    if (h < 18) return 'İyi günler';
    return 'İyi akşamlar';
  };

  return (
    <View style={styles.screen}>
      <StatusBar barStyle="light-content" backgroundColor={colors.primary} />

      {/* Top Banner */}
      <View style={styles.topBanner}>
        <View>
          <Text style={styles.greetingSmall}>{greeting()},</Text>
          <Text style={styles.greetingName}>{patient?.name} {patient?.surname}</Text>
          <Text style={styles.greetingSubtitle}>DeepDerm Hasta Paneli</Text>
        </View>
        <View style={styles.logoMini}>
          <Text style={styles.logoMiniText}>DD</Text>
        </View>
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
      >
        {/* Unread Notes Banner */}
        {unreadNotes > 0 && (
          <TouchableOpacity onPress={() => navigation.navigate('DoctorNotes')}>
            <Card style={styles.notesBanner}>
              <View style={styles.rowBetween}>
                <View style={styles.row}>
                  <Text style={styles.bannerIcon}>📋</Text>
                  <View>
                    <Text style={styles.bannerTitle}>Okunmamış Not</Text>
                    <Text style={styles.bannerSub}>Doktorunuzdan {unreadNotes} yeni not var</Text>
                  </View>
                </View>
                <Badge count={unreadNotes} color="danger" />
              </View>
            </Card>
          </TouchableOpacity>
        )}

        {/* Menu Grid */}
        <Text style={styles.sectionLabel}>Hızlı Erişim</Text>
        <View style={styles.grid}>
          <MenuCard
            icon="💊" title="İlaçlarım"
            desc="Doz takibi"
            color={colors.accent}
            onPress={() => navigation.navigate('Medications')}
          />
          <MenuCard
            icon="📸" title="Fotoğraf"
            desc="Yükle / Görüntüle"
            color={colors.primary}
            onPress={() => navigation.navigate('PhotoUpload')}
          />
          <MenuCard
            icon="⚠️" title="Yan Etki"
            desc="Bildir"
            color={colors.warning}
            onPress={() => navigation.navigate('SideEffect')}
          />
          <MenuCard
            icon="📋" title="Doktor Notları"
            desc={unreadNotes > 0 ? `${unreadNotes} yeni` : 'Görüntüle'}
            color="#8B5CF6"
            badge={unreadNotes}
            onPress={() => navigation.navigate('DoctorNotes')}
          />
        </View>

        {/* Emergency */}
        <Text style={styles.sectionLabel}>Acil Durum</Text>
        <Card style={styles.emergencyCard}>
          <Text style={styles.emergencyTitle}>🚨 Acil Bildirim</Text>
          <Text style={styles.emergencyDesc}>
            Tıbbi bir acil durumda doktorunuza anında ulaşmak için kullanın.
            {!canSendEmergency && '\n⚠️ Bu ay hakkınızı kullandınız.'}
          </Text>
          <Button
            title={canSendEmergency ? 'Acil Bildirim Gönder' : 'Bu Ay Kullanıldı'}
            onPress={() => navigation.navigate('Emergency')}
            variant={canSendEmergency ? 'danger' : 'outline'}
            style={{ marginTop: spacing.md }}
            fullWidth
            disabled={!canSendEmergency}
          />
        </Card>
      </ScrollView>
    </View>
  );
}

function MenuCard({ icon, title, desc, color, badge, onPress }: {
  icon: string; title: string; desc: string;
  color: string; badge?: number; onPress: () => void;
}) {
  return (
    <TouchableOpacity style={[styles.menuCard, shadow.sm]} onPress={onPress} activeOpacity={0.80}>
      <View style={[styles.menuIcon, { backgroundColor: color + '20' }]}>
        <Text style={styles.menuIconText}>{icon}</Text>
        {badge != null && badge > 0 && (
          <Badge count={badge} style={styles.menuBadge} />
        )}
      </View>
      <Text style={styles.menuTitle}>{title}</Text>
      <Text style={styles.menuDesc}>{desc}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  screen:   { flex: 1, backgroundColor: colors.background },
  topBanner:{
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.lg,
    paddingTop: 52,
    paddingBottom: spacing.xl,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    borderBottomLeftRadius: 28,
    borderBottomRightRadius: 28,
  },
  greetingSmall:   { color: 'rgba(255,255,255,0.8)', fontSize: 14 },
  greetingName:    { color: '#fff', fontSize: 24, fontWeight: '800', marginTop: 2 },
  greetingSubtitle:{ color: 'rgba(255,255,255,0.7)', fontSize: 12, marginTop: 2 },
  logoMini: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center', justifyContent: 'center',
  },
  logoMiniText: { color: '#fff', fontWeight: '800', fontSize: 16 },
  scroll:   { flex: 1 },
  content:  { padding: spacing.lg, paddingBottom: spacing.xxl },
  notesBanner:{
    backgroundColor: colors.dangerLight,
    borderColor: colors.danger,
    borderWidth: 1,
    marginBottom: spacing.lg,
  },
  rowBetween:{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  row:       { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  bannerIcon:{ fontSize: 24 },
  bannerTitle:{ fontWeight: '700', color: colors.dangerDark, fontSize: 14 },
  bannerSub:  { color: colors.dangerDark, fontSize: 12, opacity: 0.8 },
  sectionLabel:{
    fontSize: 11, fontWeight: '700', letterSpacing: 0.8,
    color: colors.textMuted, textTransform: 'uppercase',
    marginBottom: spacing.sm, marginTop: spacing.lg,
  },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  menuCard: {
    width: '48%',
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  menuIcon: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginBottom: spacing.sm },
  menuIconText: { fontSize: 22 },
  menuBadge: { position: 'absolute', top: -4, right: -4 },
  menuTitle: { fontSize: 15, fontWeight: '700', color: colors.text },
  menuDesc:  { fontSize: 12, color: colors.textSecond, marginTop: 2 },
  emergencyCard: {
    borderColor: colors.danger,
    borderWidth: 1,
    backgroundColor: colors.dangerLight,
    marginTop: 0,
  },
  emergencyTitle:{ fontSize: 16, fontWeight: '800', color: colors.dangerDark },
  emergencyDesc: { fontSize: 13, color: colors.dangerDark, marginTop: spacing.xs, lineHeight: 18, opacity: 0.9 },
});
