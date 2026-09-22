import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { ContentItem } from '../types';
import { theme } from '../theme';

type Props = { item: ContentItem; onPress: () => void };

export default function ContentCard({ item, onPress }: Props) {
  return (
    <Pressable style={styles.card} onPress={onPress}>
      <View style={styles.emojiBox}><Text style={styles.emoji}>{item.thumbnailEmoji}</Text></View>
      <View style={styles.body}>
        <View style={styles.metaRow}>
          <Text style={styles.platform}>{item.platform}</Text>
          <Text style={styles.date}>{item.savedAt}</Text>
        </View>
        <Text style={styles.title} numberOfLines={1}>{item.title}</Text>
        <Text style={styles.summary} numberOfLines={2}>{item.summary}</Text>
        <View style={styles.tags}>
          {item.category.slice(0, 3).map((tag) => (
            <View key={tag} style={styles.tag}><Text style={styles.tagText}>#{tag}</Text></View>
          ))}
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { flexDirection: 'row', gap: 12, backgroundColor: theme.card, borderRadius: 18, padding: 14, borderWidth: 1, borderColor: theme.line, marginBottom: 12 },
  emojiBox: { width: 64, height: 64, borderRadius: 16, backgroundColor: theme.primarySoft, alignItems: 'center', justifyContent: 'center' },
  emoji: { fontSize: 31 },
  body: { flex: 1 },
  metaRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  platform: { fontSize: 11, fontWeight: '700', color: theme.primary },
  date: { fontSize: 11, color: theme.muted },
  title: { fontSize: 16, fontWeight: '800', color: theme.text, marginBottom: 5 },
  summary: { fontSize: 13, lineHeight: 18, color: theme.muted },
  tags: { flexDirection: 'row', gap: 6, marginTop: 9, flexWrap: 'wrap' },
  tag: { backgroundColor: theme.bg, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 4 },
  tagText: { fontSize: 11, color: theme.muted }
});
