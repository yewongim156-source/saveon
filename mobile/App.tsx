import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Linking,
  Pressable,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { Ionicons } from '@expo/vector-icons';

import BottomNav from './src/components/BottomNav';
import ContentCard from './src/components/ContentCard';
import { theme } from './src/theme';
import { ContentItem, Screen } from './src/types';
import {
  ApiContent,
  createContent,
  getContents,
  uploadVideo,
} from './src/lib/api';

function inferApiPlatform(url: string): ApiContent['platform'] {
  if (url.includes('instagram.com')) return 'INSTAGRAM';
  if (url.includes('youtube.com') || url.includes('youtu.be')) return 'YOUTUBE';
  return 'WEB';
}

function toContentItem(api: ApiContent): ContentItem {
  const platformMap = {
    INSTAGRAM: 'Instagram',
    YOUTUBE: 'YouTube',
    WEB: 'Web',
    UPLOAD: 'Upload',
  } as const;

  const emojiMap = {
    INSTAGRAM: '📱',
    YOUTUBE: '▶️',
    WEB: '🔗',
    UPLOAD: '🎬',
  } as const;

  let statusText = '분석대기';
  if (api.status === 'ANALYZING') statusText = '분석중';
  if (api.status === 'COMPLETED') statusText = '분석완료';
  if (api.status === 'FAILED') statusText = '분석실패';

  return {
    id: String(api.id),
    platform: platformMap[api.platform],
    title: api.title ?? '분석 대기 중',
    summary:
      api.summary ??
      '콘텐츠가 저장되었습니다. AI 분석을 기다리고 있어요.',
    sourceUrl: api.sourceUrl,
    category: api.categories?.length ? api.categories : [statusText],
    keywords: api.keywords ?? [],
    entities: api.entities ?? [],
    savedAt: api.createdAt?.slice(0, 10) ?? '',
    thumbnailEmoji: emojiMap[api.platform],
  };
}

