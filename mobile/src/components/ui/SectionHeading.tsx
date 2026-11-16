import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { ui } from '../../design/tokens';

type Props = {
  title: string;
  subtitle?: string;
  icon?: keyof typeof Ionicons.glyphMap;
  actionLabel?: string;
  onAction?: () => void;
};

/** Shared section heading. Title stays 18pt and actions meet the tap target. */
// save:on UI_POLISH_V4
export default function SectionHeading({
  title,
  subtitle,
  icon,
  actionLabel,
  onAction,
}: Props) {
  return (
    <View style={styles.container}>
      <View style={styles.row}>
        <View style={styles.titleGroup}>
          {icon && (
            <View style={styles.iconBox}>
              <Ionicons name={icon} size={17} color={ui.color.brand} />
            </View>
          )}
          <Text style={styles.title}>{title}</Text>
        </View>
        {actionLabel && onAction && (
          <Pressable
            onPress={onAction}
            accessibilityRole="button"
            accessibilityLabel={actionLabel}
            hitSlop={6}
            style={styles.action}
          >
            <Text style={styles.actionText}>{actionLabel}</Text>
            <Ionicons name="chevron-forward" size={15} color={ui.color.brand} />
          </Pressable>
        )}
      </View>
      {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: ui.spacing.xs },
  row: {
    minHeight: ui.minTouchTarget,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: ui.spacing.xs,
  },
  titleGroup: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: ui.spacing.xs },
  iconBox: {
    width: 30, height: 30, borderRadius: ui.radius.sm,
    alignItems: 'center', justifyContent: 'center', backgroundColor: ui.color.brandSoft,
  },
  title: { flexShrink: 1, fontSize: ui.type.section, fontWeight: '800', color: ui.color.foreground },
  subtitle: { fontSize: 13, lineHeight: 19, color: ui.color.secondaryText },
  action: { minHeight: ui.minTouchTarget, flexDirection: 'row', alignItems: 'center', gap: 2, paddingHorizontal: 4 },
  actionText: { color: ui.color.brand, fontSize: 13, fontWeight: '700' },
});
