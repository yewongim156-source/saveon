import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { ui } from '../../design/tokens';

type Props = { label?: string; children: React.ReactNode };

/** Keeps the original AI evidence intact, disclosed only on request. */
export default function ExpandableEvidence({ label = '영상별 근거 확인', children }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <View style={styles.container}>
      <Pressable
        style={styles.action}
        onPress={() => setOpen((previous) => !previous)}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={open ? '출처 접기' : label}
      >
        <Ionicons name="document-text-outline" size={15} color={ui.color.brand} />
        <Text style={styles.label}>{open ? '출처 접기' : label}</Text>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={16} color={ui.color.brand} />
      </Pressable>
      {open ? <View style={styles.evidence}>{children}</View> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginTop: 3 },
  action: { minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: 7, paddingVertical: 5 },
  label: { color: ui.color.brand, fontWeight: '800', fontSize: 13, flex: 1 },
  evidence: { gap: 8, paddingBottom: 6 },
});
