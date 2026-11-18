import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { ContentItem } from '../types';
import VideoThumbnail from './ui/VideoThumbnail';
// save:on UI_POLISH_V4
import { theme } from '../theme';
import { displayContentCategories } from '../lib/categoryDisplay';
// # SAVEON_QUALITY_GUARD_V9

type Props = { item: ContentItem; onPress: () => void };

export default function ContentCard({ item, onPress }: Props) {
  const isPending = item.analysisStatus === 'PENDING';
  const isAnalyzing = item.analysisStatus === 'ANALYZING';
  const isProcessing = isPending || isAnalyzing;
  const isFailed = item.analysisStatus === 'FAILED';

  return (
    <Pressable style={styles.card} onPress={onPress}>
      <VideoThumbnail sourceUrl={item.sourceUrl} contentId={item.id} thumbnailAvailable={item.thumbnailAvailable} fallback={item.thumbnailEmoji} />
      <View style={styles.body}>
        <View style={styles.metaRow}>
          <View style={styles.metaLeft}>
            <Text style={styles.platform}>{item.platform}</Text>
            {(isProcessing || isFailed) && (
              <View style={[styles.statusBadge, isFailed && styles.statusBadgeError]}>
                {isFailed ? (
                  <Ionicons name="alert-circle-outline" size={12} color="#B84C4C" />
                ) : isPending ? (
                  <Ionicons name="time-outline" size={12} color={theme.primary} />
                ) : (
                  <ActivityIndicator size={11} color={theme.primary} />
                )}
                <Text style={[styles.statusBadgeText, isFailed && styles.statusBadgeTextError]}>
                  {isPending ? '대기 중' : isAnalyzing ? '정리 중' : '확인 필요'}
                </Text>
              </View>
            )}
          </View>
          <Text style={styles.date}>{item.savedAt}</Text>
        </View>
        <Text style={styles.title} numberOfLines={2}>{item.title}</Text>
        <Text style={styles.summary} numberOfLines={2}>
          {isPending
            ? '저장이 완료됐어요. 영상 분석을 기다리고 있어요.'
            : isAnalyzing
              ? '내용을 정리하고 있어요. 완료되면 요약이 표시돼요.'
              : isFailed
                ? '내용을 정리하지 못했어요. 저장물을 열어 확인해 주세요.'
                : item.summary}
        </Text>
        {!isProcessing && !isFailed && (
          <View style={styles.tags}>
            {displayContentCategories(item.category, item.title).slice(0, 3).map((tag) => (
              <View key={tag} style={styles.tag}><Text style={styles.tagText}>#{tag}</Text></View>
            ))}
          </View>
        )}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  /* Progress UI v2 status badge */
  metaLeft: { flexDirection: 'row', alignItems: 'center', gap: 7, flexShrink: 1 },
  statusBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 7, paddingVertical: 4, borderRadius: 999,
    backgroundColor: theme.primarySoft,
  },
  statusBadgeError: { backgroundColor: '#FFF2F0' },
  statusBadgeText: { color: theme.primary, fontSize: 11, fontWeight: '700' },
  statusBadgeTextError: { color: '#B84C4C' },
  card: { flexDirection: 'row', gap: 10, backgroundColor: theme.card, borderRadius: 18, padding: 12, borderWidth: 1, borderColor: theme.line, marginBottom: 12 },
  emojiBox: { width: 64, height: 64, borderRadius: 16, backgroundColor: theme.primarySoft, alignItems: 'center', justifyContent: 'center' },
  emoji: { fontSize: 31 },
  body: { flex: 1 },
  metaRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  platform: { fontSize: 12, fontWeight: '700', color: theme.primary },
  date: { fontSize: 11, color: theme.muted },
  title: { fontSize: 16, fontWeight: '800', color: theme.text, marginBottom: 5 },
  summary: { fontSize: 14, lineHeight: 20, color: '#515A69' },
  tags: { flexDirection: 'row', gap: 6, marginTop: 9, flexWrap: 'wrap' },
  tag: { backgroundColor: theme.bg, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 4 },
  tagText: { fontSize: 12, color: '#515A69' }
});
// SAVEON_INSTAGRAM_THUMBNAIL_V1
