import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { ApiSmartCollection } from '../../lib/api';
import { ui } from '../../design/tokens';
import AppCard from './AppCard';
import SectionHeading from './SectionHeading';

type Props = {
  collections: ApiSmartCollection[];
  loading: boolean;
  onOpen: (collection: ApiSmartCollection) => void;
};

/** Smart collections belong in 모아보기; no duplicate preview on Home. */
// save:on UI_POLISH_V4
export default function CollectionOverview({ collections, loading, onOpen }: Props) {
  return (
    <View style={styles.section} testID="more-collection-overview">
      <SectionHeading
        title="비슷한 영상 모음"
        subtitle="같은 주제의 영상을 모았어요."
        icon="albums-outline"
      />
      {loading ? (
        <AppCard>
          <View style={styles.loading}>
            <ActivityIndicator size="small" color={ui.color.brand} />
            <Text style={styles.emptyText}>비슷한 영상을 찾는 중이에요.</Text>
          </View>
        </AppCard>
      ) : collections.length === 0 ? (
        <AppCard>
          <View style={styles.loading}>
            <Ionicons name="albums-outline" size={22} color={ui.color.secondaryText} />
            <Text style={styles.emptyText}>같은 주제의 영상이 모이면 여기에 표시돼요.</Text>
          </View>
        </AppCard>
      ) : (
        <View style={styles.grid}>
          {collections.map((collection) => (
            <Pressable
              key={collection.key}
              testID={`more-collection-${collection.key}`}
              style={styles.tile}
              onPress={() => onOpen(collection)}
              accessibilityRole="button"
              accessibilityLabel={`${collection.title}, 저장물 ${collection.count}개, 자세히 보기`}
            >
              <View style={styles.top}>
                <View style={styles.iconBox}>
                  <Ionicons name="albums-outline" size={17} color={ui.color.brand} />
                </View>
                <View style={styles.countBox}>
                  <Text style={styles.countText}>{collection.count}개</Text>
                </View>
              </View>
              <Text style={styles.name} numberOfLines={2}>{collection.title}</Text>
              <Text style={styles.description} numberOfLines={2}>
                {collection.description || '같은 주제의 영상이에요.'}
              </Text>
              <View style={styles.bottom}>
                <Text style={styles.bottomText}>모아보기</Text>
                <Ionicons name="arrow-forward-outline" size={14} color={ui.color.brand} />
              </View>
            </Pressable>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { marginTop: ui.spacing.xl, marginBottom: ui.spacing.lg, gap: ui.spacing.sm },
  loading: { minHeight: 56, flexDirection: 'row', alignItems: 'center', gap: ui.spacing.sm },
  emptyText: { flex: 1, color: ui.color.secondaryText, fontSize: ui.type.body, lineHeight: 20 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', rowGap: ui.spacing.sm },
  tile: {
    width: '48.5%', minHeight: 160, padding: 13,
    backgroundColor: ui.color.surface, borderRadius: ui.radius.lg,
    borderWidth: 1, borderColor: ui.color.border, gap: ui.spacing.xs,
  },
  top: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  iconBox: { width: 34, height: 34, backgroundColor: ui.color.brandSoft, borderRadius: ui.radius.sm, alignItems: 'center', justifyContent: 'center' },
  countBox: { paddingHorizontal: ui.spacing.xs, paddingVertical: 5, borderRadius: ui.radius.pill, backgroundColor: ui.color.neutralSoft },
  countText: { fontSize: 12, color: '#515A69', fontWeight: '800' },
  name: { fontSize: 16, fontWeight: '800', lineHeight: 22, color: ui.color.foreground, minHeight: 21 },
  description: { fontSize: 13, lineHeight: 19, color: '#515A69', flexGrow: 1 },
  bottom: { marginTop: ui.spacing.xs, flexDirection: 'row', justifyContent: 'flex-end', alignItems: 'center', gap: 4 },
  bottomText: { fontSize: 13, color: ui.color.brand, fontWeight: '700' },
});
