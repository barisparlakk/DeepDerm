import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, StatusBar,
} from 'react-native';
import { getDoctorNotes, markNoteRead } from '../api/patient';
import { Card } from '../components/Card';
import { Badge } from '../components/Badge';
import { colors, spacing, radius } from '../utils/theme';
import { formatDate } from '../utils/dateUtils';

interface DoctorNote { id: string; noteText: string; createdAt: string; }

export default function DoctorNotesScreen() {
  const [notes, setNotes]         = useState<DoctorNote[]>([]);
  const [readIds, setReadIds]      = useState<Set<string>>(new Set());
  const [loading, setLoading]      = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    try {
      const data = await getDoctorNotes();
      setNotes(data);
    } catch {} finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  const handleOpen = async (note: DoctorNote) => {
    if (!readIds.has(note.id)) {
      try {
        await markNoteRead(note.id);
        setReadIds(prev => new Set(prev).add(note.id));
      } catch {}
    }
  };

  const unreadCount = notes.filter(n => !readIds.has(n.id)).length;

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
        <View style={styles.titleRow}>
          <Text style={styles.pageTitle}>📋 Doktor Notlarım</Text>
          {unreadCount > 0 && <Badge count={unreadCount} />}
        </View>
        <Text style={styles.pageDesc}>Doktorunuzun değerlendirme notları</Text>

        {notes.length === 0 ? (
          <Card style={styles.emptyCard}>
            <Text style={styles.emptyText}>Henüz doktor notu bulunmamaktadır.</Text>
          </Card>
        ) : (
          notes.map((note, idx) => {
            const isRead = readIds.has(note.id);
            return (
              <TouchableOpacity key={note.id} onPress={() => handleOpen(note)} activeOpacity={0.85}>
                <Card style={[styles.noteCard, !isRead && styles.noteCardUnread]}>
                  <View style={styles.noteHeader}>
                    <View style={styles.noteIndex}>
                      <Text style={styles.noteIndexText}>{notes.length - idx}</Text>
                    </View>
                    <View style={styles.noteMeta}>
                      <Text style={styles.noteDate}>{formatDate(note.createdAt)}</Text>
                      {!isRead && (
                        <View style={styles.unreadTag}>
                          <Text style={styles.unreadTagText}>YENİ</Text>
                        </View>
                      )}
                    </View>
                  </View>
                  <Text style={styles.noteText}>{note.noteText}</Text>
                </Card>
              </TouchableOpacity>
            );
          })
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen:  { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl },
  center:  { flex: 1, alignItems: 'center', justifyContent: 'center' },
  loadingText: { color: colors.textSecond },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  pageTitle: { fontSize: 24, fontWeight: '800', color: colors.text },
  pageDesc:  { fontSize: 13, color: colors.textSecond, marginBottom: spacing.lg, marginTop: 4 },
  emptyCard: { alignItems: 'center', padding: spacing.xl },
  emptyText: { color: colors.textSecond, textAlign: 'center' },
  noteCard: { marginBottom: spacing.sm },
  noteCardUnread: {
    borderColor: colors.primary,
    borderWidth: 1.5,
    backgroundColor: colors.primaryLight,
  },
  noteHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.sm },
  noteIndex: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center',
  },
  noteIndexText: { color: '#fff', fontWeight: '700', fontSize: 13 },
  noteMeta:  { flex: 1, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  noteDate:  { fontSize: 12, color: colors.textSecond },
  unreadTag: { backgroundColor: colors.primary, paddingHorizontal: 8, paddingVertical: 2, borderRadius: radius.full },
  unreadTagText: { color: '#fff', fontSize: 11, fontWeight: '700' },
  noteText:  { fontSize: 14, color: colors.text, lineHeight: 22 },
});
