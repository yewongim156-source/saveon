import React from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '../../theme';

export type LibrarySortOrder = 'newest' | 'oldest' | 'title';

type Props = {
  query: string;
  onQueryChange: (value: string) => void;
  sort: LibrarySortOrder;
  onSortChange: (value: LibrarySortOrder) => void;
  resultCount: number;
  totalCount: number;
};

const SORT_LABEL: Record<LibrarySortOrder, string> = {
  newest: '최신순',
  oldest: '오래된순',
  title: '제목순',
};

const NEXT_SORT: Record<LibrarySortOrder, LibrarySortOrder> = {
  newest: 'oldest',
  oldest: 'title',
  title: 'newest',
};

/** Small, local-only search & sort controls. No network calls or API changes. */
export default function LibraryFindBar({
  query,
  onQueryChange,
  sort,
  onSortChange,
  resultCount,
  totalCount,
}: Props) {
  return (
    <View style={styles.container}>
      <View style={styles.searchBox}>
        <Ionicons name="search-outline" size={19} color={theme.primary} />
        <TextInput
          style={styles.input}
          placeholder="제목, 내용, 태그로 찾기"
          placeholderTextColor={theme.muted}
          value={query}
          onChangeText={onQueryChange}
          autoCapitalize="none"
          autoCorrect={false}
          returnKeyType="search"
          accessibilityLabel="저장물에서 검색"
        />
        {query.length > 0 && (
          <Pressable
            onPress={() => onQueryChange('')}
            style={styles.clearButton}
            accessibilityRole="button"
            accessibilityLabel="검색어 지우기"
            hitSlop={8}
          >
            <Ionicons name="close-circle" size={19} color={theme.muted} />
          </Pressable>
        )}
      </View>
      <View style={styles.toolsRow}>
        <Text style={styles.resultCount} accessibilityLiveRegion="polite">
          {query.trim() ? `검색 결과 ${resultCount}개` : `저장물 ${totalCount}개`}
        </Text>
        <Pressable
          style={styles.sortButton}
          onPress={() => onSortChange(NEXT_SORT[sort])}
          accessibilityRole="button"
          accessibilityLabel={`정렬: ${SORT_LABEL[sort]}. 눌러서 정렬 변경`}
          hitSlop={6}
        >
          <Ionicons name="swap-vertical-outline" size={15} color={theme.primary} />
          <Text style={styles.sortText}>{SORT_LABEL[sort]}</Text>
          <Ionicons name="chevron-down" size={13} color={theme.primary} />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginTop: 12, marginBottom: 10, gap: 8 },
  searchBox: {
    minHeight: 48,
    backgroundColor: theme.card,
    borderColor: theme.line,
    borderWidth: 1,
    borderRadius: 15,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 13,
    gap: 9,
  },
  input: { flex: 1, minHeight: 46, paddingVertical: 10, fontSize: 14, color: theme.text },
  clearButton: { width: 28, height: 34, alignItems: 'center', justifyContent: 'center' },
  toolsRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 38, gap: 10 },
  resultCount: { fontSize: 12, color: theme.muted, fontWeight: '600' },
  sortButton: { minHeight: 38, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5, borderRadius: 10, paddingHorizontal: 12, backgroundColor: theme.primarySoft },
  sortText: { fontSize: 12, color: theme.primary, fontWeight: '700' },
});

// SAVEON_LIBRARY_MICRO_POLISH_V1
