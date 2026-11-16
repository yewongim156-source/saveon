import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { ui } from '../../design/tokens';
import BrandGradient from './BrandGradient';

type Props = {
  summary: string;
  commonCount: number;
  differenceCount: number;
  uniqueCount: number;
  expanded: boolean;
  onToggle: () => void;
};

/** Collapses presentation, never changes model results or their evidence. */
export default function ComparisonDigest({
  summary, commonCount, differenceCount, uniqueCount, expanded, onToggle,
}: Props) {
  const total = commonCount + differenceCount + uniqueCount;
  return (
    <View style={styles.container} testID="comparison-digest">
      <BrandGradient variant="soft" radius={18} />
      <View style={styles.heading}>
        <Ionicons name="sparkles-outline" size={19} color={ui.color.brand} />
        <Text style={styles.title}>한눈에 보기</Text>
      </View>
      <Text style={styles.summary}>{summary?.trim() || '영상에서 확인된 비교 내용을 모았어요.'}</Text>
      <View style={styles.countRow}>
        <View style={styles.countItem}><Text style={styles.count}>{commonCount}</Text><Text style={styles.countLabel}>공통 주제</Text></View>
        <View style={styles.divider} />
        <View style={styles.countItem}><Text style={styles.count}>{differenceCount}</Text><Text style={styles.countLabel}>서로 다른 내용</Text></View>
        <View style={styles.divider} />
        <View style={styles.countItem}><Text style={styles.count}>{uniqueCount}</Text><Text style={styles.countLabel}>영상별 정보</Text></View>
      </View>
      <Text style={styles.note}>같은 주제를 다뤄도 의견은 다를 수 있어요.</Text>
      {total > 0 ? (
        <Pressable
          style={styles.toggle}
          onPress={onToggle}
          accessibilityRole="button"
          accessibilityLabel={expanded ? '비교 근거 접기' : '비교 근거 펼치기'}
          accessibilityState={{ expanded }}
          testID="comparison-evidence-toggle"
        >
          <Text style={styles.toggleLabel}>{expanded ? '자세히 접기' : '자세히 보기'}</Text>
          <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={18} color={ui.color.brand} />
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { backgroundColor: ui.color.brandSoft, borderRadius: ui.radius.lg, padding: ui.spacing.md, gap: ui.spacing.sm },
  heading: { flexDirection: 'row', alignItems: 'center', gap: ui.spacing.xs },
  title: { fontSize: 16, fontWeight: '800', color: ui.color.foreground },
  summary: { fontSize: ui.type.body, lineHeight: 22, fontWeight: '600', color: ui.color.foreground },
  countRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: ui.color.white, borderRadius: ui.radius.md, paddingVertical: ui.spacing.sm },
  countItem: { flex: 1, alignItems: 'center', gap: 4 },
  count: { fontSize: 19, fontWeight: '900', color: ui.color.foreground },
  countLabel: { fontSize: 11, fontWeight: '700', color: ui.color.secondaryText },
  divider: { height: 26, width: 1, backgroundColor: ui.color.border },
  note: { fontSize: ui.type.caption, lineHeight: 18, color: '#50576B' },
  toggle: { minHeight: ui.minTouchTarget, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: ui.spacing.xs, borderTopWidth: 1, borderTopColor: 'rgba(91,91,214,0.13)', paddingTop: ui.spacing.xs },
  toggleLabel: { color: ui.color.brand, fontSize: ui.type.body, fontWeight: '800' },
});

// SAVEON_BRAND_PALETTE_V1
