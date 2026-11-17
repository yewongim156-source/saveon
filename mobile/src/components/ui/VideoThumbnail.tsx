import React, { useEffect, useState } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { youtubeThumbnailUrl } from '../../lib/youtubeThumbnail';
import { getInstagramThumbnailUrl } from '../../lib/api';
import { ui } from '../../design/tokens';

type Props = {
  sourceUrl?: string;
  contentId?: string;
  thumbnailAvailable?: boolean;
  fallback?: string;
  variant?: 'card' | 'detail';
};

/** Public YouTube thumbnail, otherwise the existing local placeholder. */
export default function VideoThumbnail({ sourceUrl, contentId, thumbnailAvailable = false, fallback = '▶️', variant = 'card' }: Props) {
  const url = thumbnailAvailable && contentId
    ? getInstagramThumbnailUrl(contentId)
    : youtubeThumbnailUrl(sourceUrl);
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  useEffect(() => setFailedUrl(null), [url]);
  const showImage = Boolean(url && url !== failedUrl);
  return (
    <View
      style={[styles.wrapper, variant === 'detail' && styles.detail]}
      accessibilityLabel={showImage ? '영상 썸네일' : '영상 기본 이미지'}
      testID="saved-video-thumbnail"
    >
      {showImage && url ? (
        <Image
          source={{ uri: url }}
          style={styles.image}
          resizeMode="cover"
          onError={() => setFailedUrl(url)}
          accessibilityIgnoresInvertColors
        />
      ) : (
        <Text style={styles.fallback} accessibilityElementsHidden>{fallback}</Text>
      )}
      {showImage ? (
        <View style={styles.playBadge} pointerEvents="none">
          <Ionicons name="play" size={12} color="#FFFFFF" />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    width: 86, height: 78, borderRadius: ui.radius.md, overflow: 'hidden',
    backgroundColor: ui.color.brandSoft, alignItems: 'center', justifyContent: 'center',
  },
  detail: { width: 112, height: 72 },
  image: { width: '100%', height: '100%' },
  fallback: { fontSize: 29 },
  playBadge: {
    position: 'absolute', right: 6, bottom: 6,
    width: 22, height: 22, borderRadius: 11,
    backgroundColor: 'rgba(16,18,26,0.74)', alignItems: 'center', justifyContent: 'center',
  },
});
// SAVEON_INSTAGRAM_THUMBNAIL_V1
