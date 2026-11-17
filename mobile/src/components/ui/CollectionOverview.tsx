import React, { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { ApiSmartCollection } from '../../lib/api';
import { ui } from '../../design/tokens';
import AppCard from './AppCard';
import SectionHeading from './SectionHeading';
import VideoThumbnail from './VideoThumbnail';

// SAVEON_MORE_OVERVIEW_UX_V1: compact, source-grounded collection previews.
const INITIAL_VISIBLE = 4;

type Props = {
  collections: ApiSmartCollection[];
  loading: boolean;
  onOpen: (collection: ApiSmartCollection) => void;
};

export default function CollectionOverview({ collections, loading, onOpen }: Props) {
  const [showAll, setShowAll] = useState(false);
  const hasMore = collections.length > INITIAL_VISIBLE;
  const visible = hasMore && !showAll ? collections.slice(0, INITIAL_VISIBLE) : collections;

  return (
    <View style={styles.section} testID="more-collection-overview">
      <SectionHeading
        title="비슷한 영상 모음"
        subtitle="같은 주제로 저장한 영상을 한눈에 살펴보세요."
        icon="albums-outline"
      />
      {!loading && collections.length > 0 && (
        <View style={styles.countRow}>
          <Ionicons name="layers-outline" size={14} color={ui.color.brand} />
          <Text style={styles.countLabel}>영상 모음 {collections.length}개</Text>
        </View>
      )}

      {loading ? (
        <AppCard>
          <View style={styles.stateRow}>
            <ActivityIndicator size="small" color={ui.color.brand} />
            <Text style={styles.stateText}>같은 주제의 영상을 모으고 있어요.</Text>
          </View>
        </AppCard>
      ) : collections.length === 0 ? (
        <AppCard>
          <View style={styles.stateRow}>
            <Ionicons name="albums-outline" size={22} color={ui.color.secondaryText} />
            <View style={styles.stateBody}>
              <Text style={styles.stateTitle}>아직 만들어진 영상 모음이 없어요</Text>
              <Text style={styles.stateText}>비슷한 주제의 영상을 저장하면 여기에 모아 보여줄게요.</Text>
            </View>
          </View>
        </AppCard>
      ) : (
        <View style={styles.list}>
          {visible.map((collection) => {
            const first = collection.contents?.[0];
            return (
              <Pressable
                key={collection.key}
                testID={`more-collection-${collection.key}`}
                style={({ pressed }) => [styles.card, pressed && styles.pressed]}
                onPress={() => onOpen(collection)}
                accessibilityRole="button"
                accessibilityLabel={`${collection.title}, 영상 ${collection.count}개, 모음 상세 및 영상 비교 보기`}
              >
                <View style={styles.mainRow}>
                  {first ? (
                    <VideoThumbnail
                      sourceUrl={first.sourceUrl}
                      contentId={String(first.contentId)}
                      fallback="▶️"
                    />
                  ) : (
                    <View style={styles.placeholder}>
                      <Ionicons name="albums-outline" size={24} color={ui.color.brand} />
                    </View>
                  )}
                  <View style={styles.info}>
                    <View style={styles.topLine}>
                      <Text style={styles.eyebrow}>영상 모음</Text>
                      <View style={styles.pill}>
                        <Text style={styles.pillText}>{collection.count}개</Text>
                      </View>
                    </View>
                    <Text style={styles.title} numberOfLines={2}>{collection.title}</Text>
                    <Text style={styles.description} numberOfLines={2}>
                      {collection.description || '비슷한 주제로 저장한 영상이에요.'}
                    </Text>
                  </View>
                  <Ionicons name="chevron-forward" size={18} color={ui.color.secondaryText} />
                </View>
                <View style={styles.footer}>
                  {first ? (
                    <Text style={styles.previewTitle} numberOfLines={1}>
                      대표 영상 · {first.title || '저장한 영상'}
                    </Text>
                  ) : (
                    <Text style={styles.previewTitle}>영상 목록 살펴보기</Text>
                  )}
                  <View style={styles.openHint}>
                    <Text style={styles.openText}>영상 비교</Text>
                    <Ionicons name="arrow-forward-outline" size={13} color={ui.color.brand} />
                  </View>
                </View>
              </Pressable>
            );
          })}
          {hasMore && (
            <Pressable
              style={styles.moreButton}
              onPress={() => setShowAll((value) => !value)}
              accessibilityRole="button"
              accessibilityLabel={showAll ? '영상 모음 접기' : `영상 모음 ${collections.length - INITIAL_VISIBLE}개 더 보기`}
              testID="more-collection-expand"
            >
              <Text style={styles.moreText}>
                {showAll ? '영상 모음 접기' : `나머지 ${collections.length - INITIAL_VISIBLE}개 더 보기`}
              </Text>
              <Ionicons
                name={showAll ? 'chevron-up' : 'chevron-down'}
                size={17}
                color={ui.color.brand}
              />
            </Pressable>
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { marginTop: ui.spacing.xl, marginBottom: ui.spacing.lg, gap: ui.spacing.sm },
  countRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 2 },
  countLabel: { color: ui.color.brand, fontWeight: '700', fontSize: 12 },
  list: { gap: 10 },
  card: {
    backgroundColor: ui.color.surface,
    borderWidth: 1,
    borderColor: ui.color.border,
    borderRadius: ui.radius.lg,
    padding: 12,
    gap: 11,
  },
  pressed: { backgroundColor: ui.color.brandSoft },
  mainRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  placeholder: { width: 86, height: 78, borderRadius: ui.radius.md, backgroundColor: ui.color.brandSoft, alignItems: 'center', justifyContent: 'center' },
  info: { flex: 1, minWidth: 0, gap: 3 },
  topLine: { flexDirection: 'row', alignItems: 'center', gap: 7 },
  eyebrow: { color: ui.color.secondaryText, fontSize: 11, fontWeight: '700' },
  pill: { backgroundColor: ui.color.brandSoft, paddingHorizontal: 8, paddingVertical: 3, borderRadius: ui.radius.pill },
  pillText: { color: ui.color.brand, fontSize: 11, fontWeight: '800' },
  title: { color: ui.color.foreground, fontSize: 16, lineHeight: 22, fontWeight: '800' },
  description: { color: ui.color.secondaryText, fontSize: 12, lineHeight: 17 },
  footer: { borderTopWidth: 1, borderTopColor: ui.color.border, paddingTop: 10, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  previewTitle: { flex: 1, color: ui.color.secondaryText, fontSize: 11, lineHeight: 16 },
  openHint: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  openText: { color: ui.color.brand, fontSize: 12, fontWeight: '700' },
  stateRow: { minHeight: 60, flexDirection: 'row', alignItems: 'center', gap: 12 },
  stateBody: { flex: 1, gap: 4 },
  stateTitle: { color: ui.color.foreground, fontSize: 13, fontWeight: '800' },
  stateText: { flex: 1, color: ui.color.secondaryText, fontSize: ui.type.body, lineHeight: 19 },
  moreButton: { minHeight: ui.minTouchTarget, borderWidth: 1, borderColor: ui.color.border, borderRadius: ui.radius.md, backgroundColor: ui.color.surface, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7, padding: 10 },
  moreText: { color: ui.color.brand, fontSize: 13, fontWeight: '800' },
});
