import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import ContentCard from '../ContentCard';
import { theme } from '../../theme';
import type { ContentItem } from '../../types';

const PAGE_SIZE = 8;

type Props = {
  query: string;
  onQueryChange: (value: string) => void;
  results: ContentItem[];
  matchMode: 'exact' | 'similar';
  onMatchModeChange: (value: 'exact' | 'similar') => void;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onOpen: (itemId: string) => void;
  onGoSave: () => void;
};

/** Presentation only. The existing keyword + semantic search in App.tsx is unchanged. */
export default function SearchResultsPanel({
  query,
  onQueryChange,
  results,
  matchMode,
  onMatchModeChange,
  loading,
  error,
  onRetry,
  onOpen,
  onGoSave,
}: Props) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const hasQuery = Boolean(query.trim());

  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [query]);

  const visibleResults = results.slice(0, visibleCount);
  const hasMore = results.length > visibleCount;

  return (
    <View style={styles.root}>
      <View style={styles.searchInputBox}>
        <Ionicons name="search-outline" size={20} color={theme.primary} />
        <TextInput
          value={query}
          onChangeText={onQueryChange}
          placeholder="장소, 상품, 관심 주제를 검색해 보세요"
          placeholderTextColor="#98A4B8"
          autoCapitalize="none"
          autoCorrect={false}
          returnKeyType="search"
          style={styles.input}
          accessibilityLabel="저장물 검색어"
        />
        {query.length > 0 && (
          <Pressable
            onPress={() => onQueryChange('')}
            hitSlop={10}
            accessibilityRole="button"
            accessibilityLabel="검색어 지우기"
          >
            <Ionicons name="close-circle" size={20} color={theme.muted} />
          </Pressable>
        )}
      </View>
      <Text style={styles.inputHint}>
        {matchMode === 'exact'
          ? '제목·요약·분류·키워드에 포함된 단어를 찾아요.'
          : 'AI가 비슷하다고 판단한 후보까지 보여줘요. 관련성을 직접 확인해 주세요.'}
      </Text>
      <View style={styles.matchModeRow}>
        <Pressable
          style={[styles.matchModeButton, matchMode === 'exact' && styles.matchModeSelected]}
          onPress={() => onMatchModeChange('exact')}
          accessibilityRole="button"
          accessibilityState={{ selected: matchMode === 'exact' }}
        >
          <Ionicons name="checkmark-circle-outline" size={15} color={matchMode === 'exact' ? theme.primary : theme.muted} />
          <Text style={[styles.matchModeLabel, matchMode === 'exact' && styles.matchModeLabelSelected]}>
            정확한 검색
          </Text>
        </Pressable>
        <Pressable
          style={[styles.matchModeButton, matchMode === 'similar' && styles.matchModeSelected]}
          onPress={() => onMatchModeChange('similar')}
          accessibilityRole="button"
          accessibilityState={{ selected: matchMode === 'similar' }}
        >
          <Ionicons name="sparkles-outline" size={15} color={matchMode === 'similar' ? theme.primary : theme.muted} />
          <Text style={[styles.matchModeLabel, matchMode === 'similar' && styles.matchModeLabelSelected]}>
            비슷한 내용
          </Text>
        </Pressable>
      </View>

      <View style={styles.headingRow}>
        <View style={styles.headingLeft}>
          <View style={styles.headingIcon}>
            <Ionicons name="albums-outline" size={16} color={theme.primary} />
          </View>
          <Text style={styles.headingText}>
            {hasQuery ? '검색 결과' : '저장한 영상'}
          </Text>
        </View>
        <Text style={styles.resultCount} accessibilityLiveRegion="polite">
          {loading ? '검색 중...' : `${results.length}개`}
        </Text>
      </View>

      {loading ? (
        <View style={styles.statusCard}>
          <ActivityIndicator size="small" color={theme.primary} />
          <Text style={styles.statusText}>관련된 저장물을 찾고 있어요.</Text>
        </View>
      ) : error ? (
        <View style={styles.statusCard}>
          <Ionicons name="alert-circle-outline" size={26} color="#B85A54" />
          <Text style={styles.statusTitle}>검색 결과를 불러오지 못했어요</Text>
          <Text style={styles.statusText}>{error}</Text>
          <Pressable style={styles.actionButton} onPress={onRetry} accessibilityRole="button">
            <Ionicons name="refresh-outline" size={16} color={theme.primary} />
            <Text style={styles.actionLabel}>다시 검색하기</Text>
          </Pressable>
        </View>
      ) : results.length === 0 ? (
        <View style={styles.statusCard}>
          <Ionicons
            name={hasQuery ? 'search-outline' : 'bookmark-outline'}
            size={28}
            color={theme.primary}
          />
          <Text style={styles.statusTitle}>
            {hasQuery ? '일치하는 저장물이 없어요' : '아직 저장한 영상이 없어요'}
          </Text>
          <Text style={styles.statusText}>
            {hasQuery
              ? matchMode === 'exact'
                ? '일치하는 단어가 없어요. 다른 단어로 검색하거나 비슷한 내용으로 넓혀 보세요.'
                : '비슷한 후보도 찾지 못했어요. 다른 키워드를 입력해 보세요.'
              : '영상 링크를 저장하면 이곳에서 다시 찾아볼 수 있어요.'}
          </Text>
          <Pressable
            style={styles.actionButton}
            onPress={hasQuery ? () => onQueryChange('') : onGoSave}
            accessibilityRole="button"
          >
            <Ionicons
              name={hasQuery ? 'close-outline' : 'add-outline'}
              size={16}
              color={theme.primary}
            />
            <Text style={styles.actionLabel}>
              {hasQuery ? '검색어 지우기' : '영상 저장하러 가기'}
            </Text>
          </Pressable>
        </View>
      ) : (
        <>
          {visibleResults.map((item) => (
            <ContentCard
              key={item.id}
              item={item}
              onPress={() => onOpen(item.id)}
            />
          ))}
          {hasMore && (
            <Pressable
              style={styles.moreButton}
              onPress={() => setVisibleCount((count) => count + PAGE_SIZE)}
              accessibilityRole="button"
              accessibilityLabel="검색 결과 더 보기"
            >
              <Text style={styles.moreLabel}>
                더 보기 ({Math.min(visibleCount, results.length)}/{results.length})
              </Text>
              <Ionicons name="chevron-down" size={16} color={theme.primary} />
            </Pressable>
          )}
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { marginTop: 4 },
  searchInputBox: {
    minHeight: 54,
    paddingHorizontal: 15,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: theme.card,
    borderColor: '#D8E3FA',
    borderWidth: 1,
    borderRadius: 17,
  },
  input: { flex: 1, paddingVertical: 12, fontSize: 14, color: theme.text },
  inputHint: { marginTop: 8, color: theme.muted, fontSize: 11, lineHeight: 16 },
  matchModeRow: {
    marginTop: 12,
    flexDirection: 'row',
    gap: 8,
  },
  matchModeButton: {
    flex: 1,
    minHeight: 37,
    paddingHorizontal: 10,
    flexDirection: 'row',
    gap: 5,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: theme.line,
    borderRadius: 12,
    backgroundColor: theme.card,
  },
  matchModeSelected: {
    borderColor: '#C8DBFF',
    backgroundColor: theme.primarySoft,
  },
  matchModeLabel: { fontSize: 12, fontWeight: '700', color: theme.muted },
  matchModeLabelSelected: { color: theme.primary },
  headingRow: {
    marginTop: 23,
    marginBottom: 13,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headingLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headingIcon: {
    width: 29, height: 29, borderRadius: 10,
    backgroundColor: theme.primarySoft,
    alignItems: 'center', justifyContent: 'center',
  },
  headingText: { color: theme.text, fontWeight: '800', fontSize: 15 },
  resultCount: { color: theme.primary, fontWeight: '800', fontSize: 12 },
  statusCard: {
    minHeight: 156,
    padding: 24,
    backgroundColor: theme.card,
    borderWidth: 1,
    borderColor: theme.line,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  statusTitle: { textAlign: 'center', color: theme.text, fontWeight: '800', fontSize: 14 },
  statusText: { textAlign: 'center', color: theme.muted, fontSize: 12, lineHeight: 18 },
  actionButton: {
    marginTop: 5,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 11,
    backgroundColor: theme.primarySoft,
  },
  actionLabel: { color: theme.primary, fontWeight: '800', fontSize: 12 },
  moreButton: {
    minHeight: 45,
    marginTop: 4,
    marginBottom: 10,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
    borderWidth: 1,
    borderColor: '#D8E3FA',
    borderRadius: 14,
    backgroundColor: theme.card,
  },
  moreLabel: { color: theme.primary, fontSize: 12, fontWeight: '800' },
});
