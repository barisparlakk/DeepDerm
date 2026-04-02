import React from 'react';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import { colors, radius, spacing } from '../utils/theme';

type BadgeColor = 'primary' | 'danger' | 'warning' | 'accent';

interface BadgeProps {
  count?: number;
  label?: string;
  color?: BadgeColor;
  style?: ViewStyle;
}

export const Badge: React.FC<BadgeProps> = ({
  count, label, color = 'danger', style,
}) => {
  const displayText = label ?? (count !== undefined ? String(count > 99 ? '99+' : count) : '');
  if (!displayText) return null;

  const bg: Record<BadgeColor, string> = {
    primary: colors.primary,
    danger:  colors.danger,
    warning: colors.warning,
    accent:  colors.accent,
  };

  return (
    <View style={[styles.badge, { backgroundColor: bg[color] }, style]}>
      <Text style={styles.text}>{displayText}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  badge: {
    borderRadius: radius.full,
    minWidth: 20,
    height: 20,
    paddingHorizontal: spacing.xs,
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: { color: '#fff', fontSize: 11, fontWeight: '700' },
});
