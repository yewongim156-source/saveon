import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { ui } from '../../design/tokens';

type Props = { label?: string; children: React.ReactNode };

/** Evidence is never altered or summarized by this disclosure component. */
export default function ExpandableEvidence({
  label = '영상별 근거 확인', children,
}: Props) {
  const [open, setOpen] = useState(false);

  return (
    <View style={styles.container} testID="comparison-evidence">
      <Pressable
        style={({ pressed }) => [styles.action, pressed && styles.pressed]}
        onPress={() => setOpen((previous) => !previous)}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={open ? '원문 근거 접기' : label}
      >
        <View style={styles.iconBox}>
          <Ionicons name="document-text-outline" size={16} color={ui.color.brand} />
        </View>
        <Text style={styles.label}>{open ? '원문 근거 접기' : label}</Text>
        <Ionicons
          name={open ? 'chevron-up' : 'chevron-down'}
          size={17}
          color={ui.color.brand}
        />
      </Pressable>
      {open ? <View style={styles.evidence}>{children}</View> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginTop: 9,
    borderRadius: 13,
    borderWidth: 1,
    borderColor: '#DCE6F9',
    backgroundColor: '#F8FAFF',
    overflow: 'hidden',
  },
  action: {
    minHeight: 46,
    flexDirection: 'row', alignItems: 'center', gap: 9,
    paddingHorizontal: 12, paddingVertical: 7,
  },
  pressed: { opacity: 0.7 },
  iconBox: {
    width: 28, height: 28, borderRadius: 9,
    backgroundColor: ui.color.brandSoft,
    alignItems: 'center', justifyContent: 'center',
  },
  label: { flex: 1, color: ui.color.brand, fontWeight: '800', fontSize: 12 },
  evidence: { gap: 8, paddingHorizontal: 10, paddingBottom: 10 },
});

// SAVEON_COMPARISON_UX_V1
