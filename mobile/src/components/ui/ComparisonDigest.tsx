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

/** Comparison presentation only; never changes findings, claims, or evidence. */
export default function ComparisonDigest({
  summary, commonCount, differenceCount, uniqueCount, expanded, onToggle,
}: Props) {
  const total = commonCount + differenceCount + uniqueCount;

  return (
    <View style={styles.container} testID="comparison-digest">
      <BrandGradient variant="soft" radius={18} />
      <View style={styles.heading}>
        <View style={styles.iconBox}>
          <Ionicons name="git-compare-outline" size={19} color={ui.color.brand} />
        </View>
        <View style={styles.headingText}>
          <Text style={styles.title}>영상 비교 결과</Text>
          <Text style={styles.subtitle}>저장된 영상에서 확인한 내용을 정리했어요.</Text>
        </View>
      </View>

      <Text style={styles.summary}>
        {summary?.trim() || '영상에서 확인된 비교 내용을 모았어요.'}
      </Text>

      <View style={styles.countRow}>
        <View style={styles.countItem}>
          <Text style={styles.count}>{commonCount}</Text>
          <Text style={styles.countLabel}>공통점</Text>
        </View>
        <View style={styles.divider} />
        <View style={styles.countItem}>
          <Text style={styles.count}>{differenceCount}</Text>
          <Text style={styles.countLabel}>엇갈린 점</Text>
        </View>
        <View style={styles.divider} />
        <View style={styles.countItem}>
          <Text style={styles.count}>{uniqueCount}</Text>
          <Text style={styles.countLabel}>영상별 정보</Text>
        </View>
      </View>

      {differenceCount === 0 && total > 0 ? (
        <View style={styles.noteRow}>
          <Ionicons name="information-circle-outline" size={15} color={ui.color.secondaryText} />
          <Text style={styles.noteText}>
            확인된 상충 정보가 없어요. 모든 내용이 같다는 뜻은 아니에요.
          </Text>
        </View>
      ) : (
        <View style={styles.noteRow}>
          <Ionicons name="information-circle-outline" size={15} color={ui.color.secondaryText} />
          <Text style={styles.noteText}>
            중요한 정보는 각 영상의 원문 근거를 함께 확인해 주세요.
          </Text>
        </View>
      )}

      {total > 0 ? (
        <Pressable
          style={({ pressed }) => [styles.toggle, pressed && styles.togglePressed]}
          onPress={onToggle}
          accessibilityRole="button"
          accessibilityLabel={expanded ? '비교 내용 접기' : '비교 내용 자세히 보기'}
          accessibilityState={{ expanded }}
          testID="comparison-evidence-toggle"
        >
          <Text style={styles.toggleLabel}>
            {expanded ? '비교 내용 접기' : '공통점 · 차이점 자세히 보기'}
          </Text>
          <Ionicons
            name={expanded ? 'chevron-up' : 'chevron-down'}
            size={18}
            color={ui.color.brand}
          />
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: ui.spacing.md,
    gap: ui.spacing.sm,
    backgroundColor: ui.color.brandSoft,
    borderWidth: 1,
    borderColor: '#DCE7FE',
    borderRadius: ui.radius.lg,
    overflow: 'hidden',
  },
  heading: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  iconBox: {
    width: 38, height: 38, borderRadius: 13,
    backgroundColor: 'rgba(255,255,255,0.83)',
    alignItems: 'center', justifyContent: 'center',
  },
  headingText: { flex: 1, gap: 2 },
  title: { fontSize: 16, fontWeight: '900', color: ui.color.foreground },
  subtitle: { fontSize: 11, lineHeight: 16, color: ui.color.secondaryText },
  summary: { fontSize: 14, lineHeight: 22, fontWeight: '600', color: ui.color.foreground },
  countRow: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: ui.color.white, borderRadius: 14,
    paddingVertical: 13, borderWidth: 1, borderColor: ui.color.border,
  },
  countItem: { flex: 1, alignItems: 'center', gap: 5 },
  count: { fontSize: 22, fontWeight: '900', color: ui.color.brand },
  countLabel: { fontSize: 11, fontWeight: '700', color: ui.color.secondaryText },
  divider: { height: 30, width: 1, backgroundColor: ui.color.border },
  noteRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 7 },
  noteText: { flex: 1, fontSize: 11, lineHeight: 17, color: ui.color.secondaryText },
  toggle: {
    minHeight: 46,
    backgroundColor: 'rgba(255,255,255,0.9)',
    borderWidth: 1, borderColor: '#D6E4FF',
    borderRadius: 13, flexDirection: 'row', alignItems: 'center',
    justifyContent: 'center', gap: 7, paddingHorizontal: 12,
  },
  togglePressed: { opacity: 0.75 },
  toggleLabel: { color: ui.color.brand, fontSize: 13, fontWeight: '800' },
});

// SAVEON_COMPARISON_UX_V1
