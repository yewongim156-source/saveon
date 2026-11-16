import React, { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '../../theme';

type Props = {
  text?: string | null;
};

/** Compact saved-video summary; local display state only. */
export default function DetailSummaryText({ text }: Props) {
  const [expanded, setExpanded] = useState(false);
  const content = (text ?? '').trim();
  const canExpand = content.length > 150 || content.split('\n').length > 4;

  useEffect(() => {
    setExpanded(false);
  }, [content]);

  return (
    <View style={styles.wrap}>
      <Text
        style={styles.summary}
        numberOfLines={canExpand && !expanded ? 4 : undefined}
        accessibilityRole="text"
      >
        {content || '아직 요약된 내용이 없어요.'}
      </Text>
      {canExpand ? (
        <Pressable
          style={styles.toggle}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel={expanded ? '요약 접기' : '요약 더 보기'}
          accessibilityState={{ expanded }}
          onPress={() => setExpanded((previous) => !previous)}
        >
          <Text style={styles.toggleText}>{expanded ? '접기' : '더 보기'}</Text>
          <Ionicons
            name={expanded ? 'chevron-up' : 'chevron-down'}
            color={theme.primary}
            size={15}
          />
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginTop: 12,
  },
  summary: {
    color: theme.text,
    fontSize: 14,
    lineHeight: 23,
  },
  toggle: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginTop: 10,
    minHeight: 36,
    paddingHorizontal: 2,
  },
  toggleText: {
    color: theme.primary,
    fontWeight: '800',
    fontSize: 12,
  },
});
