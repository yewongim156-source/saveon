import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import {
  close,
  InitialProps,
} from 'expo-share-extension';

import {
  ApiContent,
  createContent,
} from './src/lib/api';

function extractUrl(
  url?: string,
  text?: string,
): string | null {
  if (url?.startsWith('http')) {
    return url.trim();
  }

  const match =
    text?.match(/https?:\/\/[^\s]+/i);

  if (!match) return null;

  return match[0]
    .replace(/[),.!?\]}]+$/g, '')
    .trim();
}

function inferPlatform(
  url: string,
): ApiContent['platform'] {
  const lower = url.toLowerCase();

  if (lower.includes('instagram.com')) {
    return 'INSTAGRAM';
  }

  if (
    lower.includes('youtube.com') ||
    lower.includes('youtu.be')
  ) {
    return 'YOUTUBE';
  }

  return 'WEB';
}

type SaveState =
  | 'saving'
  | 'success'
  | 'error';

export default function ShareExtension(
  props: InitialProps,
) {
  const sharedUrl = useMemo(
    () => extractUrl(
      props.url,
      props.text,
    ),
    [props.url, props.text],
  );

  const startedRef = useRef(false);

  const [state, setState] =
    useState<SaveState>('saving');

  const [message, setMessage] =
    useState('공유한 링크를 저장하고 있어요.');

  async function saveSharedContent() {
    if (!sharedUrl) {
      setState('error');
      setMessage(
        '공유 내용에서 URL을 찾지 못했어요.',
      );
      return;
    }

    setState('saving');
    setMessage(
      '공유한 링크를 저장하고 있어요.',
    );

    try {
      const saved = await createContent(
        sharedUrl,
        inferPlatform(sharedUrl),
      );

      console.log(
        '✅ Share Extension 저장 완료:',
        saved.id,
        saved.status,
      );

      setState('success');
      setMessage(
        '저장 완료! AI 분석은 뒤에서 계속 진행돼요.',
      );

      setTimeout(() => {
        close();
      }, 700);

    } catch (error) {
      console.error(
        '❌ Share Extension 저장 실패:',
        error,
      );

      setState('error');
      setMessage(
        '저장하지 못했어요. 서버 연결을 확인해줘.',
      );
    }
  }

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    saveSharedContent();
  }, []);

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.card}>
        <Text
          allowFontScaling={false}
          style={styles.brand}
        >
          save:on
        </Text>

        <Text
          allowFontScaling={false}
          style={styles.title}
        >
          {state === 'saving'
            ? '콘텐츠 저장 중'
            : state === 'success'
              ? '저장 완료'
              : '저장 실패'}
        </Text>

        <Text
          allowFontScaling={false}
          style={styles.message}
        >
          {message}
        </Text>

        {sharedUrl && (
          <Text
            allowFontScaling={false}
            numberOfLines={2}
            style={styles.url}
          >
            {sharedUrl}
          </Text>
        )}

        {state === 'saving' && (
          <ActivityIndicator
            size="small"
            color="#6750A4"
            style={styles.indicator}
          />
        )}

        {state === 'error' && (
          <View style={styles.actions}>
            <Pressable
              style={styles.primaryButton}
              onPress={saveSharedContent}
            >
              <Text
                allowFontScaling={false}
                style={styles.primaryButtonText}
              >
                다시 시도
              </Text>
            </Pressable>

            <Pressable
              style={styles.secondaryButton}
              onPress={close}
            >
              <Text
                allowFontScaling={false}
                style={styles.secondaryButtonText}
              >
                닫기
              </Text>
            </Pressable>
          </View>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: '#F6F5FA',
  },
  card: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 28,
    paddingBottom: 20,
  },
  brand: {
    color: '#6750A4',
    fontSize: 14,
    fontWeight: '800',
    marginBottom: 18,
  },
  title: {
    color: '#1F1F24',
    fontSize: 24,
    fontWeight: '900',
    marginBottom: 10,
  },
  message: {
    color: '#696A73',
    fontSize: 15,
    lineHeight: 22,
  },
  url: {
    marginTop: 16,
    color: '#8A8B94',
    fontSize: 12,
    lineHeight: 17,
  },
  indicator: {
    marginTop: 22,
    alignSelf: 'flex-start',
  },
  actions: {
    marginTop: 22,
    gap: 10,
  },
  primaryButton: {
    minHeight: 46,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#6750A4',
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '800',
  },
  secondaryButton: {
    minHeight: 46,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#DFDDE6',
    backgroundColor: '#FFFFFF',
  },
  secondaryButtonText: {
    color: '#1F1F24',
    fontSize: 14,
    fontWeight: '800',
  },
});