export default function App() {
  const [screen, setScreen] = useState<Screen>({ name: 'home' });
  const [contents, setContents] = useState<ContentItem[]>([]);
  const [url, setUrl] = useState('');
  const [query, setQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('전체');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    loadContents();
  }, []);

  async function loadContents() {
    console.log('🔄 콘텐츠 조회 시작');

    try {
      setLoading(true);
      const data = await getContents();

      console.log('✅ 서버 응답:', data);

      setContents(
        data
          .map(toContentItem)
          .reverse(),
      );

      console.log('✅ 콘텐츠 새로고침 완료');
    } catch (error) {
      console.error('❌ 콘텐츠 조회 오류:', error);

      Alert.alert(
        '서버 연결 실패',
        'Spring Boot 서버가 실행 중인지 확인해줘.',
      );
    } finally {
      setLoading(false);
    }
  }

  const categories = useMemo(() => {
    const all = Array.from(
      new Set(contents.flatMap((item) => item.category)),
    );

    return ['전체', ...all];
  }, [contents]);

  const repeatedEntities = useMemo(() => {
    const count = new Map<string, number>();

    contents.forEach((item) => {
      item.entities.forEach((entity) => {
        count.set(entity, (count.get(entity) ?? 0) + 1);
      });
    });

    return [...count.entries()]
      .filter(([, n]) => n > 1)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4);
  }, [contents]);

  const filteredContents = useMemo(() => {
    if (selectedCategory === '전체') return contents;

    return contents.filter((item) =>
      item.category.includes(selectedCategory),
    );
  }, [contents, selectedCategory]);

  const searchResults = useMemo(() => {
    const q = query.trim().toLowerCase();

    if (!q) return contents;

    return contents.filter((item) =>
      [
        item.title,
        item.summary,
        ...item.category,
        ...item.keywords,
        ...item.entities,
      ]
        .join(' ')
        .toLowerCase()
        .includes(q),
    );
  }, [contents, query]);

  const detailItem =
    screen.name === 'detail'
      ? contents.find((item) => item.id === screen.itemId)
      : undefined;

  function goTab(
    name: 'home' | 'save' | 'library' | 'search',
  ) {
    setScreen({ name });
  }

  async function saveUrl() {
    const trimmed = url.trim();

    if (!trimmed.startsWith('http')) {
      Alert.alert(
        'URL을 확인해줘',
        'https:// 로 시작하는 URL을 입력해줘.',
      );
      return;
    }

    try {
      setLoading(true);

      const saved = await createContent(
        trimmed,
        inferApiPlatform(trimmed),
      );

      setContents((prev) => [
        toContentItem(saved),
        ...prev,
      ]);

      setUrl('');

      Alert.alert(
        '저장 완료',
        '콘텐츠 저장 및 분석이 완료됐어.',
      );
    } catch (error) {
      console.error('❌ 콘텐츠 저장 오류:', error);

      Alert.alert(
        '저장 실패',
        'Spring Boot 또는 FastAPI 서버 연결을 확인해줘.',
      );
    } finally {
      setLoading(false);
    }
  }

  async function pickVideoFromGallery() {
    try {
      const permission =
        await ImagePicker.requestMediaLibraryPermissionsAsync();

      if (!permission.granted) {
        Alert.alert(
          '사진 접근 권한 필요',
          '영상 선택을 위해 사진 보관함 접근 권한을 허용해줘.',
        );
        return;
      }

      const result =
        await ImagePicker.launchImageLibraryAsync({
          mediaTypes: ['videos'],
          allowsEditing: false,
          quality: 1,
        });

      if (result.canceled) {
        return;
      }

      const asset = result.assets[0];

      const fileName =
        `saveon-${Date.now()}.mp4`;

      const mimeType =
        asset.mimeType ??
        'video/mp4';

      console.log(
        '🎬 선택한 영상:',
        fileName,
      );

      setUploading(true);

      const analyzed =
        await uploadVideo({
          uri: asset.uri,
          name: fileName,
          type: mimeType,
        });

      console.log(
        '✅ 영상 분석 결과:',
        analyzed,
      );

      setContents(
        (prev) => [
          toContentItem(analyzed),
          ...prev,
        ],
      );

      Alert.alert(
        analyzed.status === 'COMPLETED'
          ? '영상 분석 완료'
          : '영상 분석 확인 필요',
        analyzed.status === 'COMPLETED'
          ? 'STT · OCR · Vision 분석 결과를 저장했어.'
          : 'FastAPI 로그를 확인해줘.',
      );
    } catch (error) {
      console.error(
        '❌ 영상 업로드 오류:',
        error,
      );

      Alert.alert(
        '영상 업로드 실패',
        'Spring Boot와 FastAPI 터미널 로그를 확인해줘.',
      );
    } finally {
      setUploading(false);
    }
  }

  function renderHome() {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <View style={styles.header}>
          <View>
            <Text style={styles.eyebrow}>
              MY SMART LIBRARY
            </Text>

            <Text style={styles.h1}>
              저장한 콘텐츠를{'\n'}
              다시 쓸 수 있게.
            </Text>
          </View>

          <View style={styles.logoBubble}>
            <Text style={styles.logoText}>CM</Text>
          </View>
        </View>

        <View style={styles.hero}>
          <Text style={styles.heroLabel}>
            저장된 콘텐츠
          </Text>

          <Text style={styles.heroNumber}>
            {contents.length}
          </Text>

          <Text style={styles.heroSub}>
            {loading
              ? '서버에서 콘텐츠를 불러오는 중...'
              : 'AI가 콘텐츠를 분석하고 정리했어요.'}
          </Text>

          <Pressable
            style={styles.primaryButton}
            onPress={() => goTab('save')}
          >
            <Ionicons
              name="add"
              size={19}
              color="#fff"
            />
            <Text style={styles.primaryButtonText}>
              새 콘텐츠 저장
            </Text>
          </Pressable>
        </View>

        <Text style={styles.sectionTitle}>
          반복해서 등장한 정보
        </Text>

        <View style={styles.entityGrid}>
          {repeatedEntities.length > 0 ? (
            repeatedEntities.map(([entity, count]) => (
              <View
                key={entity}
                style={styles.entityCard}
              >
                <Text style={styles.entityName}>
                  {entity}
                </Text>
                <Text style={styles.entityCount}>
                  {count}개 콘텐츠
                </Text>
              </View>
            ))
          ) : (
            <View style={styles.emptyBox}>
              <Text style={styles.emptyText}>
                동일한 장소·상품·주제가 여러 콘텐츠에서
                등장하면 여기에 표시돼요.
              </Text>
            </View>
          )}
        </View>

        <View style={styles.rowBetween}>
          <Text style={styles.sectionTitle}>
            최근 저장
          </Text>

          <Pressable onPress={() => goTab('library')}>
            <Text style={styles.linkText}>
              전체 보기
            </Text>
          </Pressable>
        </View>

        {contents.slice(0, 3).map((item) => (
          <ContentCard
            key={item.id}
            item={item}
            onPress={() =>
              setScreen({
                name: 'detail',
                itemId: item.id,
              })
            }
          />
        ))}
      </ScrollView>
    );
  }

  function renderSave() {
    return (
      <ScrollView
        contentContainerStyle={styles.page}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.eyebrow}>
          SAVE CONTENT
        </Text>

        <Text style={styles.h1}>
          콘텐츠 저장
        </Text>

        <Text style={styles.bodyText}>
          URL을 저장하거나 영상을 직접 업로드해서
          실제 콘텐츠 분석을 실행할 수 있어.
        </Text>

        <View style={styles.panel}>
          <View style={styles.inputLabelRow}>
            <Ionicons
              name="link-outline"
              size={18}
              color={theme.primary}
            />

            <Text style={styles.inputLabel}>
              URL로 저장
            </Text>
          </View>

          <TextInput
            value={url}
            onChangeText={setUrl}
            placeholder="https://www.instagram.com/reel/..."
            placeholderTextColor="#A7ABB4"
            autoCapitalize="none"
            autoCorrect={false}
            style={styles.input}
          />

          <Pressable
            style={styles.primaryButton}
            onPress={saveUrl}
            disabled={loading || uploading}
          >
            <Ionicons
              name="sparkles-outline"
              size={18}
              color="#fff"
            />

            <Text style={styles.primaryButtonText}>
              {loading ? '처리 중...' : '저장'}
            </Text>
          </Pressable>
        </View>

        <View style={styles.panel}>
          <View style={styles.inputLabelRow}>
            <Ionicons
              name="videocam-outline"
              size={18}
              color={theme.accent}
            />

            <Text style={styles.inputLabel}>
              갤러리에서 영상 선택
            </Text>
          </View>

          <Text style={styles.bodyText}>
            영상 음성은 STT, 화면 글자는 OCR,
            장면은 Vision 모델로 분석해.
          </Text>

          <Pressable
            style={[
              styles.secondaryButton,
              uploading && styles.disabledButton,
            ]}
            onPress={pickVideoFromGallery}
            disabled={uploading || loading}
          >
            <Ionicons
              name={
                uploading
                  ? 'hourglass-outline'
                  : 'cloud-upload-outline'
              }
              size={19}
              color={theme.text}
            />

            <Text style={styles.secondaryButtonText}>
              {uploading
                ? '영상 분석 중...'
                : '갤러리 열기'}
            </Text>
          </Pressable>

          {uploading && (
            <Text style={styles.processingText}>
              첫 실행은 Whisper/OCR/Vision 모델을
              내려받아서 수 분 걸릴 수 있어.
            </Text>
          )}
        </View>
      </ScrollView>
    );
  }

  function renderLibrary() {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <Text style={styles.eyebrow}>LIBRARY</Text>
        <Text style={styles.h1}>보관함</Text>

        <Pressable
          style={[
            styles.refreshButton,
            loading && styles.disabledButton,
          ]}
          disabled={loading}
          onPress={() => {
            console.log('👆 새로고침 버튼 눌림');
            loadContents();
          }}
        >
          <Ionicons
            name={
              loading
                ? 'hourglass-outline'
                : 'refresh-outline'
            }
            size={17}
            color={theme.primary}
          />

          <Text style={styles.refreshText}>
            {loading
              ? '새로고침 중...'
              : '서버에서 새로고침'}
          </Text>
        </Pressable>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipRow}
        >
          {categories.map((cat) => {
            const selected =
              selectedCategory === cat;

            return (
              <Pressable
                key={cat}
                style={[
                  styles.chip,
                  selected && styles.chipSelected,
                ]}
                onPress={() =>
                  setSelectedCategory(cat)
                }
              >
                <Text
                  style={[
                    styles.chipText,
                    selected &&
                      styles.chipTextSelected,
                  ]}
                >
                  {cat}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>

        {filteredContents.length === 0 ? (
          <View style={styles.emptyBox}>
            <Text style={styles.emptyText}>
              저장된 콘텐츠가 없어요.
            </Text>
          </View>
        ) : (
          filteredContents.map((item) => (
            <ContentCard
              key={item.id}
              item={item}
              onPress={() =>
                setScreen({
                  name: 'detail',
                  itemId: item.id,
                })
              }
            />
          ))
        )}
      </ScrollView>
    );
  }

  function renderSearch() {
    return (
      <ScrollView
        contentContainerStyle={styles.page}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.eyebrow}>
          SEARCH
        </Text>
        <Text style={styles.h1}>
          검색
        </Text>

        <Text style={styles.bodyText}>
          현재는 제목·요약·카테고리·키워드·엔티티를
          기준으로 검색해.
        </Text>

        <View style={styles.searchBox}>
          <Ionicons
            name="search-outline"
            size={20}
            color={theme.muted}
          />

          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="예: 카페, 여행, 메이크업"
            placeholderTextColor="#A7ABB4"
            style={styles.searchInput}
          />
        </View>

        <Text style={styles.resultText}>
          {searchResults.length}개 결과
        </Text>

        {searchResults.map((item) => (
          <ContentCard
            key={item.id}
            item={item}
            onPress={() =>
              setScreen({
                name: 'detail',
                itemId: item.id,
              })
            }
          />
        ))}
      </ScrollView>
    );
  }

  function renderDetail() {
    if (!detailItem) return null;

    const canOpenSource =
      detailItem.sourceUrl?.startsWith('http');

    return (
      <ScrollView contentContainerStyle={styles.page}>
        <Pressable
          style={styles.backButton}
          onPress={() => goTab('library')}
        >
          <Ionicons
            name="chevron-back"
            size={22}
            color={theme.text}
          />
          <Text style={styles.backText}>
            보관함
          </Text>
        </Pressable>

        <View style={styles.detailHero}>
          <Text style={styles.detailEmoji}>
            {detailItem.thumbnailEmoji}
          </Text>

          <Text style={styles.platformBadge}>
            {detailItem.platform}
          </Text>

          <Text style={styles.detailTitle}>
            {detailItem.title}
          </Text>

          <Text style={styles.bodyText}>
            {detailItem.summary}
          </Text>
        </View>

        <Text style={styles.sectionTitle}>
          카테고리
        </Text>

        <View style={styles.wrapRow}>
          {detailItem.category.map((tag) => (
            <View
              key={tag}
              style={styles.chip}
            >
              <Text style={styles.chipText}>
                #{tag}
              </Text>
            </View>
          ))}
        </View>

        <Text style={styles.sectionTitle}>
          키워드
        </Text>

        <View style={styles.wrapRow}>
          {detailItem.keywords.length > 0 ? (
            detailItem.keywords.map((keyword) => (
              <View
                key={keyword}
                style={styles.keywordPill}
              >
                <Text style={styles.keywordText}>
                  {keyword}
                </Text>
              </View>
            ))
          ) : (
            <Text style={styles.bodyText}>
              아직 키워드가 없어.
            </Text>
          )}
        </View>

        <Text style={styles.sectionTitle}>
          추출된 엔티티
        </Text>

        <View style={styles.wrapRow}>
          {detailItem.entities.length > 0 ? (
            detailItem.entities.map((entity) => (
              <View
                key={entity}
                style={styles.entityPill}
              >
                <Text style={styles.entityPillText}>
                  {entity}
                </Text>
              </View>
            ))
          ) : (
            <Text style={styles.bodyText}>
              아직 추출된 엔티티가 없어.
            </Text>
          )}
        </View>

        {canOpenSource && (
          <Pressable
            style={styles.secondaryButton}
            onPress={() =>
              Linking.openURL(
                detailItem.sourceUrl!,
              )
            }
          >
            <Ionicons
              name="open-outline"
              size={18}
              color={theme.text}
            />
            <Text style={styles.secondaryButtonText}>
              원본 콘텐츠 열기
            </Text>
          </Pressable>
        )}
      </ScrollView>
    );
  }

  const activeTab =
    screen.name === 'detail'
      ? 'library'
      : screen.name;

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="dark-content" />

      <View style={styles.content}>
        {screen.name === 'home' && renderHome()}
        {screen.name === 'save' && renderSave()}
        {screen.name === 'library' && renderLibrary()}
        {screen.name === 'search' && renderSearch()}
        {screen.name === 'detail' && renderDetail()}
      </View>

      <BottomNav
        active={activeTab}
        onChange={(tab) => goTab(tab)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: theme.bg,
  },
  content: {
    flex: 1,
  },
  page: {
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 30,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  eyebrow: {
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 1.2,
    color: theme.primary,
    marginBottom: 8,
  },
  h1: {
    fontSize: 32,
    lineHeight: 39,
    fontWeight: '900',
    color: theme.text,
    marginBottom: 12,
  },
  bodyText: {
    color: theme.muted,
    fontSize: 14,
    lineHeight: 21,
  },
  logoBubble: {
    width: 44,
    height: 44,
    borderRadius: 14,
    backgroundColor: theme.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoText: {
    color: '#fff',
    fontWeight: '900',
  },
  hero: {
    marginTop: 20,
    marginBottom: 28,
    padding: 22,
    backgroundColor: theme.text,
    borderRadius: 24,
  },
  heroLabel: {
    color: '#C7CBD3',
    fontSize: 13,
  },
  heroNumber: {
    color: '#fff',
    fontSize: 48,
    fontWeight: '900',
    marginTop: 2,
  },
  heroSub: {
    color: '#C7CBD3',
    marginBottom: 18,
  },
  primaryButton: {
    minHeight: 48,
    borderRadius: 14,
    backgroundColor: theme.primary,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
    paddingHorizontal: 16,
    marginTop: 12,
  },
  primaryButtonText: {
    color: '#fff',
    fontWeight: '800',
    fontSize: 14,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '900',
    color: theme.text,
    marginTop: 20,
    marginBottom: 12,
  },
  entityGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  entityCard: {
    width: '48%',
    backgroundColor: theme.card,
    borderRadius: 16,
    padding: 15,
    borderWidth: 1,
    borderColor: theme.line,
  },
  entityName: {
    fontSize: 15,
    fontWeight: '800',
    color: theme.text,
  },
  entityCount: {
    marginTop: 5,
    fontSize: 12,
    color: theme.muted,
  },
  emptyBox: {
    backgroundColor: theme.card,
    padding: 16,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: theme.line,
  },
  emptyText: {
    color: theme.muted,
    lineHeight: 19,
  },
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  linkText: {
    color: theme.primary,
    fontWeight: '700',
    marginTop: 10,
  },
  panel: {
    backgroundColor: theme.card,
    borderRadius: 20,
    padding: 18,
    borderWidth: 1,
    borderColor: theme.line,
    marginTop: 16,
  },
  inputLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    marginBottom: 12,
  },
  inputLabel: {
    fontSize: 16,
    fontWeight: '800',
    color: theme.text,
  },
  input: {
    minHeight: 50,
    borderWidth: 1,
    borderColor: theme.line,
    borderRadius: 14,
    paddingHorizontal: 14,
    color: theme.text,
    backgroundColor: theme.bg,
  },
  secondaryButton: {
    minHeight: 48,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: theme.line,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
    paddingHorizontal: 16,
    marginTop: 14,
    backgroundColor: '#fff',
  },
  secondaryButtonText: {
    color: theme.text,
    fontWeight: '800',
  },
  disabledButton: {
    opacity: 0.6,
  },
  processingText: {
    color: theme.muted,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 10,
  },
  chipRow: {
    gap: 8,
    paddingBottom: 14,
  },
  chip: {
    paddingHorizontal: 13,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: theme.card,
    borderWidth: 1,
    borderColor: theme.line,
  },
  chipSelected: {
    backgroundColor: theme.primary,
    borderColor: theme.primary,
  },
  chipText: {
    fontSize: 12,
    fontWeight: '700',
    color: theme.muted,
  },
  chipTextSelected: {
    color: '#fff',
  },
  searchBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: theme.card,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: theme.line,
    paddingHorizontal: 14,
    marginTop: 16,
  },
  searchInput: {
    flex: 1,
    minHeight: 50,
    color: theme.text,
  },
  resultText: {
    color: theme.muted,
    fontSize: 12,
    marginTop: 14,
    marginBottom: 10,
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    marginBottom: 14,
  },
  backText: {
    color: theme.text,
    fontWeight: '700',
  },
  detailHero: {
    backgroundColor: theme.card,
    borderRadius: 22,
    padding: 20,
    borderWidth: 1,
    borderColor: theme.line,
  },
  detailEmoji: {
    fontSize: 44,
    marginBottom: 14,
  },
  platformBadge: {
    color: theme.primary,
    fontSize: 12,
    fontWeight: '800',
    marginBottom: 7,
  },
  detailTitle: {
    color: theme.text,
    fontSize: 25,
    lineHeight: 31,
    fontWeight: '900',
    marginBottom: 10,
  },
  wrapRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  keywordPill: {
    backgroundColor: theme.primarySoft,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
  },
  keywordText: {
    color: theme.primary,
    fontWeight: '700',
    fontSize: 12,
  },
  entityPill: {
    backgroundColor: '#ECF8F2',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
  },
  entityPillText: {
    color: theme.accent,
    fontWeight: '800',
    fontSize: 12,
  },
  refreshButton: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    borderRadius: 12,
    backgroundColor: theme.primarySoft,
    marginBottom: 16,
  },
  refreshText: {
    color: theme.primary,
    fontWeight: '800',
    fontSize: 13,
  },
});
