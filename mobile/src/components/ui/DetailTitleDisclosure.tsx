import React, { useState } from 'react';
import {
  Pressable,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type TextStyle,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '../../theme';

type Props = {
  title: string;
  titleStyle: StyleProp<TextStyle>;
  maxLines?: number;
};

/** Presentation-only title collapse; never changes the saved title. */
export default function DetailTitleDisclosure({
  title,
  titleStyle,
  maxLines = 3,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const [measuredLines, setMeasuredLines] = useState<number | null>(null);
  const needsToggle = measuredLines === null
    ? title.trim().length > 44
    : measuredLines > maxLines;

  return (
    <View style={styles.container} testID="detail-title-disclosure">
      {/* The invisible full text is laid out at the same width to detect overflow. */}
      <View
        style={styles.measureLayer}
        pointerEvents="none"
        accessible={false}
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      >
        <Text
          style={titleStyle}
          onTextLayout={(event) => {
            const count = event.nativeEvent.lines.length;
            setMeasuredLines((previous) => previous === count ? previous : count);
          }}
        >
          {title}
        </Text>
      </View>

      <Text
        style={titleStyle}
        numberOfLines={expanded ? undefined : maxLines}
        ellipsizeMode="tail"
        accessibilityLabel={title}
      >
        {title}
      </Text>

      {needsToggle && (
        <Pressable
          style={styles.toggle}
          onPress={() => setExpanded((value) => !value)}
          accessibilityRole="button"
          accessibilityLabel={expanded ? '제목 접기' : '제목 전체 보기'}
          accessibilityState={{ expanded }}
          hitSlop={8}
          testID="detail-title-toggle"
        >
          <Text style={styles.toggleLabel}>
            {expanded ? '제목 접기' : '제목 더 보기'}
          </Text>
          <Ionicons
            name={expanded ? 'chevron-up' : 'chevron-down'}
            size={15}
            color={theme.primary}
          />
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { position: 'relative', width: '100%' },
  measureLayer: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: 0,
    opacity: 0,
  },
  toggle: {
    minHeight: 34,
    alignSelf: 'flex-end',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 6,
    marginTop: -4,
    marginBottom: 6,
  },
  toggleLabel: { fontSize: 12, fontWeight: '800', color: theme.primary },
});
