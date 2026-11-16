import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { ApiInterestTimeline, ApiInterestTimelineTrend } from '../../lib/api';
import { ui } from '../../design/tokens';
import AppCard from './AppCard';
import SectionHeading from './SectionHeading';

type Props = {
  timeline: ApiInterestTimeline | null;
  loading: boolean;
  expanded: boolean;
  onToggle: () => void;
};

function Trend({ trend }: { trend: ApiInterestTimelineTrend }) {
  const rising = trend.delta > 0;
  const falling = trend.delta < 0;
  const marker = rising ? 'arrow-up-outline' : falling ? 'arrow-down-outline' : 'remove-outline';
  const color = rising ? ui.color.brand : ui.color.secondaryText;
  return (
    <View style={styles.trendRow}>
      <Text style={styles.trendLabel} numberOfLines={1}>{trend.label}</Text>
      <View style={styles.trendValues}>
        <Text style={styles.trendCount}>{trend.currentCount}개</Text>
        <Ionicons name={marker} size={13} color={color} />
        <Text style={[styles.delta, { color }]}>
          {trend.delta > 0 ? '+' : ''}{trend.delta}
        </Text>
      </View>
    </View>
  );
}

/** Compact home-facing summary; never interprets delta as a user sentiment score. */
// save:on UI_POLISH_V4
export default function InterestHighlights({ timeline, loading, expanded, onToggle }: Props) {
  const canExpand = !!timeline && (
    timeline.categoryTrends.length > 2 ||
    timeline.emergingInterests.length > 3 ||
    timeline.topInterests.length > 0
  );
  return (
    <View style={styles.section} testID="home-interest-highlights">
      <SectionHeading
        title="요즘 많이 저장한 것"
        subtitle="지난주와 이번 주 저장 기록을 비교해 봤어요."
        icon="trending-up-outline"
      />
      <AppCard style={styles.card}>
        {loading ? (
          <View style={styles.loading}>
            <ActivityIndicator color={ui.color.brand} size="small" />
            <Text style={styles.muted}>저장 기록을 불러오는 중이에요.</Text>
          </View>
        ) : !timeline ? (
          <Text style={styles.muted}>영상을 저장하면 최근 기록을 볼 수 있어요.</Text>
        ) : (
          <>
            <View style={styles.metrics}>
              <View style={styles.metricMain}>
                <Text style={styles.metricCaption}>최근 7일</Text>
                <Text style={styles.metricValue}>{timeline.recentCount}<Text style={styles.unit}>개</Text></Text>
              </View>
              <View style={styles.metricDivider} />
              <View style={styles.metricMain}>
                <Text style={styles.metricCaption}>이전 7일</Text>
                <Text style={styles.metricValue}>{timeline.previousCount}<Text style={styles.unit}>개</Text></Text>
              </View>
              <View style={styles.monthMetric}>
                <Text style={styles.metricCaption}>최근 30일</Text>
                <Text style={styles.monthValue}>{timeline.last30DaysCount}개</Text>
              </View>
            </View>
            {timeline.summary?.trim() ? (
              <Text style={styles.summary} numberOfLines={expanded ? undefined : 2}>
                {timeline.summary}
              </Text>
            ) : null}
            {timeline.categoryTrends.length > 0 ? (
              <View style={styles.group}>
                <Text style={styles.groupTitle}>많이 저장한 주제</Text>
                {timeline.categoryTrends.slice(0, expanded ? undefined : 2).map((trend) => (
                  <Trend key={trend.label} trend={trend} />
                ))}
              </View>
            ) : null}
            {expanded && timeline.emergingInterests.length > 0 ? (
              <View style={styles.group}>
                <Text style={styles.groupTitle}>새로 관심이 생긴 주제</Text>
                <View style={styles.chips}>
                  {timeline.emergingInterests.slice(0, expanded ? undefined : 3).map((item) => (
                    <View key={`${item.type}:${item.label}`} style={styles.chip}>
                      <Text style={styles.chipText}>{item.label} · {item.count}</Text>
                    </View>
                  ))}
                </View>
              </View>
            ) : null}
            {expanded && timeline.topInterests.length > 0 && (
              <View style={styles.group}>
                <Text style={styles.groupTitle}>최근 한 달 자주 저장한 것</Text>
                <View style={styles.chips}>
                  {timeline.topInterests.map((item) => (
                    <View key={`${item.type}:${item.label}`} style={styles.chipNeutral}>
                      <Text style={styles.chipNeutralText}>{item.label} · {item.count}</Text>
                    </View>
                  ))}
                </View>
              </View>
            )}
            {canExpand && (
              <Pressable
                style={styles.toggle}
                testID="home-interest-toggle"
                onPress={onToggle}
                accessibilityRole="button"
                accessibilityLabel={expanded ? '간단히 보기' : '더 보기'}
                accessibilityState={{ expanded }}
              >
                <Text style={styles.toggleText}>{expanded ? '간단히 보기' : '더 보기'}</Text>
                <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={16} color={ui.color.brand} />
              </Pressable>
            )}
          </>
        )}
      </AppCard>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { marginTop: ui.spacing.md, marginBottom: ui.spacing.md, gap: ui.spacing.xs },
  card: { gap: ui.spacing.sm },
  loading: { flexDirection: 'row', alignItems: 'center', gap: ui.spacing.sm, minHeight: 42 },
  muted: { fontSize: ui.type.body, lineHeight: 21, color: ui.color.secondaryText },
  metrics: {
    backgroundColor: ui.color.neutralSoft,
    padding: ui.spacing.sm,
    borderRadius: ui.radius.md,
    flexDirection: 'row', alignItems: 'center', gap: ui.spacing.xs,
  },
  metricMain: { flex: 1, alignItems: 'center', gap: 3 },
  metricDivider: { height: 32, width: 1, backgroundColor: ui.color.border },
  metricCaption: { fontSize: 13, color: ui.color.secondaryText, fontWeight: '600' },
  metricValue: { fontSize: 24, fontWeight: '900', color: ui.color.foreground },
  unit: { fontSize: ui.type.caption, fontWeight: '700' },
  monthMetric: { alignItems: 'center', paddingLeft: ui.spacing.xs, gap: 4 },
  monthValue: { fontSize: 15, fontWeight: '800', color: ui.color.foreground },
  summary: { fontSize: ui.type.body, lineHeight: 21, color: ui.color.foreground, fontWeight: '600' },
  group: { gap: ui.spacing.xs },
  groupTitle: { fontSize: 14, color: ui.color.secondaryText, fontWeight: '800' },
  trendRow: {
    paddingVertical: ui.spacing.xs, paddingHorizontal: ui.spacing.sm,
    borderRadius: ui.radius.sm, backgroundColor: ui.color.neutralSoft,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: ui.spacing.xs,
  },
  trendLabel: { fontSize: ui.type.body, fontWeight: '700', color: ui.color.foreground, flex: 1 },
  trendValues: { flexDirection: 'row', alignItems: 'center', gap: ui.spacing.xs },
  trendCount: { fontSize: 13, fontWeight: '700', color: ui.color.foreground },
  delta: { fontSize: 13, fontWeight: '800', minWidth: 26, textAlign: 'right' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: ui.spacing.xs },
  chip: { paddingVertical: 7, paddingHorizontal: ui.spacing.sm, borderRadius: ui.radius.pill, backgroundColor: ui.color.brandSoft },
  chipText: { color: ui.color.brand, fontSize: 13, fontWeight: '700' },
  chipNeutral: { paddingVertical: 7, paddingHorizontal: ui.spacing.sm, borderRadius: ui.radius.pill, backgroundColor: ui.color.neutralSoft },
  chipNeutralText: { color: ui.color.foreground, fontSize: 13, fontWeight: '700' },
  toggle: {
    minHeight: ui.minTouchTarget, alignSelf: 'flex-end',
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: ui.spacing.xs, paddingHorizontal: ui.spacing.sm,
    borderTopWidth: 1, borderColor: ui.color.border,
  },
  toggleText: { color: ui.color.brand, fontSize: 13, fontWeight: '800' },
});
