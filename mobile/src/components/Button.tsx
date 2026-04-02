import React from 'react';
import {
  TouchableOpacity, Text, ActivityIndicator, StyleSheet, ViewStyle, TextStyle,
} from 'react-native';
import { colors, radius, spacing } from '../utils/theme';

type Variant = 'primary' | 'danger' | 'outline' | 'ghost';

interface ButtonProps {
  title: string;
  onPress: () => void;
  variant?: Variant;
  loading?: boolean;
  disabled?: boolean;
  style?: ViewStyle;
  textStyle?: TextStyle;
  fullWidth?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  title, onPress, variant = 'primary', loading = false,
  disabled = false, style, textStyle, fullWidth = false,
}) => {
  const isDisabled = disabled || loading;
  return (
    <TouchableOpacity
      style={[
        styles.base,
        styles[variant],
        fullWidth && { width: '100%' },
        isDisabled && styles.disabledBase,
        style,
      ]}
      onPress={onPress}
      disabled={isDisabled}
      activeOpacity={0.75}
    >
      {loading
        ? <ActivityIndicator color={variant === 'outline' || variant === 'ghost' ? colors.primary : '#fff'} />
        : <Text style={[styles.text, styles[`${variant}Text` as keyof typeof styles], textStyle]}>{title}</Text>
      }
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  base: {
    paddingVertical: 14,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 50,
  },
  primary:     { backgroundColor: colors.primary },
  danger:      { backgroundColor: colors.danger },
  outline:     { backgroundColor: 'transparent', borderWidth: 1.5, borderColor: colors.primary },
  ghost:       { backgroundColor: 'transparent' },
  disabledBase:{ opacity: 0.5 },
  text: {
    fontSize: 16,
    fontWeight: '600',
    letterSpacing: 0.2,
  },
  primaryText: { color: '#fff' },
  dangerText:  { color: '#fff' },
  outlineText: { color: colors.primary },
  ghostText:   { color: colors.primary },
});
