import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { ui } from '../../design/tokens';
import type { ApiCollectionComparisonEvidence } from '../../lib/api';

type Props = {
  evidences: ApiCollectionComparisonEvidence[];
  onOpenContent: (contentId: number) => void;
};

function EvidenceCard({ evidence, onOpenContent }: {
  evidence: ApiCollectionComparisonEvidence;
  onOpenContent: (contentId: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const quote = String(evidence.quote ?? '').trim();
  const canExpand = quote.length > 85;
  const time = evidence.timestampSeconds;
  const timeLabel = typeof time === 'number' && Number.isFinite(time) && time >= 0
    ? `${Math.floor(time / 60)}:${String(Math.floor(time % 60)).padStart(2, '0')}`
    : null;

  return (
    <View style={styles.card} testID={`comparison-evidence-${evidence.contentId}`}>
      <View style={styles.top}>
        <View style={styles.iconBox}>
          <Ionicons name="videocam-outline" size={17} color={ui.color.brand} />
        </View>
        <View style={styles.headline}>
          <Text style={styles.eyebrow}>저장한 영상 · #{evidence.contentId}</Text>
          <Text style={styles.title} numberOfLines={2}>
            {evidence.title?.trim() || '저장한 영상'}
          </Text>
        </View>
        {timeLabel ? <Text style={styles.time}>{timeLabel}</Text> : null}
      </View>
      {quote ? (
        <Text style={styles.quote} numberOfLines={expanded ? undefined : 3}>
          “{quote}”
        </Text>
      ) : (
        <Text style={styles.emptyQuote}>표시할 원문 근거가 없어요.</Text>
      )}
      <View style={styles.actions}>
        {canExpand ? (
          <Pressable
            onPress={() => setExpanded((value) => !value)}
            accessibilityRole="button"
            accessibilityLabel={expanded ? '원문 접기' : '원문 더 보기'}
            accessibilityState={{ expanded }}
            style={styles.action}
            hitSlop={6}
          >
            <Text style={styles.actionText}>{expanded ? '원문 접기' : '원문 더 보기'}</Text>
            <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={14} color={ui.color.brand} />
          </Pressable>
        ) : <View />}
        <Pressable
          onPress={() => onOpenContent(evidence.contentId)}
          accessibilityRole="button"
          accessibilityLabel={`${evidence.title || '저장한 영상'} 상세 보기`}
          style={styles.action}
          hitSlop={6}
        >
          <Ionicons name="arrow-forward-circle-outline" size={16} color={ui.color.brand} />
          <Text style={styles.actionText}>저장물 보기</Text>
        </Pressable>
      </View>
    </View>
  );
}

/** UI only: renders exactly the comparison evidences returned by the API. */
export default function ComparisonEvidenceCards({ evidences, onOpenContent }: Props) {
  if (!evidences.length) return null;
  return (
    <View style={styles.list}>
      {evidences.map((evidence, index) => (
        <EvidenceCard
          key={`${evidence.contentId}:${index}`}
          evidence={evidence}
          onOpenContent={onOpenContent}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  list: { gap: 9, marginTop: 8 },
  card: {
    padding: 12,
    backgroundColor: ui.color.surface,
    borderWidth: 1,
    borderColor: ui.color.border,
    borderRadius: ui.radius.md,
    gap: 9,
  },
  top: { flexDirection: 'row', gap: 9, alignItems: 'center' },
  iconBox: {
    width: 34, height: 34, borderRadius: 11,
    alignItems: 'center', justifyContent: 'center', backgroundColor: ui.color.brandSoft,
  },
  headline: { flex: 1, minWidth: 0, gap: 3 },
  eyebrow: { color: ui.color.secondaryText, fontSize: 10, fontWeight: '700' },
  title: { color: ui.color.foreground, fontSize: 12, lineHeight: 17, fontWeight: '800' },
  time: { fontSize: 11, color: ui.color.secondaryText, fontWeight: '700' },
  quote: { color: ui.color.secondaryText, fontSize: 12, lineHeight: 19 },
  emptyQuote: { color: ui.color.secondaryText, fontSize: 11 },
  actions: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    borderTopWidth: 1, borderTopColor: ui.color.border, paddingTop: 7,
  },
  action: { minHeight: 34, flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 4 },
  actionText: { color: ui.color.brand, fontSize: 11, fontWeight: '800' },
});
