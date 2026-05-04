import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, KeyboardAvoidingView,
  Platform, TouchableOpacity, Alert, StatusBar,
} from 'react-native';
import { useAuth } from '../context/AuthContext';
import { Input } from '../components/Input';
import { Button } from '../components/Button';
import { colors, spacing, radius } from '../utils/theme';

export default function RegisterScreen({ navigation }: any) {
  const { register } = useAuth();
  const [name,     setName]     = useState('');
  const [surname,  setSurname]  = useState('');
  const [age,      setAge]      = useState('');
  const [gender,   setGender]   = useState<'Erkek' | 'Kadın' | ''>('');
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [kvkk,     setKvkk]    = useState(false);
  const [loading,  setLoading]  = useState(false);
  const [errors,   setErrors]   = useState<Record<string, string>>({});

  const validate = () => {
    const e: Record<string, string> = {};
    if (!name.trim())    e.name    = 'Ad zorunludur';
    if (!surname.trim()) e.surname = 'Soyad zorunludur';
    const ageNum = parseInt(age);
    if (isNaN(ageNum) || ageNum < 1 || ageNum > 149) e.age = 'Geçerli bir yaş girin';
    if (!gender)         e.gender   = 'Cinsiyet seçiniz';
    if (!email.trim() || !email.includes('@')) e.email = 'Geçerli bir e-posta girin';
    if (password.length < 6) e.password = 'Şifre en az 6 karakter olmalıdır';
    if (!kvkk)           e.kvkk = 'KVKK onayı zorunludur';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleRegister = async () => {
    if (!validate()) return;
    setLoading(true);
    try {
      await register({
        name: name.trim(),
        surname: surname.trim(),
        age: parseInt(age),
        gender,
        email: email.trim(),
        password,
        kvkkConsent: kvkk,
      });
    } catch (err: any) {
      const data = err?.response?.data;
      let msg: string;
      if (typeof data === 'string') {
        msg = data;
      } else if (data?.fields) {
        // Validation error — show the first field error
        msg = Object.values(data.fields as Record<string, string>)[0] ?? 'Kayıt başarısız.';
      } else {
        msg = data?.error || data?.message || 'Kayıt başarısız. Lütfen tekrar deneyin.';
      }
      Alert.alert('Kayıt Hatası', msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <StatusBar barStyle="dark-content" backgroundColor={colors.background} />
      <ScrollView
        contentContainerStyle={styles.container}
        keyboardShouldPersistTaps="handled"
      >
        {/* Back */}
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>← Geri</Text>
        </TouchableOpacity>

        <Text style={styles.title}>Hesap Oluştur</Text>
        <Text style={styles.desc}>Doktorunuzla bağlantı kurmak için kayıt olun.</Text>

        <View style={styles.row}>
          <Input
            label="Ad"
            placeholder="Adınız"
            value={name}
            onChangeText={setName}
            error={errors.name}
            containerStyle={styles.half}
          />
          <Input
            label="Soyad"
            placeholder="Soyadınız"
            value={surname}
            onChangeText={setSurname}
            error={errors.surname}
            containerStyle={styles.half}
          />
        </View>

        <View style={styles.row}>
          <Input
            label="Yaş"
            placeholder="23"
            value={age}
            onChangeText={setAge}
            keyboardType="number-pad"
            error={errors.age}
            containerStyle={styles.half}
          />
          <View style={[styles.half, { marginBottom: spacing.md }]}>
            <Text style={styles.label}>Cinsiyet</Text>
            <View style={styles.genderRow}>
              {(['Erkek', 'Kadın'] as const).map((g) => (
                <TouchableOpacity
                  key={g}
                  style={[styles.genderBtn, gender === g && styles.genderBtnActive]}
                  onPress={() => setGender(g)}
                >
                  <Text style={[styles.genderText, gender === g && styles.genderTextActive]}>{g}</Text>
                </TouchableOpacity>
              ))}
            </View>
            {errors.gender ? <Text style={styles.errorText}>{errors.gender}</Text> : null}
          </View>
        </View>

        <Input
          label="E-posta"
          placeholder="ornek@email.com"
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          error={errors.email}
        />
        <Input
          label="Şifre"
          placeholder="En az 6 karakter"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          error={errors.password}
        />

        {/* KVKK */}
        <TouchableOpacity style={styles.kvkkRow} onPress={() => setKvkk(!kvkk)}>
          <View style={[styles.checkbox, kvkk && styles.checkboxActive]}>
            {kvkk && <Text style={styles.checkMark}>✓</Text>}
          </View>
          <Text style={styles.kvkkText}>
            KVKK kapsamında kişisel verilerimin işlenmesine açık rıza veriyorum.
          </Text>
        </TouchableOpacity>
        {errors.kvkk ? <Text style={styles.errorText}>{errors.kvkk}</Text> : null}

        <Button
          title="Kayıt Ol"
          onPress={handleRegister}
          loading={loading}
          fullWidth
          style={{ marginTop: spacing.lg }}
        />

        <View style={styles.footer}>
          <Text style={styles.footerText}>Zaten hesabınız var mı? </Text>
          <TouchableOpacity onPress={() => navigation.goBack()}>
            <Text style={styles.link}>Giriş Yap</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: colors.background },
  container: { flexGrow: 1, padding: spacing.lg, paddingTop: spacing.xl },
  backBtn: { marginBottom: spacing.lg },
  backText: { color: colors.primary, fontSize: 15, fontWeight: '600' },
  title: { fontSize: 26, fontWeight: '800', color: colors.text, marginBottom: 4 },
  desc:  { fontSize: 13, color: colors.textSecond, marginBottom: spacing.lg },
  row: { flexDirection: 'row', gap: spacing.sm },
  half: { flex: 1 },
  label: { fontSize: 13, fontWeight: '600', color: colors.text, marginBottom: 6 },
  genderRow: { flexDirection: 'row', gap: spacing.sm },
  genderBtn: {
    flex: 1,
    paddingVertical: 11,
    borderRadius: radius.md,
    borderWidth: 1.5,
    borderColor: colors.border,
    backgroundColor: colors.background,
    alignItems: 'center',
  },
  genderBtnActive: { backgroundColor: colors.primaryLight, borderColor: colors.primary },
  genderText:      { fontSize: 14, color: colors.textSecond, fontWeight: '500' },
  genderTextActive:{ color: colors.primary, fontWeight: '700' },
  kvkkRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    marginBottom: 4,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
    flexShrink: 0,
  },
  checkboxActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  checkMark: { color: '#fff', fontWeight: '800', fontSize: 13 },
  kvkkText:  { flex: 1, fontSize: 13, color: colors.textSecond, lineHeight: 18 },
  errorText: { fontSize: 12, color: colors.danger, marginTop: 2, marginBottom: spacing.sm },
  footer: { flexDirection: 'row', justifyContent: 'center', marginTop: spacing.lg },
  footerText: { color: colors.textSecond, fontSize: 14 },
  link: { color: colors.primary, fontWeight: '700', fontSize: 14 },
});
