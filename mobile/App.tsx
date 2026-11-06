import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
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
import * as Calendar from 'expo-calendar';
import { Ionicons } from '@expo/vector-icons';

import BottomNav from './src/components/BottomNav';
import ContentCard from './src/components/ContentCard';
import { theme } from './src/theme';
import { ContentItem, Screen } from './src/types';
import {
  ApiContent,
  ApiContentAction,
  ApiContentActionPlan,
  ApiContentBundle,
  ApiContentConnection,
  ApiContentQuality,
  ApiEntityCorrection,
  ApiKnowledgeAnswer,
  ApiInterestTimeline,
  ApiSmartReminder,
  ApiSmartCollection,
  ApiCollectionComparison,
  ApiContentConflict,
  askSavedKnowledge,
  compareSmartCollection,
  correctContent,
  createContent,
  getConnectedContents,
  getContent,
  getContentBundle,
  getContentQuality,
  getContentConnections,
  getContents,
  getInterestTimeline,
  getSmartReminders,
  getSmartCollections,
  getContentConflicts,
  logActionCorrection,
  planContentActions,
  planSingleContentActions,
  reanalyzeContent,
  searchContents,
  semanticSearchContents,
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

  let statusText = '정리 대기';
  if (api.status === 'ANALYZING') statusText = '정리 중';
  if (api.status === 'COMPLETED') statusText = '정리 완료';
  if (api.status === 'FAILED') statusText = '다시 시도 필요';

  const fallbackTitle =
    api.status === 'FAILED'
      ? '내용을 정리하지 못했어요'
      : api.status === 'ANALYZING'
        ? '저장한 내용을 정리하고 있어요'
        : '저장한 콘텐츠';

  const fallbackSummary =
    api.status === 'FAILED'
      ? '원본 콘텐츠를 불러오지 못했어요. 다시 시도할 수 있어요.'
      : '저장은 끝났어요. 앱을 나가도 정리는 계속 진행돼요.';

  return {
    id: String(api.id),
    platform: platformMap[api.platform],
    title: api.title ?? fallbackTitle,
    summary: api.summary ?? fallbackSummary,
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
  const [connections, setConnections] = useState<
    ApiContentConnection[]
  >([]);
  const [connectionsLoading, setConnectionsLoading] = useState(false);
  const [smartCollections, setSmartCollections] = useState<
    ApiSmartCollection[]
  >([]);
  const [smartCollectionsLoading, setSmartCollectionsLoading] =
    useState(false);
  const [contentConflicts, setContentConflicts] = useState<
    ApiContentConflict[]
  >([]);
  const [contentConflictsLoading, setContentConflictsLoading] =
    useState(false);
  const [interestTimeline, setInterestTimeline] =
    useState<ApiInterestTimeline | null>(null);
  const [interestTimelineLoading, setInterestTimelineLoading] =
    useState(false);
  const [smartReminders, setSmartReminders] = useState<
    ApiSmartReminder[]
  >([]);
  const [smartRemindersLoading, setSmartRemindersLoading] =
    useState(false);
  const [activeSmartCollection, setActiveSmartCollection] =
    useState<ApiSmartCollection | null>(null);
  const [collectionComparison, setCollectionComparison] =
    useState<ApiCollectionComparison | null>(null);
  const [collectionComparisonLoading, setCollectionComparisonLoading] =
    useState(false);
  const [collectionComparisonError, setCollectionComparisonError] =
    useState<string | null>(null);
  const [connectionFilter, setConnectionFilter] = useState<
    ApiContentConnection | null
  >(null);
  const [contentBundle, setContentBundle] = useState<
    ApiContentBundle | null
  >(null);
  const [bundleLoading, setBundleLoading] = useState(false);
  const [bundleError, setBundleError] = useState<string | null>(null);
  const [actionPlan, setActionPlan] = useState<
    ApiContentActionPlan | null
  >(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [detailRawContent, setDetailRawContent] =
    useState<ApiContent | null>(null);
  const [contentQuality, setContentQuality] =
    useState<ApiContentQuality | null>(null);
  const [qualityLoading, setQualityLoading] = useState(false);
  const [analysisEditing, setAnalysisEditing] = useState(false);
  const [correctionFocus, setCorrectionFocus] = useState<
    'summary' | 'info' | null
  >(null);
  const [correctionSaving, setCorrectionSaving] = useState(false);
  const [correctionDraft, setCorrectionDraft] = useState<{
    title: string;
    summary: string;
    categories: string[];
    keywords: string;
    entityDetails: ApiEntityCorrection[];
  } | null>(null);

  const [activeChecklist, setActiveChecklist] = useState<{
    key: string;
    title: string;
    items: string[];
    checked: boolean[];
  } | null>(null);
  const [url, setUrl] = useState('');
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<ContentItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchMode, setSearchMode] = useState<'search' | 'ask'>(
    'search',
  );
  const [knowledgeQuestion, setKnowledgeQuestion] = useState('');
  const [knowledgeAnswer, setKnowledgeAnswer] =
    useState<ApiKnowledgeAnswer | null>(null);
  const [knowledgeLoading, setKnowledgeLoading] = useState(false);
  const [knowledgeError, setKnowledgeError] = useState<string | null>(null);
  const [detailReturnTab, setDetailReturnTab] = useState<
    'home' | 'library' | 'search'
  >('library');
  const [selectedCategory, setSelectedCategory] = useState('전체');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    loadContents();
    loadConnections();
    loadSmartCollections();
    loadContentConflicts();
    loadInterestTimeline();
    loadSmartReminders();
  }, []);

  useEffect(() => {
    const hasAnalyzingContent =
      contents.some((item) =>
        item.category.includes('정리 중') ||
        item.category.includes('정리 대기'),
      );

    if (!hasAnalyzingContent) return;

    const intervalId = setInterval(() => {
      loadContents(true);
      loadConnections(true);
      loadSmartCollections(true);
      loadContentConflicts(true);
      loadInterestTimeline(true);
      loadSmartReminders(true);
    }, 4000);

    return () => clearInterval(intervalId);
  }, [contents]);

  useEffect(() => {
    if (
      screen.name !== 'search' ||
      searchMode !== 'search' ||
      activeSmartCollection
    ) return;

    const searchTerm = query.trim();

    if (!searchTerm) {
      setSearchResults(contents);
      setSearchError(null);
      setSearching(false);
      return;
    }

    let cancelled = false;
    setSearching(true);
    setSearchError(null);

    const timeoutId = setTimeout(async () => {
      try {
        let data: ApiContent[] = [];

        if (connectionFilter) {
          data = await getConnectedContents(
            connectionFilter.type,
            connectionFilter.entity,
          );
        } else {
          const [keywordResult, semanticResult] =
            await Promise.allSettled([
              searchContents(searchTerm),
              semanticSearchContents(searchTerm, 20),
            ]);

          const merged = new Map<number, ApiContent>();

          if (keywordResult.status === 'fulfilled') {
            keywordResult.value.forEach((item) =>
              merged.set(item.id, item),
            );
          }

          if (semanticResult.status === 'fulfilled') {
            semanticResult.value.forEach((item) => {
              if (!merged.has(item.id)) {
                merged.set(item.id, item);
              }
            });
          }

          if (
            keywordResult.status === 'rejected' &&
            semanticResult.status === 'rejected'
          ) {
            throw new Error('검색 요청 실패');
          }

          data = Array.from(merged.values());
        }

        if (!cancelled) {
          setSearchResults(data.map(toContentItem));
        }
      } catch (error) {
        console.error('❌ 콘텐츠 검색 오류:', error);

        if (!cancelled) {
          setSearchResults([]);
          setSearchError(
            '검색하지 못했어요. 잠시 후 다시 시도해줘.',
          );
        }
      } finally {
        if (!cancelled) {
          setSearching(false);
        }
      }
    }, 350);

    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [
    activeSmartCollection,
    connectionFilter,
    contents,
    query,
    screen.name,
    searchMode,
  ]);

  useEffect(() => {
    if (screen.name !== 'search' || !connectionFilter) {
      setContentBundle(null);
      setBundleError(null);
      setBundleLoading(false);
      setActionPlan(null);
      setActionError(null);
      setActionLoading(false);
      setActiveChecklist(null);
      return;
    }

    let cancelled = false;

    async function loadBundleAndActions() {
      try {
        setBundleLoading(true);
        setBundleError(null);
        setActionPlan(null);
        setActionError(null);
        setActionLoading(false);

        const data = await getContentBundle(
          connectionFilter.type,
          connectionFilter.entity,
        );

        if (cancelled) return;

        setContentBundle(data);
        setBundleLoading(false);
        setActionLoading(true);

        try {
          const actions = await planContentActions(data);

          if (!cancelled) {
            setActionPlan(actions);
          }
        } catch (error) {
          console.error('❌ Action Agent 조회 오류:', error);

          if (!cancelled) {
            setActionPlan(null);
            setActionError(
              '바로 활용할 기능을 불러오지 못했어요. 저장한 내용은 그대로 볼 수 있어.',
            );
          }
        } finally {
          if (!cancelled) {
            setActionLoading(false);
          }
        }
      } catch (error) {
        console.error('❌ 관심 정보 묶음 조회 오류:', error);

        if (!cancelled) {
          setContentBundle(null);
          setBundleError(
            '모아보기 정보를 불러오지 못했어요. 관련 저장물은 그대로 볼 수 있어.',
          );
          setBundleLoading(false);
          setActionPlan(null);
          setActionLoading(false);
        }
      }
    }

    loadBundleAndActions();

    return () => {
      cancelled = true;
    };
  }, [connectionFilter, screen.name]);

  useEffect(() => {
    if (screen.name !== 'detail') {
      setDetailRawContent(null);
      setContentQuality(null);
      setAnalysisEditing(false);
      setCorrectionFocus(null);
      setCorrectionDraft(null);
      return;
    }

    const contentId = Number(screen.itemId);

    if (!Number.isFinite(contentId)) {
      return;
    }

    let cancelled = false;

    async function loadDetailMetadata() {
      try {
        setQualityLoading(true);

        const [content, quality] = await Promise.all([
          getContent(contentId),
          getContentQuality(contentId),
        ]);

        if (!cancelled) {
          setDetailRawContent(content);
          setContentQuality(quality);
        }
      } catch (error) {
        console.error(
          '❌ 상세 AI 검증 정보 조회 오류:',
          error,
        );
      } finally {
        if (!cancelled) {
          setQualityLoading(false);
        }
      }
    }

    loadDetailMetadata();

    return () => {
      cancelled = true;
    };
  }, [screen, contents]);

  useEffect(() => {
    if (screen.name !== 'detail') {
      return;
    }

    const contentId = Number(screen.itemId);

    if (!Number.isFinite(contentId)) {
      return;
    }

    let cancelled = false;

    async function loadSingleContentActions() {
      try {
        setActionPlan(null);
        setActionError(null);
        setActionLoading(true);
        setActiveChecklist(null);

        const actions =
          await planSingleContentActions(contentId);

        if (!cancelled) {
          setActionPlan(actions);
        }
      } catch (error) {
        console.error(
          '❌ 단일 콘텐츠 Action Agent 조회 오류:',
          error,
        );

        if (!cancelled) {
          setActionPlan(null);
          setActionError(
            '바로 활용할 기능을 불러오지 못했어요.',
          );
        }
      } finally {
        if (!cancelled) {
          setActionLoading(false);
        }
      }
    }

    loadSingleContentActions();

    return () => {
      cancelled = true;
    };
  }, [screen, contents]);

  async function loadContents(silent = false) {
    console.log('🔄 콘텐츠 조회 시작');

    try {
      if (!silent) setLoading(true);
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

      if (!silent) {
        Alert.alert(
          '내용을 불러오지 못했어요',
          '잠시 후 다시 시도해줘.',
        );
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function loadConnections(silent = false) {
    try {
      if (!silent) {
        setConnectionsLoading(true);
      }

      const data = await getContentConnections(8);
      setConnections(data);
    } catch (error) {
      console.error(
        '❌ 콘텐츠 연결 조회 오류:',
        error,
      );

      if (!silent) {
        setConnections([]);
      }
    } finally {
      if (!silent) {
        setConnectionsLoading(false);
      }
    }
  }

  const categories = useMemo(() => {
    const all = Array.from(
      new Set(contents.flatMap((item) => item.category)),
    );

    return ['전체', ...all];
  }, [contents]);

  const filteredContents = useMemo(() => {
    if (selectedCategory === '전체') return contents;

    return contents.filter((item) =>
      item.category.includes(selectedCategory),
    );
  }, [contents, selectedCategory]);

  const detailItem =
    screen.name === 'detail'
      ? contents.find((item) => item.id === screen.itemId) ??
        searchResults.find((item) => item.id === screen.itemId)
      : undefined;

  function goTab(
    name: 'home' | 'save' | 'library' | 'search' | 'more',
  ) {
    if (name === 'search') {
      setConnectionFilter(null);
      setContentBundle(null);
      setBundleError(null);
    }

    setScreen({ name });
  }

  function openConflictEvidence(
    contentId: number,
  ) {
    openDetail(String(contentId), 'home');
  }

  function conflictTypeLabel(
    claimType: string,
  ) {
    const labels: Record<string, string> = {
      DATE_TIME: '날짜·시간',
      PRICE: '가격',
      LOCATION: '장소',
      STATISTIC: '수치',
      PRODUCT_PERFORMANCE: '제품 정보',
      HEALTH_BEAUTY: '건강·뷰티 정보',
      TRAVEL_RULE: '여행 정보',
      OTHER: '정보',
    };

    return labels[claimType] ?? '정보';
  }

  async function runCollectionComparison() {
    if (!activeSmartCollection) return;

    setCollectionComparisonLoading(true);
    setCollectionComparisonError(null);

    try {
      const result = await compareSmartCollection(
        activeSmartCollection.title,
        activeSmartCollection.contents.map(
          (item) => item.contentId,
        ),
      );
      setCollectionComparison(result);
    } catch (error) {
      console.error('❌ 컬렉션 비교 오류:', error);
      setCollectionComparisonError(
        '비교 결과를 만들지 못했어요. 잠시 후 다시 시도해 주세요.',
      );
    } finally {
      setCollectionComparisonLoading(false);
    }
  }

  function externalFactStatusLabel(status: string) {
    const labels: Record<string, string> = {
      SUPPORTED: '외부 근거와 일치',
      UPDATED: '현재 정보로 업데이트',
      CONFLICTING: '외부 정보와 다름',
      INSUFFICIENT_EVIDENCE: '확인 가능한 근거 부족',
    };

    return labels[status] ?? '외부 확인';
  }

  function openSmartCollection(
    collection: ApiSmartCollection,
  ) {
    setActiveSmartCollection(collection);
    setCollectionComparison(null);
    setCollectionComparisonError(null);
    setConnectionFilter(null);
    setSearchMode('search');
    setQuery('');
    setSearchError(null);

    const ids = new Set(
      collection.contents.map((item) =>
        String(item.contentId),
      ),
    );

    setSearchResults(
      contents.filter((item) =>
        ids.has(item.id),
      ),
    );

    setScreen({ name: 'search' });
  }

  function openConnection(
    connection: ApiContentConnection,
  ) {
    setActiveSmartCollection(null);
    setConnectionFilter(connection);
    setQuery(connection.entity);
    setScreen({ name: 'search' });
  }

  function connectionTypeLabel(
    type: ApiContentConnection['type'],
  ) {
    const labels: Record<
      ApiContentConnection['type'],
      string
    > = {
      PLACE: '장소',
      PRODUCT: '상품',
      BRAND: '브랜드',
      PERSON: '인물',
      SERVICE: '서비스',
    };

    return labels[type];
  }

  function connectionTypeIcon(
    type: ApiContentConnection['type'],
  ): keyof typeof Ionicons.glyphMap {
    const icons: Record<
      ApiContentConnection['type'],
      keyof typeof Ionicons.glyphMap
    > = {
      PLACE: 'location-outline',
      PRODUCT: 'bag-outline',
      BRAND: 'pricetag-outline',
      PERSON: 'person-outline',
      SERVICE: 'apps-outline',
    };

    return icons[type];
  }

  function actionTypeIcon(
    kind: ApiContentAction['kind'],
  ): keyof typeof Ionicons.glyphMap {
    const icons: Record<
      ApiContentAction['kind'],
      keyof typeof Ionicons.glyphMap
    > = {
      MAP_SEARCH: 'map-outline',
      WEB_SEARCH: 'search-outline',
      COMPARE_SEARCH: 'swap-horizontal-outline',
      CALENDAR_ADD: 'calendar-outline',
      CHECKLIST_CREATE: 'checkbox-outline',
    };

    return icons[kind];
  }

  const correctionEntityTypes: ApiEntityCorrection['type'][] = [
    'PLACE',
    'PRODUCT',
    'BRAND',
    'PERSON',
    'SERVICE',
    'EVENT',
    'DATE',
    'OTHER',
  ];

  const correctionCategories = [
    '장소/여행',
    '음식/레시피',
    '제품/쇼핑',
    '뷰티/패션',
    '학습/커리어',
    '건강/운동',
    '생활정보',
    '엔터테인먼트',
    '기타',
  ];

  function entityTypeLabel(
    type: ApiEntityCorrection['type'],
  ) {
    const labels: Record<
      ApiEntityCorrection['type'],
      string
    > = {
      PLACE: '장소',
      PRODUCT: '제품',
      BRAND: '브랜드',
      PERSON: '인물',
      SERVICE: '서비스',
      EVENT: '행사',
      DATE: '날짜',
      OTHER: '기타',
    };

    return labels[type];
  }

  function entityTypeIcon(
    type: ApiEntityCorrection['type'],
  ): keyof typeof Ionicons.glyphMap {
    const icons: Record<
      ApiEntityCorrection['type'],
      keyof typeof Ionicons.glyphMap
    > = {
      PLACE: 'location-outline',
      PRODUCT: 'bag-outline',
      BRAND: 'pricetag-outline',
      PERSON: 'person-outline',
      SERVICE: 'apps-outline',
      EVENT: 'calendar-outline',
      DATE: 'time-outline',
      OTHER: 'information-circle-outline',
    };

    return icons[type];
  }

  function qualityMessage(type: string) {
    const messages: Record<string, string> = {
      LOW_CONFIDENCE_ENTITY:
        '일부 정보가 확실하지 않아 한 번 확인하는 게 좋아요.',
      ENTITY_TYPE_CONFLICT:
        '같은 정보가 서로 다르게 정리되어 있어요.',
      CATEGORY_ENTITY_CONFLICT:
        '콘텐츠 내용과 저장된 정보가 서로 맞지 않을 수 있어요.',
      INVALID_DATE:
        '날짜 정보가 올바르지 않을 수 있어요.',
      CANONICAL_TYPE_CONFLICT:
        '전에 확인한 정보와 이번에 정리된 내용이 달라요.',
      MISSING_STRUCTURED_ANALYSIS:
        '일부 정보를 자동으로 확인하지 못했어요.',
      VALIDATION_PARSE_ERROR:
        '일부 정보를 자동으로 확인하지 못했어요.',
    };

    return messages[type] ??
      '확인이 필요한 정보가 있어요.';
  }

  function actionDisplayTitle(
    action: ApiContentAction,
  ) {
    const labels: Record<
      ApiContentAction['kind'],
      string
    > = {
      MAP_SEARCH: '지도에서 보기',
      WEB_SEARCH: '더 찾아보기',
      COMPARE_SEARCH: '비교해서 보기',
      CALENDAR_ADD: '캘린더에 추가',
      CHECKLIST_CREATE: '체크리스트 만들기',
    };

    return labels[action.kind] || action.title;
  }

  function parseCorrectionEntities(
    raw?: string | null,
  ): ApiEntityCorrection[] {
    if (!raw) return [];

    try {
      const structured = JSON.parse(raw);
      const details = Array.isArray(structured?.entityDetails)
        ? structured.entityDetails
        : [];

      return details
        .map((item: any) => ({
          name: String(item?.name ?? '').trim(),
          type: String(item?.type ?? 'OTHER')
            .trim()
            .toUpperCase() as ApiEntityCorrection['type'],
        }))
        .filter(
          (item: ApiEntityCorrection) =>
            item.name.length > 0 &&
            correctionEntityTypes.includes(item.type),
        );
    } catch (error) {
      console.error('❌ entityDetails 파싱 오류:', error);
      return [];
    }
  }

  function beginAnalysisCorrection(
    focus: 'summary' | 'info' = 'info',
  ) {
    if (!detailRawContent) return;

    setCorrectionDraft({
      title: detailRawContent.title ?? '',
      summary: detailRawContent.summary ?? '',
      categories: detailRawContent.categories ?? [],
      keywords: (detailRawContent.keywords ?? []).join(', '),
      entityDetails: parseCorrectionEntities(
        detailRawContent.structuredAnalysis,
      ),
    });

    setCorrectionFocus(focus);
    setAnalysisEditing(true);
  }

  function toggleCorrectionCategory(category: string) {
    setCorrectionDraft((current) => {
      if (!current) return current;

      const selected =
        current.categories.includes(category);

      return {
        ...current,
        categories: selected
          ? current.categories.filter(
              (item) => item !== category,
            )
          : [...current.categories, category],
      };
    });
  }

  function splitDraftList(value: string) {
    return Array.from(
      new Set(
        value
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
      ),
    );
  }


  async function loadSmartReminders(
    silent = false,
  ) {
    try {
      if (!silent) {
        setSmartRemindersLoading(true);
      }

      const data = await getSmartReminders(6);
      setSmartReminders(data);
    } catch (error) {
      console.error('❌ 스마트 리마인더 조회 오류:', error);

      if (!silent) {
        setSmartReminders([]);
      }
    } finally {
      if (!silent) {
        setSmartRemindersLoading(false);
      }
    }
  }

  async function loadInterestTimeline(
    silent = false,
  ) {
    try {
      if (!silent) {
        setInterestTimelineLoading(true);
      }

      const data = await getInterestTimeline();
      setInterestTimeline(data);
    } catch (error) {
      console.error('❌ 관심사 타임라인 조회 오류:', error);

      if (!silent) {
        setInterestTimeline(null);
      }
    } finally {
      if (!silent) {
        setInterestTimelineLoading(false);
      }
    }
  }

  async function loadContentConflicts(
    silent = false,
  ) {
    try {
      if (!silent) {
        setContentConflictsLoading(true);
      }

      const data = await getContentConflicts(6);
      setContentConflicts(data);
    } catch (error) {
      console.error('❌ 저장물 상충 정보 조회 오류:', error);

      if (!silent) {
        setContentConflicts([]);
      }
    } finally {
      if (!silent) {
        setContentConflictsLoading(false);
      }
    }
  }

  async function loadSmartCollections(
    silent = false,
  ) {
    try {
      if (!silent) {
        setSmartCollectionsLoading(true);
      }

      const data = await getSmartCollections(6);
      setSmartCollections(data);
    } catch (error) {
      console.error('❌ 스마트 컬렉션 조회 오류:', error);

      if (!silent) {
        setSmartCollections([]);
      }
    } finally {
      if (!silent) {
        setSmartCollectionsLoading(false);
      }
    }
  }


  async function saveAnalysisCorrection() {
    if (
      !detailRawContent ||
      !correctionDraft ||
      correctionSaving
    ) {
      return;
    }

    try {
      setCorrectionSaving(true);

      const updated = await correctContent(
        detailRawContent.id,
        {
          title: correctionDraft.title.trim(),
          summary: correctionDraft.summary.trim(),
          categories: correctionDraft.categories,
          keywords: splitDraftList(
            correctionDraft.keywords,
          ),
          entityDetails: correctionDraft.entityDetails
            .map((item) => ({
              name: item.name.trim(),
              type: item.type,
            }))
            .filter((item) => item.name.length > 0),
        },
      );

      setDetailRawContent(updated);
      setAnalysisEditing(false);
      setCorrectionFocus(null);
      setCorrectionDraft(null);

      const updatedItem = toContentItem(updated);

      setContents((current) =>
        current.map((item) =>
          item.id === String(updated.id)
            ? updatedItem
            : item,
        ),
      );

      setSearchResults((current) =>
        current.map((item) =>
          item.id === String(updated.id)
            ? updatedItem
            : item,
        ),
      );

      const quality = await getContentQuality(
        updated.id,
      );
      setContentQuality(quality);

      const actions =
        await planSingleContentActions(updated.id);
      setActionPlan(actions);

      await loadConnections(true);

      Alert.alert(
        '수정했어',
        '바꾼 내용이 저장됐고 관련 검색과 활용 기능에도 반영했어.',
      );
    } catch (error) {
      console.error('❌ AI 결과 수정 오류:', error);

      Alert.alert(
        '수정하지 못했어',
        '서버 상태를 확인한 뒤 다시 시도해줘.',
      );
    } finally {
      setCorrectionSaving(false);
    }
  }

  async function retryDetailAnalysis() {
    if (!detailRawContent) return;

    try {
      const updated =
        await reanalyzeContent(detailRawContent.id);

      setDetailRawContent(updated);

      const updatedItem = toContentItem(updated);

      setContents((current) =>
        current.map((item) =>
          item.id === String(updated.id)
            ? updatedItem
            : item,
        ),
      );

      Alert.alert(
        '다시 정리하고 있어요',
        '앱을 나가도 작업은 계속 진행돼.',
      );
    } catch (error) {
      console.error('❌ 재분석 요청 오류:', error);

      Alert.alert(
        '다시 시도하지 못했어요',
        '잠시 후 다시 시도해줘.',
      );
    }
  }

  function updateCorrectionEntity(
    index: number,
    patch: Partial<ApiEntityCorrection>,
  ) {
    setCorrectionDraft((current) => {
      if (!current) return current;

      return {
        ...current,
        entityDetails: current.entityDetails.map(
          (item, itemIndex) =>
            itemIndex === index
              ? { ...item, ...patch }
              : item,
        ),
      };
    });
  }

  function addCorrectionEntity() {
    setCorrectionDraft((current) => {
      if (!current) return current;

      return {
        ...current,
        entityDetails: [
          ...current.entityDetails,
          {
            name: '',
            type: 'OTHER',
          },
        ],
      };
    });
  }

  function removeCorrectionEntity(index: number) {
    setCorrectionDraft((current) => {
      if (!current) return current;

      return {
        ...current,
        entityDetails: current.entityDetails.filter(
          (_, itemIndex) => itemIndex !== index,
        ),
      };
    });
  }

  function currentDetailContentId() {
    if (screen.name !== 'detail') return null;

    const value = Number(screen.itemId);
    return Number.isFinite(value) ? value : null;
  }

  async function persistActionCorrection(
    fieldName: string,
    aiValue: string,
    correctedValue: string,
    errorType: string,
  ) {
    const contentId = currentDetailContentId();

    if (!contentId || aiValue === correctedValue) {
      return;
    }

    try {
      await logActionCorrection({
        contentId,
        fieldName,
        aiValue,
        correctedValue,
        errorType,
      });
    } catch (error) {
      console.error(
        '⚠️ Action 교정 로그 저장 실패:',
        error,
      );
    }
  }

  async function openExternalUrl(
    target: string,
    fallback?: string,
  ) {
    try {
      await Linking.openURL(target);
    } catch (error) {
      if (fallback) {
        try {
          await Linking.openURL(fallback);
          return;
        } catch (fallbackError) {
          console.error('❌ fallback URL 실행 오류:', fallbackError);
        }
      }

      console.error('❌ 외부 URL 실행 오류:', error);
      Alert.alert(
        '열지 못했어',
        '외부 화면을 열지 못했어. 잠시 후 다시 시도해줘.',
      );
    }
  }

  function openMapPicker(query: string) {
    const encoded = encodeURIComponent(query);

    Alert.alert(
      '지도 앱 선택',
      `“${query}”을 어디에서 찾아볼까?`,
      [
        {
          text: '네이버지도',
          onPress: () =>
            openExternalUrl(
              `nmap://search?query=${encoded}&appname=com.yewon.saveon20260918`,
              `https://map.naver.com/p/search/${encoded}`,
            ),
        },
        {
          text: '카카오맵',
          onPress: () =>
            openExternalUrl(
              `kakaomap://search?q=${encoded}`,
              `https://m.map.kakao.com/scheme/search?q=${encoded}`,
            ),
        },
        {
          text: '취소',
          style: 'cancel',
        },
      ],
    );
  }

  async function addCalendarEvent(
    action: ApiContentAction,
  ) {
    const eventDate = action.eventDate?.trim();
    const eventTitle = action.eventTitle?.trim() || action.title;

    if (!eventDate) {
      Alert.alert(
        '날짜를 확인할 수 없어',
        '저장 콘텐츠에서 명확한 날짜가 확인된 경우에만 캘린더에 추가할 수 있어.',
      );
      return;
    }

    try {
      const permission =
        await Calendar.requestCalendarPermissionsAsync();

      if (permission.status !== 'granted') {
        Alert.alert(
          '캘린더 권한이 필요해',
          '설정에서 캘린더 접근을 허용하면 일정으로 추가할 수 있어.',
        );
        return;
      }

      const calendars = await Calendar.getCalendarsAsync(
        Calendar.EntityTypes.EVENT,
      );

      const writableCalendar =
        calendars.find((calendar) => calendar.allowsModifications) ??
        calendars[0];

      if (!writableCalendar) {
        Alert.alert(
          '사용 가능한 캘린더가 없어',
          '기기에 수정 가능한 캘린더를 만든 뒤 다시 시도해줘.',
        );
        return;
      }

      const startDate = new Date(`${eventDate}T00:00:00`);
      if (Number.isNaN(startDate.getTime())) {
        throw new Error(`잘못된 날짜 형식: ${eventDate}`);
      }

      const endDate = new Date(startDate);
      endDate.setDate(endDate.getDate() + 1);

      await Calendar.createEventAsync(
        writableCalendar.id,
        {
          title: eventTitle,
          startDate,
          endDate,
          allDay: true,
          notes: action.description || 'save:on에서 저장한 콘텐츠 기반 일정',
          timeZone: 'Asia/Seoul',
        },
      );

      Alert.alert(
        '캘린더에 추가했어',
        `${eventDate} · ${eventTitle}`,
      );
    } catch (error) {
      console.error('❌ 캘린더 추가 오류:', error);
      Alert.alert(
        '일정을 추가하지 못했어',
        '캘린더 상태를 확인한 뒤 다시 시도해줘.',
      );
    }
  }

  function createChecklist(
    action: ApiContentAction,
  ) {
    const items = action.checklistItems ?? [];

    if (items.length < 2) {
      Alert.alert(
        '체크리스트를 만들 수 없어',
        '저장 콘텐츠에서 체크 항목을 충분히 찾지 못했어.',
      );
      return;
    }

    setActiveChecklist({
      key: `${action.kind}:${action.title}`,
      title: action.title,
      items,
      checked: items.map(() => false),
    });
  }

  function toggleChecklistItem(index: number) {
    setActiveChecklist((current) => {
      if (!current) return current;

      return {
        ...current,
        checked: current.checked.map((value, itemIndex) =>
          itemIndex === index ? !value : value,
        ),
      };
    });
  }

  function confirmMapAction(
    action: ApiContentAction,
  ) {
    const query = action.query.trim();
    if (!query) return;

    Alert.alert(
      '어디를 찾아볼까요?',
      `“${query}”을 지도에서 찾아볼게요.`,
      [
        {
          text: '장소 수정',
          onPress: () => {
            Alert.prompt(
              '장소 수정',
              '지도에서 검색할 정확한 장소명을 입력해줘.',
              async (value) => {
                const corrected = value?.trim();
                if (!corrected) return;

                await persistActionCorrection(
                  'MAP_QUERY',
                  query,
                  corrected,
                  'ENTITY_NAME_ERROR',
                );

                openMapPicker(corrected);
              },
              'plain-text',
              query,
            );
          },
        },
        {
          text: '지도 선택',
          onPress: () => openMapPicker(query),
        },
        {
          text: '취소',
          style: 'cancel',
        },
      ],
    );
  }

  function confirmCalendarAction(
    action: ApiContentAction,
  ) {
    const eventDate = action.eventDate?.trim();
    const eventTitle =
      action.eventTitle?.trim() || action.title;

    if (!eventDate) {
      Alert.alert(
        '날짜를 확인할 수 없어',
        '명확한 날짜가 있는 경우에만 캘린더에 추가할 수 있어.',
      );
      return;
    }

    Alert.alert(
      '캘린더에 추가',
      `${eventTitle}\n${eventDate} · 종일`,
      [
        {
          text: '날짜 수정',
          onPress: () => {
            Alert.prompt(
              '날짜 수정',
              'YYYY-MM-DD 형식으로 입력해줘.',
              async (value) => {
                const corrected = value?.trim();

                if (
                  !corrected ||
                  !/^\d{4}-\d{2}-\d{2}$/.test(corrected)
                ) {
                  Alert.alert(
                    '형식을 확인해줘',
                    '예: 2026-11-04',
                  );
                  return;
                }

                await persistActionCorrection(
                  'EVENT_DATE',
                  eventDate,
                  corrected,
                  'WRONG_DATE',
                );

                await addCalendarEvent({
                  ...action,
                  eventDate: corrected,
                });
              },
              'plain-text',
              eventDate,
            );
          },
        },
        {
          text: '추가',
          onPress: () => addCalendarEvent(action),
        },
        {
          text: '취소',
          style: 'cancel',
        },
      ],
    );
  }

  async function executeContentAction(
    action: ApiContentAction,
  ) {
    if (action.kind === 'MAP_SEARCH') {
      confirmMapAction(action);
      return;
    }

    if (action.kind === 'CALENDAR_ADD') {
      confirmCalendarAction(action);
      return;
    }

    if (action.kind === 'CHECKLIST_CREATE') {
      createChecklist(action);
      return;
    }

    const query = action.query.trim();
    if (!query) return;

    const encoded = encodeURIComponent(query);
    await openExternalUrl(
      `https://www.google.com/search?q=${encoded}`,
    );
  }

  function actionMetaText(
    action: ApiContentAction,
  ) {
    if (
      action.kind === 'MAP_SEARCH' ||
      action.kind === 'WEB_SEARCH' ||
      action.kind === 'COMPARE_SEARCH'
    ) {
      return action.query.trim()
        ? `“${action.query.trim()}”`
        : '';
    }

    if (action.kind === 'CALENDAR_ADD') {
      return action.eventDate?.trim()
        ? `${action.eventDate} · 종일 일정`
        : '캘린더 일정';
    }

    if (action.kind === 'CHECKLIST_CREATE') {
      const count = action.checklistItems?.length ?? 0;
      return count > 0
        ? `${count}개 체크 항목`
        : '앱 내부 체크리스트';
    }

    return '';
  }

  function renderActionAgentPanel(
    intro: string,
  ) {
    if (!actionLoading && !actionPlan && !actionError) {
      return null;
    }

    const visibleActions =
      actionPlan?.actions.slice(0, 3) ?? [];

    return (
      <View style={styles.actionAgentPanel}>
        <View style={styles.agentHeaderRow}>
          <View style={styles.agentHeaderLeft}>
            <Ionicons
              name="flash-outline"
              size={17}
              color={theme.accent}
            />
            <Text style={styles.agentTitle}>
              바로 활용하기
            </Text>
          </View>
        </View>

        <Text style={styles.actionAgentIntro}>
          {intro}
        </Text>

        {actionLoading ? (
          <View style={styles.actionLoadingRow}>
            <ActivityIndicator
              size="small"
              color={theme.accent}
            />
            <Text style={styles.actionLoadingText}>
              이 저장물에 맞는 기능을 준비하고 있어요.
            </Text>
          </View>
        ) : actionError ? (
          <Text style={styles.actionErrorText}>
            {actionError}
          </Text>
        ) : visibleActions.length === 0 ? (
          <Text style={styles.actionLoadingText}>
            지금 바로 이어서 할 작업은 없어요.
          </Text>
        ) : (
          visibleActions.map((action, index) => {
            const meta = actionMetaText(action);

            return (
              <Pressable
                key={`${action.kind}:${action.query || action.eventDate || action.title}`}
                style={[
                  styles.actionCard,
                  index === 0 &&
                    styles.actionCardPrimary,
                ]}
                onPress={() => executeContentAction(action)}
              >
                <View
                  style={[
                    styles.actionIconBubble,
                    index === 0 &&
                      styles.actionIconBubblePrimary,
                  ]}
                >
                  <Ionicons
                    name={actionTypeIcon(action.kind)}
                    size={18}
                    color={
                      index === 0
                        ? '#FFFFFF'
                        : theme.accent
                    }
                  />
                </View>

                <View style={styles.actionCardBody}>
                  <Text
                    style={[
                      styles.actionTitle,
                      index === 0 &&
                        styles.actionTitlePrimary,
                    ]}
                  >
                    {actionDisplayTitle(action)}
                  </Text>

                  {action.description.length > 0 && (
                    <Text
                      style={[
                        styles.actionDescription,
                        index === 0 &&
                          styles.actionDescriptionPrimary,
                      ]}
                    >
                      {action.description}
                    </Text>
                  )}

                  {meta.length > 0 && (
                    <Text
                      style={[
                        styles.actionQuery,
                        index === 0 &&
                          styles.actionQueryPrimary,
                      ]}
                    >
                      {meta}
                    </Text>
                  )}
                </View>

                <Ionicons
                  name={
                    action.kind === 'CHECKLIST_CREATE'
                      ? 'chevron-down-outline'
                      : 'chevron-forward-outline'
                  }
                  size={17}
                  color={
                    index === 0
                      ? '#FFFFFF'
                      : theme.muted
                  }
                />
              </Pressable>
            );
          })
        )}

        {activeChecklist && (
          <View style={styles.checklistPanel}>
            <View style={styles.checklistHeaderRow}>
              <View>
                <Text style={styles.checklistEyebrow}>
                  체크리스트
                </Text>
                <Text style={styles.checklistTitle}>
                  {activeChecklist.title}
                </Text>
              </View>

              <Pressable
                onPress={() => setActiveChecklist(null)}
                hitSlop={8}
              >
                <Ionicons
                  name="close-outline"
                  size={22}
                  color={theme.muted}
                />
              </Pressable>
            </View>

            {activeChecklist.items.map((item, index) => {
              const checked =
                activeChecklist.checked[index];

              return (
                <Pressable
                  key={`${activeChecklist.key}:${index}:${item}`}
                  style={styles.checklistRow}
                  onPress={() =>
                    toggleChecklistItem(index)
                  }
                >
                  <Ionicons
                    name={
                      checked
                        ? 'checkbox'
                        : 'square-outline'
                    }
                    size={21}
                    color={
                      checked
                        ? theme.primary
                        : theme.muted
                    }
                  />

                  <Text
                    style={[
                      styles.checklistItemText,
                      checked &&
                        styles.checklistItemTextChecked,
                    ]}
                  >
                    {item}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        )}
      </View>
    );
  }

  function renderConnectionBundle() {
    if (!connectionFilter) return null;

    if (bundleLoading) {
      return (
        <View style={styles.bundlePanel}>
          <View style={styles.bundleLoadingRow}>
            <ActivityIndicator
              size="small"
              color={theme.primary}
            />
            <Text style={styles.bundleLoadingText}>
              저장한 내용을 한눈에 볼 수 있게 정리하고 있어요.
            </Text>
          </View>
        </View>
      );
    }

    if (bundleError) {
      return (
        <View style={styles.bundlePanel}>
          <Text style={styles.bundleErrorText}>
            {bundleError}
          </Text>
        </View>
      );
    }

    if (!contentBundle) return null;

    return (
      <View style={styles.bundlePanel}>
        <View style={styles.bundleHeader}>
          <View style={styles.bundleIconBubble}>
            <Ionicons
              name={connectionTypeIcon(contentBundle.type)}
              size={20}
              color={theme.primary}
            />
          </View>

          <View style={styles.bundleHeaderText}>
            <Text style={styles.bundleEyebrow}>
              내가 모은 정보
            </Text>
            <Text style={styles.bundleTitle}>
              {contentBundle.entity}
            </Text>
            <Text style={styles.bundleMeta}>
              {contentBundle.count}개의 저장물에서 함께 나온 {connectionTypeLabel(contentBundle.type)}
            </Text>
          </View>
        </View>

        {contentBundle.synthesis ? (
          <View style={styles.agentPanel}>
            <View style={styles.agentHeaderRow}>
              <View style={styles.agentHeaderLeft}>
                <Ionicons
                  name="sparkles-outline"
                  size={17}
                  color={theme.primary}
                />
                <Text style={styles.agentTitle}>
                  저장한 내용 한눈에 보기
                </Text>
              </View>
            </View>

            <Text style={styles.agentSummary}>
              {contentBundle.synthesis.summary}
            </Text>

            {contentBundle.synthesis.keyInterests.length > 0 && (
              <View style={styles.agentSubsection}>
                <Text style={styles.agentSubsectionTitle}>
                  자주 나온 주제
                </Text>
                <View style={styles.wrapRow}>
                  {contentBundle.synthesis.keyInterests.map((item) => (
                    <View
                      key={`agent-interest:${item}`}
                      style={styles.agentInterestPill}
                    >
                      <Text style={styles.agentInterestText}>
                        {item}
                      </Text>
                    </View>
                  ))}
                </View>
              </View>
            )}

            {contentBundle.synthesis.takeaways.length > 0 && (
              <View style={styles.agentSubsection}>
                <Text style={styles.agentSubsectionTitle}>
                  저장물에서 반복된 내용
                </Text>
                {contentBundle.synthesis.takeaways.map((item, index) => (
                  <View
                    key={`agent-takeaway:${index}:${item}`}
                    style={styles.agentTakeawayRow}
                  >
                    <View style={styles.agentBullet} />
                    <Text style={styles.agentTakeawayText}>
                      {item}
                    </Text>
                  </View>
                ))}
              </View>
            )}
          </View>
        ) : (
          <Text style={styles.bundleOverview}>
            {contentBundle.overview}
          </Text>
        )}

        {renderActionAgentPanel(
          '필요한 경우 저장한 정보를 바로 다음 행동으로 이어갈 수 있어요.',
        )}

        {contentBundle.categories.length > 0 && (
          <View style={styles.bundleSection}>
            <Text style={styles.bundleSectionTitle}>
              이런 내용이 많아요
            </Text>
            <View style={styles.wrapRow}>
              {contentBundle.categories.map((item) => (
                <View
                  key={`category:${item}`}
                  style={styles.bundleCategoryPill}
                >
                  <Text style={styles.bundleCategoryText}>
                    {item}
                  </Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {contentBundle.commonTags.length > 0 && (
          <View style={styles.bundleSection}>
            <Text style={styles.bundleSectionTitle}>
              자주 함께 나온 주제
            </Text>
            <View style={styles.wrapRow}>
              {contentBundle.commonTags.map((tag) => (
                <View
                  key={`tag:${tag}`}
                  style={styles.bundleTagPill}
                >
                  <Text style={styles.bundleTagText}>
                    #{tag}
                  </Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {contentBundle.relatedEntities.length > 0 && (
          <View style={styles.bundleSection}>
            <Text style={styles.bundleSectionTitle}>
              함께 자주 나온 정보
            </Text>

            {contentBundle.relatedEntities.map((item) => (
              <View
                key={`${item.type}:${item.entity}`}
                style={styles.relatedEntityRow}
              >
                <View style={styles.relatedEntityLeft}>
                  <Ionicons
                    name={connectionTypeIcon(item.type)}
                    size={15}
                    color={theme.accent}
                  />
                  <View>
                    <Text style={styles.relatedEntityName}>
                      {item.entity}
                    </Text>
                    <Text style={styles.relatedEntityTypeText}>
                      {connectionTypeLabel(item.type)}
                    </Text>
                  </View>
                </View>
                <Text style={styles.relatedEntityCount}>
                  {item.count}개 저장물
                </Text>
              </View>
            ))}
          </View>
        )}

        {contentBundle.highlights.length > 0 && (
          <View style={styles.bundleSection}>
            <Text style={styles.bundleSectionTitle}>
              이 주제로 저장한 내용
            </Text>

            {contentBundle.highlights.map((highlight) => (
              <View
                key={highlight.contentId}
                style={styles.highlightCard}
              >
                <Text style={styles.highlightTitle}>
                  {highlight.title}
                </Text>
                {highlight.summary.length > 0 && (
                  <Text style={styles.highlightSummary}>
                    {highlight.summary}
                  </Text>
                )}
              </View>
            ))}
          </View>
        )}
      </View>
    );
  }

  function openDetail(
    itemId: string,
    from: 'home' | 'library' | 'search',
  ) {
    setDetailReturnTab(from);
    setScreen({
      name: 'detail',
      itemId,
    });
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

    const duplicate = contents.find(
      (item) => item.sourceUrl === trimmed,
    );

    if (duplicate) {
      Alert.alert(
        '이미 저장한 콘텐츠예요',
        '기존에 저장한 내용을 바로 열어볼 수 있어요.',
        [
          {
            text: '보러 가기',
            onPress: () =>
              openDetail(duplicate.id, 'home'),
          },
          {
            text: '취소',
            style: 'cancel',
          },
        ],
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
        '저장했어요',
        '앱을 나가도 내용 정리는 계속 진행돼. 끝나면 저장물에 자동으로 채워져요.',
      );
    } catch (error) {
      console.error('❌ 콘텐츠 저장 오류:', error);

      Alert.alert(
        '저장하지 못했어요',
        '잠시 후 다시 시도해줘.',
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

      loadConnections(true);

      Alert.alert(
        analyzed.status === 'COMPLETED'
          ? '영상 정리가 끝났어요'
          : '영상을 저장했어요',
        analyzed.status === 'COMPLETED'
          ? '영상에서 필요한 내용을 정리해 저장했어.'
          : '내용을 정리하지 못했다면 저장물에서 다시 시도할 수 있어.',
      );
    } catch (error) {
      console.error(
        '❌ 영상 업로드 오류:',
        error,
      );

      Alert.alert(
        '영상을 저장하지 못했어요',
        '잠시 후 다시 시도해줘.',
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
              SAVE:ON
            </Text>

            <Text style={styles.h1}>
              저장해둔 순간을{'\n'}
              필요할 때 바로 꺼내 쓰게.
            </Text>
          </View>

          <View style={styles.logoBubble}>
            <Text style={styles.logoText}>SO</Text>
          </View>
        </View>

        <View style={styles.hero}>
          <Text style={styles.heroLabel}>
            내 저장물
          </Text>

          <Text style={styles.heroNumber}>
            {contents.length}
          </Text>

          <Text style={styles.heroSub}>
            {loading
              ? '저장한 내용을 불러오고 있어요.'
              : contents.length > 0
                ? '저장한 영상과 링크를 필요할 때 다시 찾기 쉽게 정리해뒀어요.'
                : '릴스나 쇼츠를 하나 저장해보세요. 필요한 내용만 알아서 정리해둘게요.'}
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
              새로 저장하기
            </Text>
          </Pressable>
        </View>

        {contents.length === 0 && (
          <View style={styles.onboardingCard}>
            <Text style={styles.onboardingTitle}>
              이렇게 쓰면 돼요
            </Text>

            <View style={styles.onboardingStep}>
              <View style={styles.onboardingNumber}>
                <Text style={styles.onboardingNumberText}>1</Text>
              </View>
              <Text style={styles.onboardingStepText}>
                릴스·쇼츠 링크를 붙여넣거나 Save:on으로 공유해요.
              </Text>
            </View>

            <View style={styles.onboardingStep}>
              <View style={styles.onboardingNumber}>
                <Text style={styles.onboardingNumberText}>2</Text>
              </View>
              <Text style={styles.onboardingStepText}>
                앱을 나가도 내용 정리는 계속돼요.
              </Text>
            </View>

            <View style={styles.onboardingStep}>
              <View style={styles.onboardingNumber}>
                <Text style={styles.onboardingNumberText}>3</Text>
              </View>
              <Text style={styles.onboardingStepText}>
                나중에 검색하거나 지도·캘린더 같은 기능으로 바로 활용해요.
              </Text>
            </View>
          </View>
        )}

        {contents.length > 0 && (
          <>
            {contentConflicts.length > 0 && (
              <Pressable
                style={styles.homeAlertSummary}
                onPress={() => goTab('more')}
              >
                <View style={styles.homeAlertIcon}>
                  <Ionicons
                    name="alert-circle-outline"
                    size={18}
                    color="#A75B36"
                  />
                </View>

                <View style={styles.homeAlertBody}>
                  <Text style={styles.homeAlertTitle}>
                    확인이 필요한 정보가 {contentConflicts.length}개 있어요
                  </Text>
                  <Text style={styles.homeAlertText}>
                    저장한 콘텐츠끼리 내용이 다른 부분을 확인해보세요.
                  </Text>
                </View>

                <Ionicons
                  name="chevron-forward"
                  size={17}
                  color={theme.muted}
                />
              </Pressable>
            )}

            <View style={styles.rowBetween}>
              <View>
                <Text style={styles.sectionTitle}>
                  자동으로 묶인 주제
                </Text>
                <Text style={styles.smartSectionSubtitle}>
                  비슷한 저장물을 주제별로 모아뒀어요.
                </Text>
              </View>

              {smartCollections.length > 0 && (
                <Pressable onPress={() => goTab('more')}>
                  <Text style={styles.linkText}>
                    전체 보기
                  </Text>
                </Pressable>
              )}
            </View>

            {smartCollectionsLoading ? (
              <View style={styles.emptyBox}>
                <ActivityIndicator
                  size="small"
                  color={theme.primary}
                />
              </View>
            ) : smartCollections.length > 0 ? (
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.smartCollectionRow}
              >
                {smartCollections.slice(0, 3).map((collection) => (
                  <Pressable
                    key={collection.key}
                    style={styles.smartCollectionCard}
                    onPress={() =>
                      openSmartCollection(collection)
                    }
                  >
                    <View style={styles.smartCollectionTop}>
                      <View style={styles.smartCollectionIcon}>
                        <Ionicons
                          name="albums-outline"
                          size={18}
                          color={theme.primary}
                        />
                      </View>
                      <Text style={styles.smartCollectionCount}>
                        {collection.count}개
                      </Text>
                    </View>

                    <Text
                      style={styles.smartCollectionTitle}
                      numberOfLines={2}
                    >
                      {collection.title}
                    </Text>

                    <Text
                      style={styles.smartCollectionDescription}
                      numberOfLines={3}
                    >
                      {collection.description}
                    </Text>
                  </Pressable>
                ))}
              </ScrollView>
            ) : (
              <View style={styles.emptyBox}>
                <Text style={styles.emptyText}>
                  비슷한 주제의 저장물이 쌓이면 자동으로 모아드려요.
                </Text>
              </View>
            )}

            {connections.length > 0 && (
              <Pressable
                style={styles.homeInterestSummary}
                onPress={() => goTab('more')}
              >
                <View style={styles.homeInterestBody}>
                  <Text style={styles.homeInterestLabel}>
                    내가 자주 저장한 관심사
                  </Text>
                  <Text
                    style={styles.homeInterestText}
                    numberOfLines={1}
                  >
                    {connections
                      .slice(0, 3)
                      .map((item) => item.entity)
                      .join(' · ')}
                  </Text>
                </View>

                <Ionicons
                  name="chevron-forward"
                  size={18}
                  color={theme.muted}
                />
              </Pressable>
            )}

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
                  openDetail(item.id, 'home')
                }
              />
            ))}
          </>
        )}
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
          SAVE:ON
        </Text>

        <Text style={styles.h1}>
          새로 저장하기
        </Text>

        <Text style={styles.bodyText}>
          링크나 영상을 저장하면 내용을 읽고, 나중에 다시 찾기 쉽게 정리해둘게요.
        </Text>

        <View style={styles.saveNotice}>
          <Ionicons
            name="checkmark-circle-outline"
            size={19}
            color={theme.primary}
          />
          <Text style={styles.saveNoticeText}>
            저장이 끝나면 앱을 나가도 괜찮아요. 내용 정리는 뒤에서 계속돼요.
          </Text>
        </View>

        <View style={styles.panel}>
          <View style={styles.inputLabelRow}>
            <Ionicons
              name="link-outline"
              size={18}
              color={theme.primary}
            />

            <Text style={styles.inputLabel}>
              링크 붙여넣기
            </Text>
          </View>

          <TextInput
            value={url}
            onChangeText={setUrl}
            placeholder="Instagram, YouTube 등의 링크"
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
              name="bookmark-outline"
              size={18}
              color="#fff"
            />

            <Text style={styles.primaryButtonText}>
              {loading ? '저장하는 중...' : '저장하기'}
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
              내 영상에서 저장
            </Text>
          </View>

          <Text style={styles.bodyText}>
            갤러리의 영상을 선택하면 말한 내용과 화면 속 정보를 함께 읽어 정리해요.
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
                ? '영상을 정리하고 있어요...'
                : '갤러리에서 선택'}
            </Text>
          </Pressable>

          {uploading && (
            <Text style={styles.processingText}>
              처음 사용하는 경우 준비 과정 때문에 조금 더 걸릴 수 있어요.
            </Text>
          )}
        </View>
      </ScrollView>
    );
  }

  function renderLibrary() {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <Text style={styles.eyebrow}>SAVE:ON</Text>
        <Text style={styles.h1}>내 저장물</Text>

        <Pressable
          style={[
            styles.refreshButton,
            loading && styles.disabledButton,
          ]}
          disabled={loading}
          onPress={() => {
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
              ? '불러오는 중...'
              : '새로고침'}
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
              아직 저장한 콘텐츠가 없어요. 릴스나 쇼츠를 공유해서 첫 저장물을 만들어보세요.
            </Text>
          </View>
        ) : (
          filteredContents.map((item) => (
            <ContentCard
              key={item.id}
              item={item}
              onPress={() =>
                openDetail(item.id, 'library')
              }
            />
          ))
        )}
      </ScrollView>
    );
  }

  async function askMySavedContent() {
    const question = knowledgeQuestion.trim();

    if (!question || knowledgeLoading) return;

    setKnowledgeLoading(true);
    setKnowledgeError(null);
    setKnowledgeAnswer(null);

    try {
      const result = await askSavedKnowledge(question, 5);
      setKnowledgeAnswer(result);
    } catch (error) {
      console.error('❌ 저장물 Q&A 오류:', error);
      setKnowledgeError(
        '지금은 답변을 만들지 못했어요. 잠시 후 다시 질문해줘.',
      );
    } finally {
      setKnowledgeLoading(false);
    }
  }

  function openKnowledgeSource(
    contentId: number,
  ) {
    openDetail(String(contentId), 'search');
  }

  function smartReminderIcon(
    type: ApiSmartReminder['type'],
  ): keyof typeof Ionicons.glyphMap {
    if (type === 'DATE_CHECK') return 'calendar-outline';
    if (type === 'EVENT_CHECK') return 'ticket-outline';
    if (type === 'TRAVEL_REVISIT') return 'map-outline';
    return 'time-outline';
  }

  function openSmartReminder(
    reminder: ApiSmartReminder,
  ) {
    openDetail(String(reminder.contentId), 'library');
  }

  function renderMore() {
    return (
      <ScrollView
        contentContainerStyle={styles.page}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.eyebrow}>
          SAVE:ON
        </Text>

        <Text style={styles.h1}>
          모아보기
        </Text>

        <Text style={styles.bodyText}>
          저장한 내용을 주제별로 보고, 반복되는 관심사와 확인이 필요한 정보를 한곳에서 볼 수 있어요.
        </Text>

        <View style={styles.interestTimelineSection}>
          <View style={styles.moreSectionHeader}>
            <View>
              <Text style={styles.sectionTitle}>
                최근 관심 변화
              </Text>
              <Text style={styles.moreSectionSubtitle}>
                최근 7일과 그 전 7일의 저장 패턴을 비교했어요.
              </Text>
            </View>
          </View>

          {interestTimelineLoading ? (
            <View style={styles.interestTimelineCard}>
              <ActivityIndicator
                size="small"
                color={theme.primary}
              />
              <Text style={styles.connectionLoadingText}>
                최근 관심 흐름을 정리하고 있어요.
              </Text>
            </View>
          ) : interestTimeline ? (
            <View style={styles.interestTimelineCard}>
              <View style={styles.interestTimelineSummaryRow}>
                <View style={styles.interestTimelineIcon}>
                  <Ionicons
                    name="trending-up-outline"
                    size={19}
                    color={theme.primary}
                  />
                </View>
                <Text style={styles.interestTimelineSummary}>
                  {interestTimeline.summary}
                </Text>
              </View>

              <View style={styles.interestTimelineStats}>
                <View style={styles.interestTimelineStat}>
                  <Text style={styles.interestTimelineStatValue}>
                    {interestTimeline.recentCount}
                  </Text>
                  <Text style={styles.interestTimelineStatLabel}>
                    최근 7일
                  </Text>
                </View>
                <View style={styles.interestTimelineStat}>
                  <Text style={styles.interestTimelineStatValue}>
                    {interestTimeline.previousCount}
                  </Text>
                  <Text style={styles.interestTimelineStatLabel}>
                    이전 7일
                  </Text>
                </View>
                <View style={styles.interestTimelineStat}>
                  <Text style={styles.interestTimelineStatValue}>
                    {interestTimeline.last30DaysCount}
                  </Text>
                  <Text style={styles.interestTimelineStatLabel}>
                    최근 30일
                  </Text>
                </View>
              </View>

              {interestTimeline.categoryTrends.length > 0 && (
                <View style={styles.interestTimelineBlock}>
                  <Text style={styles.interestTimelineBlockTitle}>
                    카테고리 변화
                  </Text>
                  <View style={styles.interestTrendList}>
                    {interestTimeline.categoryTrends.map((trend) => {
                      const isUp = trend.delta > 0;
                      const isDown = trend.delta < 0;
                      return (
                        <View
                          key={`trend:${trend.label}`}
                          style={styles.interestTrendRow}
                        >
                          <Text
                            style={styles.interestTrendLabel}
                            numberOfLines={1}
                          >
                            {trend.label}
                          </Text>
                          <View style={styles.interestTrendValueRow}>
                            <Text style={styles.interestTrendCount}>
                              {trend.currentCount}개
                            </Text>
                            <Ionicons
                              name={
                                isUp
                                  ? 'arrow-up-outline'
                                  : isDown
                                    ? 'arrow-down-outline'
                                    : 'remove-outline'
                              }
                              size={13}
                              color={
                                isUp
                                  ? theme.primary
                                  : isDown
                                    ? '#8A7F76'
                                    : theme.muted
                              }
                            />
                            <Text
                              style={[
                                styles.interestTrendDelta,
                                isUp && styles.interestTrendDeltaUp,
                              ]}
                            >
                              {trend.delta > 0 ? '+' : ''}{trend.delta}
                            </Text>
                          </View>
                        </View>
                      );
                    })}
                  </View>
                </View>
              )}

              {interestTimeline.emergingInterests.length > 0 && (
                <View style={styles.interestTimelineBlock}>
                  <Text style={styles.interestTimelineBlockTitle}>
                    새롭게 반복되는 관심사
                  </Text>
                  <View style={styles.interestTimelineChips}>
                    {interestTimeline.emergingInterests.map((item) => (
                      <View
                        key={`emerging:${item.type}:${item.label}`}
                        style={styles.interestTimelineChipStrong}
                      >
                        <Ionicons
                          name="sparkles-outline"
                          size={12}
                          color={theme.primary}
                        />
                        <Text style={styles.interestTimelineChipStrongText}>
                          {item.label} · {item.count}
                        </Text>
                      </View>
                    ))}
                  </View>
                </View>
              )}

              {interestTimeline.topInterests.length > 0 && (
                <View style={styles.interestTimelineBlock}>
                  <Text style={styles.interestTimelineBlockTitle}>
                    최근 30일 자주 저장한 관심사
                  </Text>
                  <View style={styles.interestTimelineChips}>
                    {interestTimeline.topInterests.map((item) => (
                      <View
                        key={`top:${item.type}:${item.label}`}
                        style={styles.interestTimelineChip}
                      >
                        <Text style={styles.interestTimelineChipText}>
                          {item.label} · {item.count}
                        </Text>
                      </View>
                    ))}
                  </View>
                </View>
              )}
            </View>
          ) : (
            <View style={styles.emptyBox}>
              <Text style={styles.emptyText}>
                저장물이 쌓이면 최근 관심 변화를 자동으로 보여드려요.
              </Text>
            </View>
          )}
        </View>

        {(smartRemindersLoading || smartReminders.length > 0) && (
          <View style={styles.smartReminderSection}>
            <View style={styles.moreSectionHeader}>
              <View>
                <Text style={styles.sectionTitle}>
                  다시 볼 타이밍
                </Text>
                <Text style={styles.moreSectionSubtitle}>
                  날짜, 혜택, 여행, 반복 관심사를 바탕으로 지금 다시 보기 좋은 저장물이에요.
                </Text>
              </View>
            </View>

            {smartRemindersLoading ? (
              <View style={styles.smartReminderLoadingCard}>
                <ActivityIndicator
                  size="small"
                  color={theme.primary}
                />
                <Text style={styles.connectionLoadingText}>
                  다시 볼 저장물을 고르고 있어요.
                </Text>
              </View>
            ) : (
              <View style={styles.smartReminderList}>
                {smartReminders.map((reminder) => (
                  <Pressable
                    key={reminder.key}
                    style={({ pressed }) => [
                      styles.smartReminderCard,
                      pressed && styles.smartReminderCardPressed,
                    ]}
                    onPress={() => openSmartReminder(reminder)}
                  >
                    <View style={styles.smartReminderCardHeader}>
                      <View style={styles.smartReminderIcon}>
                        <Ionicons
                          name={smartReminderIcon(reminder.type)}
                          size={18}
                          color={theme.primary}
                        />
                      </View>

                      <View style={styles.smartReminderHeaderText}>
                        <View style={styles.smartReminderBadge}>
                          <Text style={styles.smartReminderBadgeText}>
                            {reminder.badge}
                          </Text>
                        </View>
                        <Text style={styles.smartReminderTitle}>
                          {reminder.title}
                        </Text>
                      </View>

                      <Ionicons
                        name="chevron-forward"
                        size={17}
                        color={theme.muted}
                      />
                    </View>

                    <Text style={styles.smartReminderDescription}>
                      {reminder.description}
                    </Text>

                    {reminder.evidence.length > 0 && (
                      <View style={styles.smartReminderEvidence}>
                        {reminder.evidence.slice(0, 2).map((item) => (
                          <View
                            key={`${reminder.key}:${item}`}
                            style={styles.smartReminderEvidenceRow}
                          >
                            <Ionicons
                              name="checkmark-circle-outline"
                              size={13}
                              color={theme.primary}
                            />
                            <Text
                              style={styles.smartReminderEvidenceText}
                              numberOfLines={1}
                            >
                              {item}
                            </Text>
                          </View>
                        ))}
                      </View>
                    )}

                    <Text
                      style={styles.smartReminderContentTitle}
                      numberOfLines={1}
                    >
                      {reminder.contentTitle}
                    </Text>
                  </Pressable>
                ))}
              </View>
            )}
          </View>
        )}

        {(contentConflictsLoading ||
          contentConflicts.length > 0) && (
          <View style={styles.moreSection}>
            <View style={styles.moreSectionHeader}>
              <View>
                <Text style={styles.sectionTitle}>
                  확인이 필요한 정보
                </Text>
                <Text style={styles.moreSectionSubtitle}>
                  저장한 콘텐츠끼리 내용이 다른 부분이에요.
                </Text>
              </View>

              {contentConflicts.length > 0 && (
                <View style={styles.conflictCountBadge}>
                  <Text style={styles.conflictCountText}>
                    {contentConflicts.length}
                  </Text>
                </View>
              )}
            </View>

            {contentConflictsLoading ? (
              <View style={styles.emptyBox}>
                <ActivityIndicator
                  size="small"
                  color={theme.primary}
                />
                <Text style={styles.connectionLoadingText}>
                  저장한 정보를 확인하고 있어요.
                </Text>
              </View>
            ) : (
              contentConflicts.map((conflict) => (
                <View
                  key={conflict.key}
                  style={styles.conflictCard}
                >
                  <View style={styles.conflictCardHeader}>
                    <View style={styles.conflictIcon}>
                      <Ionicons
                        name="alert-circle-outline"
                        size={18}
                        color="#A75B36"
                      />
                    </View>

                    <View style={styles.conflictHeaderText}>
                      <Text style={styles.conflictTypeText}>
                        {conflictTypeLabel(conflict.claimType)}
                      </Text>
                      <Text style={styles.conflictTitle}>
                        {conflict.title}
                      </Text>
                    </View>
                  </View>

                  <Text style={styles.conflictDescription}>
                    {conflict.description}
                  </Text>

                  <View style={styles.conflictEvidenceList}>
                    {conflict.evidences
                      .slice(0, 2)
                      .map((evidence, index) => (
                        <Pressable
                          key={`${conflict.key}:${evidence.contentId}`}
                          style={styles.conflictEvidenceCard}
                          onPress={() =>
                            openConflictEvidence(
                              evidence.contentId,
                            )
                          }
                        >
                          <View style={styles.conflictEvidenceIndex}>
                            <Text style={styles.conflictEvidenceIndexText}>
                              {index + 1}
                            </Text>
                          </View>

                          <View style={styles.conflictEvidenceBody}>
                            <Text
                              style={styles.conflictEvidenceTitle}
                              numberOfLines={1}
                            >
                              {evidence.title || '저장한 콘텐츠'}
                            </Text>

                            <Text
                              style={styles.conflictEvidenceClaim}
                              numberOfLines={2}
                            >
                              {evidence.claimText}
                            </Text>
                          </View>

                          <Ionicons
                            name="chevron-forward"
                            size={16}
                            color={theme.muted}
                          />
                        </Pressable>
                      ))}
                  </View>
                </View>
              ))
            )}
          </View>
        )}

        <View style={styles.moreSection}>
          <View style={styles.moreSectionHeader}>
            <View>
              <Text style={styles.sectionTitle}>
                자동으로 묶인 주제
              </Text>
              <Text style={styles.moreSectionSubtitle}>
                비슷한 저장물을 주제별로 모아뒀어요.
              </Text>
            </View>
          </View>

          {smartCollectionsLoading ? (
            <View style={styles.emptyBox}>
              <ActivityIndicator
                size="small"
                color={theme.primary}
              />
              <Text style={styles.connectionLoadingText}>
                저장물을 주제별로 묶고 있어요.
              </Text>
            </View>
          ) : smartCollections.length > 0 ? (
            <View style={styles.moreCollectionGrid}>
              {smartCollections.map((collection) => (
                <Pressable
                  key={collection.key}
                  style={styles.moreCollectionCard}
                  onPress={() =>
                    openSmartCollection(collection)
                  }
                >
                  <View style={styles.smartCollectionTop}>
                    <View style={styles.smartCollectionIcon}>
                      <Ionicons
                        name="albums-outline"
                        size={18}
                        color={theme.primary}
                      />
                    </View>

                    <Text style={styles.smartCollectionCount}>
                      {collection.count}개
                    </Text>
                  </View>

                  <Text
                    style={styles.smartCollectionTitle}
                    numberOfLines={2}
                  >
                    {collection.title}
                  </Text>

                  <Text
                    style={styles.smartCollectionDescription}
                    numberOfLines={3}
                  >
                    {collection.description}
                  </Text>
                </Pressable>
              ))}
            </View>
          ) : (
            <View style={styles.emptyBox}>
              <Text style={styles.emptyText}>
                비슷한 주제의 저장물이 2개 이상 쌓이면 자동으로 모아드려요.
              </Text>
            </View>
          )}
        </View>

        <View style={styles.moreSection}>
          <Text style={styles.sectionTitle}>
            내가 자주 저장한 관심사
          </Text>

          <Text style={styles.moreSectionSubtitle}>
            반복해서 저장한 장소, 브랜드, 제품 등을 모아서 보여줘요.
          </Text>

          <View style={styles.moreConnections}>
            {connectionsLoading ? (
              <View style={styles.emptyBox}>
                <ActivityIndicator
                  size="small"
                  color={theme.primary}
                />
              </View>
            ) : connections.length > 0 ? (
              connections.map((connection) => (
                <Pressable
                  key={`${connection.type}:${connection.entity}`}
                  style={styles.moreConnectionCard}
                  onPress={() =>
                    openConnection(connection)
                  }
                >
                  <View style={styles.moreConnectionIcon}>
                    <Ionicons
                      name={connectionTypeIcon(connection.type)}
                      size={17}
                      color={theme.primary}
                    />
                  </View>

                  <View style={styles.moreConnectionBody}>
                    <Text style={styles.moreConnectionTitle}>
                      {connection.entity}
                    </Text>
                    <Text style={styles.moreConnectionMeta}>
                      {connection.count}개의 저장물에서 함께 나왔어요
                    </Text>
                  </View>

                  <Ionicons
                    name="chevron-forward"
                    size={17}
                    color={theme.muted}
                  />
                </Pressable>
              ))
            ) : (
              <View style={styles.emptyBox}>
                <Text style={styles.emptyText}>
                  같은 장소나 브랜드를 여러 번 저장하면 여기에서 모아볼 수 있어요.
                </Text>
              </View>
            )}
          </View>
        </View>
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
          SAVE:ON
        </Text>

        <Text style={styles.h1}>
          {activeSmartCollection
            ? activeSmartCollection.title
            : connectionFilter
              ? `${connectionFilter.entity} 모아보기`
              : '내 저장물 찾기'}
        </Text>

        {!connectionFilter && !activeSmartCollection && (
          <>
            <Text style={styles.bodyText}>
              검색하거나, 저장해둔 내용에 직접 질문해보세요.
            </Text>

            <View style={styles.searchModeTabs}>
              <Pressable
                style={[
                  styles.searchModeTab,
                  searchMode === 'search' &&
                    styles.searchModeTabActive,
                ]}
                onPress={() => setSearchMode('search')}
              >
                <Ionicons
                  name="search-outline"
                  size={16}
                  color={
                    searchMode === 'search'
                      ? '#FFFFFF'
                      : theme.muted
                  }
                />
                <Text
                  style={[
                    styles.searchModeTabText,
                    searchMode === 'search' &&
                      styles.searchModeTabTextActive,
                  ]}
                >
                  검색
                </Text>
              </Pressable>

              <Pressable
                style={[
                  styles.searchModeTab,
                  searchMode === 'ask' &&
                    styles.searchModeTabActive,
                ]}
                onPress={() => setSearchMode('ask')}
              >
                <Ionicons
                  name="chatbubble-ellipses-outline"
                  size={16}
                  color={
                    searchMode === 'ask'
                      ? '#FFFFFF'
                      : theme.muted
                  }
                />
                <Text
                  style={[
                    styles.searchModeTabText,
                    searchMode === 'ask' &&
                      styles.searchModeTabTextActive,
                  ]}
                >
                  질문
                </Text>
              </Pressable>
            </View>
          </>
        )}

        {activeSmartCollection && (
          <View style={styles.smartCollectionDetail}>
            <View style={styles.smartCollectionDetailHeader}>
              <View style={styles.smartCollectionDetailIcon}>
                <Ionicons
                  name="albums-outline"
                  size={20}
                  color={theme.primary}
                />
              </View>
              <View style={styles.smartCollectionDetailHeaderText}>
                <Text style={styles.smartCollectionDetailEyebrow}>
                  자동 컬렉션
                </Text>
                <Text style={styles.smartCollectionDetailTitle}>
                  {activeSmartCollection.title}
                </Text>
              </View>
            </View>

            <Text style={styles.smartCollectionDetailDescription}>
              {activeSmartCollection.description}
            </Text>

            {activeSmartCollection.categories.length > 0 && (
              <View style={styles.wrapRow}>
                {activeSmartCollection.categories.map((category) => (
                  <View
                    key={`smart-category:${category}`}
                    style={styles.chip}
                  >
                    <Text style={styles.chipText}>
                      {category}
                    </Text>
                  </View>
                ))}
              </View>
            )}

            <Text style={styles.smartCollectionDetailMeta}>
              {activeSmartCollection.count}개의 저장물을 비슷한 주제로 묶었어요.
            </Text>

            <Pressable
              style={styles.collectionCompareButton}
              onPress={runCollectionComparison}
              disabled={collectionComparisonLoading}
            >
              {collectionComparisonLoading ? (
                <ActivityIndicator
                  size="small"
                  color="#FFFFFF"
                />
              ) : (
                <Ionicons
                  name="git-compare-outline"
                  size={17}
                  color="#FFFFFF"
                />
              )}
              <Text style={styles.collectionCompareButtonText}>
                {collectionComparisonLoading
                  ? '비교하는 중...'
                  : collectionComparison
                  ? '비교 다시 보기'
                  : '저장물 비교하기'}
              </Text>
            </Pressable>

            <Text style={styles.collectionCompareHint}>
              같은 제품·장소·브랜드가 여러 저장물에 반복될 때 공통점과 엇갈리는 점을 비교해요. 객관적 수치가 서로 다를 때만 외부 정보를 확인해요.
            </Text>

            {collectionComparisonError && (
              <Text style={styles.collectionCompareError}>
                {collectionComparisonError}
              </Text>
            )}

            {collectionComparison && (
              <View style={styles.collectionComparisonPanel}>
                {!collectionComparison.eligible ? (
                  <View style={styles.collectionCompareNotEligible}>
                    <Ionicons
                      name="albums-outline"
                      size={18}
                      color={theme.muted}
                    />
                    <View style={styles.collectionCompareNotEligibleText}>
                      <Text style={styles.collectionComparisonTitle}>
                        비교보다 모아보기가 더 잘 맞아요
                      </Text>
                      <Text style={styles.collectionComparisonSummary}>
                        {collectionComparison.reason}
                      </Text>
                    </View>
                  </View>
                ) : (
                  <>
                    <View style={styles.collectionComparisonHeader}>
                      <Ionicons
                        name="git-compare-outline"
                        size={18}
                        color={theme.primary}
                      />
                      <View style={styles.collectionComparisonHeaderText}>
                        <Text style={styles.collectionComparisonTitle}>
                          {collectionComparison.title}
                        </Text>
                        <Text style={styles.collectionComparisonEntity}>
                          비교 대상 · {collectionComparison.comparisonEntity}
                        </Text>
                        <Text style={styles.collectionComparisonSummary}>
                          {collectionComparison.summary}
                        </Text>
                      </View>
                    </View>

                    {collectionComparison.disagreements.length > 0 && (
                      <View style={styles.collectionComparisonSection}>
                        <View style={styles.collectionComparisonSectionHeader}>
                          <Ionicons
                            name="swap-horizontal-outline"
                            size={16}
                            color="#A45B3D"
                          />
                          <Text style={styles.collectionComparisonSectionTitle}>
                            엇갈리는 점
                          </Text>
                        </View>
                        <Text style={styles.collectionComparisonSectionHint}>
                          같은 항목을 두고 영상마다 다르게 말한 부분이에요. 어느 쪽이 맞다고 단정하지 않아요.
                        </Text>

                        {collectionComparison.disagreements.map(
                          (finding, index) => (
                            <View
                              key={`disagreement:${index}:${finding.topic}`}
                              style={styles.collectionComparisonDimension}
                            >
                              <Text style={styles.collectionComparisonDimensionTitle}>
                                {finding.topic}
                              </Text>
                              <Text style={styles.collectionComparisonFindingStatement}>
                                {finding.statement}
                              </Text>

                              {finding.evidences.map((evidence) => (
                                <View
                                  key={`disagreement-evidence:${index}:${evidence.contentId}:${evidence.quote}`}
                                  style={styles.collectionComparisonEvidenceCard}
                                >
                                  <Text
                                    style={styles.collectionComparisonItemTitle}
                                    numberOfLines={1}
                                  >
                                    {evidence.title || `저장물 #${evidence.contentId}`}
                                  </Text>
                                  <Text style={styles.collectionComparisonEvidence}>
                                    “{evidence.quote}”
                                  </Text>
                                  {evidence.timestampSeconds !== null && (
                                    <Text style={styles.collectionComparisonTimestamp}>
                                      {Math.floor(evidence.timestampSeconds / 60)}:
                                      {String(
                                        Math.floor(evidence.timestampSeconds % 60),
                                      ).padStart(2, '0')}
                                    </Text>
                                  )}
                                </View>
                              ))}
                            </View>
                          ),
                        )}
                      </View>
                    )}

                    {collectionComparison.commonPoints.length > 0 && (
                      <View style={styles.collectionComparisonSection}>
                        <View style={styles.collectionComparisonSectionHeader}>
                          <Ionicons
                            name="checkmark-circle-outline"
                            size={16}
                            color="#4E816D"
                          />
                          <Text style={styles.collectionComparisonSectionTitle}>
                            공통점
                          </Text>
                        </View>
                        {collectionComparison.commonPoints.map(
                          (finding, index) => (
                            <View
                              key={`common:${index}:${finding.topic}`}
                              style={styles.collectionComparisonDimension}
                            >
                              <Text style={styles.collectionComparisonDimensionTitle}>
                                {finding.topic}
                              </Text>
                              <Text style={styles.collectionComparisonFindingStatement}>
                                {finding.statement}
                              </Text>
                              <Text style={styles.collectionComparisonEvidence}>
                                근거 · {finding.evidences
                                  .map((evidence) => evidence.title)
                                  .filter(Boolean)
                                  .join(' / ')}
                              </Text>
                            </View>
                          ),
                        )}
                      </View>
                    )}

                    {collectionComparison.uniqueMentions.length > 0 && (
                      <View style={styles.collectionComparisonSection}>
                        <View style={styles.collectionComparisonSectionHeader}>
                          <Ionicons
                            name="information-circle-outline"
                            size={16}
                            color={theme.primary}
                          />
                          <Text style={styles.collectionComparisonSectionTitle}>
                            한 영상에만 나온 정보
                          </Text>
                        </View>

                        {collectionComparison.uniqueMentions.map(
                          (finding, index) => (
                            <View
                              key={`unique:${index}:${finding.topic}`}
                              style={styles.collectionComparisonDimension}
                            >
                              <Text style={styles.collectionComparisonDimensionTitle}>
                                {finding.topic}
                              </Text>
                              <Text style={styles.collectionComparisonFindingStatement}>
                                {finding.statement}
                              </Text>
                              {finding.evidences[0] && (
                                <Text style={styles.collectionComparisonEvidence}>
                                  근거 · {finding.evidences[0].title}
                                  {finding.evidences[0].quote
                                    ? ` · “${finding.evidences[0].quote}”`
                                    : ''}
                                </Text>
                              )}
                            </View>
                          ),
                        )}
                      </View>
                    )}

                    {collectionComparison.externalFacts.length > 0 && (
                      <View style={styles.collectionExternalSection}>
                        <View style={styles.collectionExternalHeader}>
                          <Ionicons
                            name="shield-checkmark-outline"
                            size={17}
                            color="#8A651F"
                          />
                          <Text style={styles.collectionExternalTitle}>
                            외부 확인
                          </Text>
                        </View>
                        <Text style={styles.collectionExternalHint}>
                          저장한 영상끼리 가격·날짜·용량 같은 객관 정보가 달랐던 항목만 현재 공식 정보를 확인했어요.
                        </Text>

                        {collectionComparison.externalFacts.map(
                          (fact, factIndex) => (
                            <View
                              key={`external-fact:${factIndex}:${fact.label}`}
                              style={styles.collectionExternalFact}
                            >
                              <View style={styles.collectionExternalFactTop}>
                                <Text style={styles.collectionExternalFactLabel}>
                                  {fact.label}
                                </Text>
                                <View style={styles.collectionExternalStatus}>
                                  <Text style={styles.collectionExternalStatusText}>
                                    {externalFactStatusLabel(fact.status)}
                                  </Text>
                                </View>
                              </View>

                              <Text style={styles.collectionExternalSavedLabel}>
                                저장물에서 나온 정보
                              </Text>
                              <Text style={styles.collectionExternalValue}>
                                {fact.savedValues.join(' / ')}
                              </Text>

                              {!!fact.currentValue && (
                                <>
                                  <Text style={styles.collectionExternalSavedLabel}>
                                    현재 외부 확인
                                  </Text>
                                  <Text style={styles.collectionExternalValue}>
                                    {fact.currentValue}
                                  </Text>
                                </>
                              )}

                              {!!fact.explanation && (
                                <Text style={styles.collectionExternalExplanation}>
                                  {fact.explanation}
                                </Text>
                              )}

                              <Text style={styles.collectionExternalCheckedAt}>
                                확인 시점 · {new Date(fact.checkedAt).toLocaleString('ko-KR')}
                              </Text>

                              {fact.sources.length > 0 && (
                                <View style={styles.collectionExternalSources}>
                                  {fact.sources.slice(0, 3).map((source) => (
                                    <Pressable
                                      key={source.url}
                                      onPress={() =>
                                        Linking.openURL(source.url)
                                      }
                                      style={styles.collectionExternalSource}
                                    >
                                      <Ionicons
                                        name="open-outline"
                                        size={12}
                                        color={theme.primary}
                                      />
                                      <Text
                                        style={styles.collectionExternalSourceText}
                                        numberOfLines={1}
                                      >
                                        {source.title}
                                      </Text>
                                    </Pressable>
                                  ))}
                                </View>
                              )}
                            </View>
                          ),
                        )}
                      </View>
                    )}

                    <View style={styles.collectionComparisonDecisionNote}>
                      <Ionicons
                        name="compass-outline"
                        size={15}
                        color={theme.muted}
                      />
                      <Text style={styles.collectionComparisonDecisionText}>
                        Save:on은 무엇을 사거나 어디를 갈지 대신 결정하지 않고, 저장한 영상의 공통점과 차이를 판단 재료로 정리해요.
                      </Text>
                    </View>
                  </>
                )}
              </View>
            )}
          </View>
        )}

        {connectionFilter && (
          <>
            <Text style={styles.bodyText}>
              내가 저장한 것 중 “{connectionFilter.entity}”이 함께 나온 내용을 모았어요.
            </Text>
            {renderConnectionBundle()}
          </>
        )}

        {!connectionFilter &&
          !activeSmartCollection &&
          searchMode === 'ask' && (
          <View style={styles.knowledgePanel}>
            <View style={styles.knowledgeHeader}>
              <View style={styles.knowledgeIconBubble}>
                <Ionicons
                  name="sparkles-outline"
                  size={18}
                  color={theme.primary}
                />
              </View>

              <View style={styles.knowledgeHeaderText}>
                <Text style={styles.knowledgeTitle}>
                  내 저장물에 질문하기
                </Text>
                <Text style={styles.knowledgeSubtitle}>
                  답변은 내가 저장한 콘텐츠만 근거로 만들어요.
                </Text>
              </View>
            </View>

            <View style={styles.knowledgeInputBox}>
              <TextInput
                value={knowledgeQuestion}
                onChangeText={setKnowledgeQuestion}
                placeholder="예: 내가 저장한 성수 카페 중 빵이 유명한 곳은?"
                placeholderTextColor="#A7ABB4"
                multiline
                autoCorrect={false}
                style={styles.knowledgeInput}
                returnKeyType="send"
                onSubmitEditing={askMySavedContent}
              />

              <Pressable
                style={[
                  styles.knowledgeAskButton,
                  (!knowledgeQuestion.trim() ||
                    knowledgeLoading) &&
                    styles.disabledButton,
                ]}
                disabled={
                  !knowledgeQuestion.trim() ||
                  knowledgeLoading
                }
                onPress={askMySavedContent}
              >
                {knowledgeLoading ? (
                  <ActivityIndicator
                    size="small"
                    color="#FFFFFF"
                  />
                ) : (
                  <Ionicons
                    name="arrow-up"
                    size={18}
                    color="#FFFFFF"
                  />
                )}
              </Pressable>
            </View>

            <View style={styles.questionExamples}>
              {[
                '내가 저장한 성수 카페 중 빵이 유명한 곳은?',
                '올리브영 관련해서 저장한 내용 정리해줘',
                '여행 저장물에서 장소만 알려줘',
              ].map((example) => (
                <Pressable
                  key={example}
                  style={styles.questionExampleChip}
                  onPress={() =>
                    setKnowledgeQuestion(example)
                  }
                >
                  <Text style={styles.questionExampleText}>
                    {example}
                  </Text>
                </Pressable>
              ))}
            </View>

            {knowledgeLoading && (
              <View style={styles.knowledgeLoadingRow}>
                <ActivityIndicator
                  size="small"
                  color={theme.primary}
                />
                <Text style={styles.knowledgeLoadingText}>
                  관련 저장물을 찾고 답변을 정리하고 있어요.
                </Text>
              </View>
            )}

            {knowledgeError && (
              <View style={styles.knowledgeErrorBox}>
                <Text style={styles.knowledgeErrorText}>
                  {knowledgeError}
                </Text>
              </View>
            )}

            {knowledgeAnswer && !knowledgeLoading && (
              <View style={styles.knowledgeAnswerCard}>
                <View style={styles.knowledgeAnswerHeader}>
                  <Ionicons
                    name="chatbubble-outline"
                    size={17}
                    color={theme.primary}
                  />
                  <Text style={styles.knowledgeAnswerLabel}>
                    저장물에서 찾은 답
                  </Text>
                </View>

                <Text style={styles.knowledgeAnswerText}>
                  {knowledgeAnswer.answer}
                </Text>

                {knowledgeAnswer.sources.length > 0 && (
                  <View style={styles.knowledgeSources}>
                    <Text style={styles.knowledgeSourcesTitle}>
                      답변에 참고한 저장물
                    </Text>

                    {knowledgeAnswer.sources.map((source) => (
                      <Pressable
                        key={source.contentId}
                        style={styles.knowledgeSourceCard}
                        onPress={() =>
                          openKnowledgeSource(
                            source.contentId,
                          )
                        }
                      >
                        <View style={styles.knowledgeSourceBody}>
                          <Text
                            style={styles.knowledgeSourceTitle}
                            numberOfLines={2}
                          >
                            {source.title ||
                              '저장한 콘텐츠'}
                          </Text>

                          {source.summary.length > 0 && (
                            <Text
                              style={styles.knowledgeSourceSummary}
                              numberOfLines={2}
                            >
                              {source.summary}
                            </Text>
                          )}
                        </View>

                        <Ionicons
                          name="chevron-forward"
                          size={17}
                          color={theme.muted}
                        />
                      </Pressable>
                    ))}
                  </View>
                )}

                {!knowledgeAnswer.grounded && (
                  <Text style={styles.knowledgeGroundingNote}>
                    충분한 근거가 없으면 저장한 내용 밖의 사실은 추측하지 않아요.
                  </Text>
                )}
              </View>
            )}
          </View>
        )}

        {!connectionFilter &&
          !activeSmartCollection &&
          searchMode === 'search' && (
          <>
            <View style={styles.searchBox}>
              <Ionicons
                name="search-outline"
                size={20}
                color={theme.muted}
              />

              <TextInput
                value={query}
                onChangeText={(text) => {
                  setConnectionFilter(null);
                  setQuery(text);
                }}
                placeholder="예: 성수 데이트 카페, 여름 메이크업"
                placeholderTextColor="#A7ABB4"
                returnKeyType="search"
                autoCorrect={false}
                style={styles.searchInput}
              />

              {query.length > 0 && (
                <Pressable
                  onPress={() => {
                    setConnectionFilter(null);
                    setQuery('');
                  }}
                  hitSlop={8}
                >
                  <Ionicons
                    name="close-circle"
                    size={19}
                    color={theme.muted}
                  />
                </Pressable>
              )}
            </View>

            <Text style={styles.resultText}>
              {searching
                ? '찾고 있어요...'
                : `${searchResults.length}개 찾았어요`}
            </Text>

            {searching ? (
              <View style={styles.searchState}>
                <ActivityIndicator
                  size="small"
                  color={theme.primary}
                />
                <Text style={styles.searchStateText}>
                  비슷한 내용까지 함께 찾고 있어요.
                </Text>
              </View>
            ) : searchError ? (
              <View style={styles.emptyBox}>
                <Text style={styles.emptyText}>
                  {searchError}
                </Text>
              </View>
            ) : searchResults.length === 0 ? (
              <View style={styles.emptyBox}>
                <Text style={styles.emptyText}>
                  아직 맞는 저장물을 찾지 못했어요. 다른 표현으로 한 번 더 검색해보세요.
                </Text>
              </View>
            ) : (
              searchResults.map((item) => (
                <ContentCard
                  key={item.id}
                  item={item}
                  onPress={() =>
                    openDetail(item.id, 'search')
                  }
                />
              ))
            )}
          </>
        )}

        {activeSmartCollection && (
          <>
            <Text style={styles.relatedContentsTitle}>
              이 주제의 저장물
            </Text>

            <Text style={styles.resultText}>
              {searchResults.length}개의 저장물
            </Text>

            {searchResults.map((item) => (
              <ContentCard
                key={item.id}
                item={item}
                onPress={() =>
                  openDetail(item.id, 'search')
                }
              />
            ))}
          </>
        )}

        {connectionFilter && (
          <>
            <Text style={styles.relatedContentsTitle}>
              관련 저장물
            </Text>

            <Text style={styles.resultText}>
              {searching
                ? '찾고 있어요...'
                : `${searchResults.length}개의 관련 저장물`}
            </Text>

            {searchResults.map((item) => (
              <ContentCard
                key={item.id}
                item={item}
                onPress={() =>
                  openDetail(item.id, 'search')
                }
              />
            ))}
          </>
        )}
      </ScrollView>
    );
  }

  function renderDetail() {
    if (!detailItem) return null;

    const canOpenSource =
      detailItem.sourceUrl?.startsWith('http');

    const savedEntities =
      parseCorrectionEntities(
        detailRawContent?.structuredAnalysis,
      );

    let structuredDetail: any = {};
    try {
      structuredDetail = detailRawContent?.structuredAnalysis
        ? JSON.parse(detailRawContent.structuredAnalysis)
        : {};
    } catch (error) {
      console.error('❌ structuredAnalysis 상세 파싱 오류:', error);
    }

    const detailFactChecks = Array.isArray(
      structuredDetail?.factChecks,
    )
      ? structuredDetail.factChecks
      : [];
    const verificationStatus = String(
      structuredDetail?.verificationStatus ?? '',
    ).toUpperCase();
    const verificationCorrections = Array.isArray(
      structuredDetail?.corrections,
    )
      ? structuredDetail.corrections
      : [];
    const unverifiedNotes = Array.isArray(
      structuredDetail?.unverifiedNotes,
    )
      ? structuredDetail.unverifiedNotes
      : [];

    const evidenceReviewMessages = Array.from(
      new Set([
        ...(contentQuality?.warnings ?? []).map((warning) =>
          qualityMessage(warning.type),
        ),
        ...detailFactChecks
          .filter((check: any) =>
            ['CONFLICTING', 'PARTIALLY_SUPPORTED', 'INSUFFICIENT_EVIDENCE'].includes(
              String(check?.verdict ?? '').toUpperCase(),
            ),
          )
          .map((check: any) => {
            const verdict = String(
              check?.verdict ?? '',
            ).toUpperCase();
            if (verdict === 'CONFLICTING') {
              return '외부 근거와 내용이 다른 정보가 있어요.';
            }
            if (verdict === 'PARTIALLY_SUPPORTED') {
              return '일부 내용만 근거로 확인됐어요.';
            }
            return '충분한 근거를 찾지 못한 정보가 있어요.';
          }),
        ...(verificationCorrections.length > 0
          ? ['검증 과정에서 바로잡은 정보가 있어요.']
          : []),
        ...(unverifiedNotes.length > 0
          ? ['아직 확인되지 않은 내용이 포함되어 있어요.']
          : []),
      ]),
    ).slice(0, 3);

    const needsEvidenceReview =
      Boolean(contentQuality?.requiresReview) ||
      ['PARTIALLY_VERIFIED', 'INSUFFICIENT_EVIDENCE'].includes(
        verificationStatus,
      ) ||
      evidenceReviewMessages.length > 0;

    const backLabel =
      detailReturnTab === 'home'
        ? '홈'
        : detailReturnTab === 'search'
          ? '검색'
          : '내 저장물';

    return (
      <ScrollView contentContainerStyle={styles.page}>
        <Pressable
          style={styles.backButton}
          onPress={() => goTab(detailReturnTab)}
        >
          <Ionicons
            name="chevron-back"
            size={22}
            color={theme.text}
          />
          <Text style={styles.backText}>
            {backLabel}
          </Text>
        </Pressable>

        <View style={styles.detailHero}>
          <View style={styles.detailPlatformRow}>
            <Text style={styles.detailEmoji}>
              {detailItem.thumbnailEmoji}
            </Text>

            <Text style={styles.platformBadge}>
              {detailItem.platform}
            </Text>
          </View>

          {detailRawContent?.status === 'COMPLETED' &&
            (detailItem.category.length > 0 ||
              savedEntities.length > 0) && (
              <View style={styles.detailMetaCard}>
                <View style={styles.detailMetaHeader}>
                  <Ionicons
                    name="information-circle-outline"
                    size={18}
                    color={theme.primary}
                  />
                  <Text style={styles.detailMetaTitle}>
                    콘텐츠 정보
                  </Text>

                  {!analysisEditing && (
                    <Pressable
                      style={styles.detailMetaEditButton}
                      onPress={() =>
                        beginAnalysisCorrection('info')
                      }
                    >
                      <Text style={styles.detailMetaEditText}>
                        수정
                      </Text>
                    </Pressable>
                  )}
                </View>

                {detailItem.category.length > 0 && (
                  <View style={styles.detailMetaRow}>
                    <Text style={styles.detailMetaLabel}>
                      분류
                    </Text>
                    <View style={styles.detailMetaValues}>
                      {detailItem.category.map((tag) => (
                        <View
                          key={tag}
                          style={styles.detailMetaChip}
                        >
                          <Text style={styles.detailMetaChipText}>
                            {tag}
                          </Text>
                        </View>
                      ))}
                    </View>
                  </View>
                )}

                {savedEntities.length > 0 && (
                  <View style={styles.detailMetaRow}>
                    <Text style={styles.detailMetaLabel}>
                      주요 정보
                    </Text>
                    <View style={styles.detailMetaValues}>
                      {savedEntities.slice(0, 5).map(
                        (entity, index) => (
                          <View
                            key={`${entity.type}:${entity.name}:${index}`}
                            style={styles.detailEntityChip}
                          >
                            <Ionicons
                              name={entityTypeIcon(entity.type)}
                              size={13}
                              color={theme.primary}
                            />
                            <Text style={styles.detailEntityChipText}>
                              {entity.name}
                            </Text>
                          </View>
                        ),
                      )}
                    </View>
                  </View>
                )}

                {detailRawContent?.userEdited && (
                  <View style={styles.detailMetaEdited}>
                    <Ionicons
                      name="checkmark-circle-outline"
                      size={13}
                      color={theme.primary}
                    />
                    <Text style={styles.detailMetaEditedText}>
                      내가 확인해 수정한 정보가 반영되어 있어요.
                    </Text>
                  </View>
                )}
              </View>
            )}

          <Text style={styles.detailTitle}>
            {detailItem.title}
          </Text>
        </View>

        {detailRawContent?.status === 'FAILED' && (
          <View style={styles.retryPanel}>
            <View style={styles.retryHeader}>
              <Ionicons
                name="refresh-circle-outline"
                size={20}
                color={theme.accent}
              />
              <Text style={styles.retryTitle}>
                내용을 정리하지 못했어요
              </Text>
            </View>

            <Text style={styles.retryBody}>
              원본 콘텐츠 상태에 따라 일시적으로 실패할 수 있어요. 저장물은 그대로 남아 있어요.
            </Text>

            <Pressable
              style={styles.retryButton}
              onPress={retryDetailAnalysis}
            >
              <Text style={styles.retryButtonText}>
                다시 정리하기
              </Text>
            </Pressable>
          </View>
        )}

        {detailRawContent?.status === 'ANALYZING' && (
          <View style={styles.processingPanel}>
            <ActivityIndicator
              size="small"
              color={theme.primary}
            />
            <View style={styles.processingPanelText}>
              <Text style={styles.processingPanelTitle}>
                내용을 정리하고 있어요
              </Text>
              <Text style={styles.processingPanelBody}>
                앱을 나가도 괜찮아요. 끝나면 이 화면에 자동으로 반영돼요.
              </Text>
            </View>
          </View>
        )}

        {detailRawContent?.status === 'COMPLETED' && (
          <>
            <View style={styles.userSection}>
              <View style={styles.userSectionHeader}>
                <View>
                  <Text style={styles.userSectionEyebrow}>
                    AI가 정리한 내용
                  </Text>
                  <Text style={styles.userSectionTitle}>
                    핵심만 빠르게 보기
                  </Text>
                </View>

                {!analysisEditing && (
                  <Pressable
                    style={styles.inlineEditButton}
                    onPress={() =>
                      beginAnalysisCorrection('summary')
                    }
                  >
                    <Text style={styles.inlineEditText}>
                      수정
                    </Text>
                  </Pressable>
                )}
              </View>

              <Text style={styles.detailSummaryText}>
                {detailItem.summary}
              </Text>
            </View>


            {analysisEditing && correctionDraft && (
              <View style={styles.correctionEditor}>
                <View style={styles.correctionEditorHeader}>
                  <View>
                    <Text style={styles.correctionEditorTitle}>
                      {correctionFocus === 'summary'
                        ? '정리된 내용 수정'
                        : '저장된 정보 수정'}
                    </Text>
                    <Text style={styles.correctionEditorSubtitle}>
                      필요한 부분만 바꾸면 돼요.
                    </Text>
                  </View>

                  <Pressable
                    onPress={() => {
                      setAnalysisEditing(false);
                      setCorrectionFocus(null);
                      setCorrectionDraft(null);
                    }}
                    hitSlop={8}
                  >
                    <Ionicons
                      name="close-outline"
                      size={22}
                      color={theme.muted}
                    />
                  </Pressable>
                </View>

                {correctionFocus === 'summary' ? (
                  <>
                    <Text style={styles.correctionLabel}>
                      제목
                    </Text>
                    <TextInput
                      style={styles.correctionInput}
                      value={correctionDraft.title}
                      onChangeText={(value) =>
                        setCorrectionDraft((current) =>
                          current
                            ? { ...current, title: value }
                            : current,
                        )
                      }
                    />

                    <Text style={styles.correctionLabel}>
                      내용 요약
                    </Text>
                    <TextInput
                      style={[
                        styles.correctionInput,
                        styles.correctionMultiline,
                      ]}
                      multiline
                      value={correctionDraft.summary}
                      onChangeText={(value) =>
                        setCorrectionDraft((current) =>
                          current
                            ? { ...current, summary: value }
                            : current,
                        )
                      }
                    />
                  </>
                ) : (
                  <>
                    <Text style={styles.correctionLabel}>
                      어떤 내용인가요?
                    </Text>

                    <View style={styles.categoryChoiceWrap}>
                      {correctionCategories.map((category) => {
                        const selected =
                          correctionDraft.categories.includes(
                            category,
                          );

                        return (
                          <Pressable
                            key={category}
                            style={[
                              styles.categoryChoice,
                              selected &&
                                styles.categoryChoiceSelected,
                            ]}
                            onPress={() =>
                              toggleCorrectionCategory(
                                category,
                              )
                            }
                          >
                            <Text
                              style={[
                                styles.categoryChoiceText,
                                selected &&
                                  styles.categoryChoiceTextSelected,
                              ]}
                            >
                              {category}
                            </Text>
                          </Pressable>
                        );
                      })}
                    </View>

                    <View style={styles.correctionEntityHeader}>
                      <View>
                        <Text style={styles.correctionLabel}>
                          저장된 주요 정보
                        </Text>
                        <Text style={styles.correctionHint}>
                          장소·브랜드·제품처럼 나중에 다시 찾을 때 중요한 정보예요.
                        </Text>
                      </View>

                      <Pressable
                        onPress={addCorrectionEntity}
                      >
                        <Text style={styles.addEntityText}>
                          + 추가
                        </Text>
                      </Pressable>
                    </View>

                    {correctionDraft.entityDetails.map(
                      (entity, index) => (
                        <View
                          key={`correction-entity-${index}`}
                          style={styles.correctionEntityCard}
                        >
                          <View style={styles.correctionEntityTop}>
                            <TextInput
                              style={[
                                styles.correctionInput,
                                styles.correctionEntityNameInput,
                              ]}
                              value={entity.name}
                              placeholder="이름"
                              onChangeText={(value) =>
                                updateCorrectionEntity(
                                  index,
                                  { name: value },
                                )
                              }
                            />

                            <Pressable
                              onPress={() =>
                                removeCorrectionEntity(index)
                              }
                              hitSlop={8}
                            >
                              <Ionicons
                                name="trash-outline"
                                size={18}
                                color={theme.muted}
                              />
                            </Pressable>
                          </View>

                          <Text style={styles.entityChoiceQuestion}>
                            이 정보는 무엇인가요?
                          </Text>

                          <View style={styles.entityTypeWrap}>
                            {correctionEntityTypes.map(
                              (type) => (
                                <Pressable
                                  key={`${index}:${type}`}
                                  style={[
                                    styles.entityTypeChip,
                                    entity.type === type &&
                                      styles.entityTypeChipActive,
                                  ]}
                                  onPress={() =>
                                    updateCorrectionEntity(
                                      index,
                                      { type },
                                    )
                                  }
                                >
                                  <Text
                                    style={[
                                      styles.entityTypeChipText,
                                      entity.type === type &&
                                        styles.entityTypeChipTextActive,
                                    ]}
                                  >
                                    {entityTypeLabel(type)}
                                  </Text>
                                </Pressable>
                              ),
                            )}
                          </View>
                        </View>
                      ),
                    )}
                  </>
                )}

                <Pressable
                  style={styles.correctionSaveButtonFull}
                  disabled={correctionSaving}
                  onPress={saveAnalysisCorrection}
                >
                  {correctionSaving ? (
                    <ActivityIndicator
                      size="small"
                      color="#FFFFFF"
                    />
                  ) : (
                    <Text style={styles.correctionSaveText}>
                      저장하기
                    </Text>
                  )}
                </Pressable>
              </View>
            )}

            {!qualityLoading && needsEvidenceReview && (
              <View style={styles.evidenceReviewCard}>
                <View style={styles.evidenceReviewHeader}>
                  <View style={styles.evidenceReviewIcon}>
                    <Ionicons
                      name="warning-outline"
                      size={18}
                      color="#A76500"
                    />
                  </View>

                  <View style={styles.evidenceReviewHeaderText}>
                    <Text style={styles.evidenceReviewTitle}>
                      확인 필요한 정보
                    </Text>
                    <Text style={styles.evidenceReviewSubtitle}>
                      일부 내용은 근거가 부족하거나 서로 다를 수 있어요.
                    </Text>
                  </View>

                  <View style={styles.evidenceReviewBadge}>
                    <Text style={styles.evidenceReviewBadgeText}>
                      검토 필요
                    </Text>
                  </View>
                </View>

                {evidenceReviewMessages.length > 0 && (
                  <View style={styles.evidenceReviewMessages}>
                    {evidenceReviewMessages.map((message) => (
                      <View
                        key={message}
                        style={styles.evidenceReviewMessageRow}
                      >
                        <View style={styles.evidenceReviewDot} />
                        <Text style={styles.evidenceReviewMessage}>
                          {message}
                        </Text>
                      </View>
                    ))}
                  </View>
                )}

                <Text style={styles.evidenceSourceLabel}>
                  근거/출처
                </Text>

                <View style={styles.evidenceSourceWrap}>
                  <View style={styles.evidenceSourceChip}>
                    <Ionicons
                      name="sparkles-outline"
                      size={14}
                      color={theme.primary}
                    />
                    <Text style={styles.evidenceSourceText}>
                      AI 분석 결과
                    </Text>
                  </View>

                  {detailFactChecks.length > 0 && (
                    <View style={styles.evidenceSourceChip}>
                      <Ionicons
                        name="shield-checkmark-outline"
                        size={14}
                        color={theme.primary}
                      />
                      <Text style={styles.evidenceSourceText}>
                        사실 검증 {detailFactChecks.length}건
                      </Text>
                    </View>
                  )}

                  {canOpenSource && (
                    <View style={styles.evidenceSourceChip}>
                      <Ionicons
                        name="link-outline"
                        size={14}
                        color={theme.primary}
                      />
                      <Text style={styles.evidenceSourceText}>
                        원본 콘텐츠
                      </Text>
                    </View>
                  )}

                  {detailRawContent?.userEdited && (
                    <View style={styles.evidenceSourceChip}>
                      <Ionicons
                        name="person-circle-outline"
                        size={14}
                        color={theme.primary}
                      />
                      <Text style={styles.evidenceSourceText}>
                        사용자 수정 반영
                      </Text>
                    </View>
                  )}
                </View>

                <View style={styles.evidenceReviewActions}>
                  <Pressable
                    style={styles.evidenceEditButton}
                    onPress={() =>
                      beginAnalysisCorrection('info')
                    }
                  >
                    <Text style={styles.evidenceEditButtonText}>
                      직접 고치기
                    </Text>
                  </Pressable>

                  {canOpenSource && (
                    <Pressable
                      style={styles.evidenceSourceButton}
                      onPress={() =>
                        Linking.openURL(
                          detailItem.sourceUrl!,
                        )
                      }
                    >
                      <Ionicons
                        name="open-outline"
                        size={15}
                        color="#FFFFFF"
                      />
                      <Text style={styles.evidenceSourceButtonText}>
                        원본 보기
                      </Text>
                    </Pressable>
                  )}
                </View>
              </View>
            )}

            {renderActionAgentPanel(
              '저장한 내용을 바탕으로 지금 바로 쓸 수 있는 기능이에요.',
            )}
          </>
        )}

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
              원본 보기
            </Text>
          </Pressable>
        )}
      </ScrollView>
    );
  }

  const activeTab =
    screen.name === 'detail'
      ? detailReturnTab
      : screen.name;

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="dark-content" />

      <View style={styles.content}>
        {screen.name === 'home' && renderHome()}
        {screen.name === 'save' && renderSave()}
        {screen.name === 'library' && renderLibrary()}
        {screen.name === 'search' && renderSearch()}
        {screen.name === 'more' && renderMore()}
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
  connectionCardTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  connectionTypeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  connectionTypeText: {
    color: theme.primary,
    fontSize: 11,
    fontWeight: '800',
  },
  connectionLinkText: {
    marginTop: 10,
    color: theme.primary,
    fontSize: 12,
    fontWeight: '800',
  },
  connectionLoadingText: {
    marginTop: 9,
    color: theme.muted,
    fontSize: 12,
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
  searchState: {
    minHeight: 72,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  searchStateText: {
    color: theme.muted,
    fontSize: 13,
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
    fontSize: 26,
  },
  platformBadge: {
    color: theme.primary,
    fontSize: 12,
    fontWeight: '800',
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
  bundlePanel: {
    marginTop: 18,
    backgroundColor: theme.card,
    borderRadius: 22,
    padding: 18,
    borderWidth: 1,
    borderColor: theme.line,
  },
  bundleHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  bundleIconBubble: {
    width: 42,
    height: 42,
    borderRadius: 14,
    backgroundColor: theme.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  bundleHeaderText: {
    flex: 1,
  },
  bundleEyebrow: {
    color: theme.primary,
    fontSize: 11,
    fontWeight: '900',
    marginBottom: 3,
  },
  bundleTitle: {
    color: theme.text,
    fontSize: 21,
    fontWeight: '900',
  },
  bundleMeta: {
    color: theme.muted,
    fontSize: 12,
    marginTop: 3,
  },
  bundleOverview: {
    color: theme.text,
    fontSize: 14,
    lineHeight: 21,
    marginTop: 16,
  },
  agentPanel: {
    marginTop: 16,
    padding: 14,
    borderRadius: 16,
    backgroundColor: theme.primarySoft,
  },
  agentHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 10,
  },
  agentHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    flex: 1,
  },
  agentTitle: {
    color: theme.text,
    fontSize: 12,
    fontWeight: '900',
  },
  agentSourceBadge: {
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: 999,
  },
  agentSourceBadgeActive: {
    backgroundColor: theme.card,
  },
  agentSourceBadgeFallback: {
    backgroundColor: '#F1F1F5',
  },
  agentSourceText: {
    fontSize: 10,
    fontWeight: '900',
  },
  agentSourceTextActive: {
    color: theme.primary,
  },
  agentSourceTextFallback: {
    color: theme.muted,
  },
  agentSummary: {
    color: theme.text,
    fontSize: 14,
    lineHeight: 21,
    marginTop: 12,
    fontWeight: '700',
  },
  agentSubsection: {
    marginTop: 14,
  },
  agentSubsectionTitle: {
    color: theme.muted,
    fontSize: 11,
    fontWeight: '900',
    marginBottom: 8,
  },
  agentInterestPill: {
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 999,
    backgroundColor: theme.card,
  },
  agentInterestText: {
    color: theme.primary,
    fontSize: 11,
    fontWeight: '800',
  },
  agentTakeawayRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    marginTop: 7,
  },
  agentBullet: {
    width: 5,
    height: 5,
    borderRadius: 999,
    backgroundColor: theme.primary,
    marginTop: 7,
  },
  agentTakeawayText: {
    color: theme.text,
    fontSize: 12,
    lineHeight: 18,
    flex: 1,
  },
  actionAgentPanel: {
    marginTop: 12,
    padding: 14,
    borderRadius: 16,
    backgroundColor: '#F4F9F7',
    borderWidth: 1,
    borderColor: '#DCEDE5',
  },
  actionAgentIntro: {
    color: theme.muted,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 9,
    marginBottom: 4,
  },
  actionLoadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 10,
  },
  actionLoadingText: {
    color: theme.muted,
    fontSize: 12,
  },
  actionErrorText: {
    color: theme.muted,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 10,
  },
  actionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginTop: 10,
    padding: 12,
    borderRadius: 14,
    backgroundColor: theme.card,
    borderWidth: 1,
    borderColor: theme.line,
  },
  actionIconBubble: {
    width: 36,
    height: 36,
    borderRadius: 12,
    backgroundColor: '#ECF8F2',
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionCardBody: {
    flex: 1,
  },
  actionTitle: {
    color: theme.text,
    fontSize: 13,
    fontWeight: '900',
  },
  actionDescription: {
    color: theme.muted,
    fontSize: 11,
    lineHeight: 16,
    marginTop: 3,
  },
  actionQuery: {
    color: theme.accent,
    fontSize: 10,
    fontWeight: '800',
    marginTop: 5,
  },
  checklistPanel: {
    marginTop: 12,
    padding: 14,
    borderRadius: 16,
    backgroundColor: theme.surface,
    borderWidth: 1,
    borderColor: theme.border,
  },
  checklistHeaderRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  checklistEyebrow: {
    fontSize: 11,
    fontWeight: '700',
    color: theme.primary,
    marginBottom: 3,
  },
  checklistTitle: {
    fontSize: 15,
    fontWeight: '800',
    color: theme.text,
  },
  checklistRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 9,
    paddingVertical: 7,
  },
  checklistItemText: {
    flex: 1,
    fontSize: 13,
    lineHeight: 19,
    color: theme.text,
  },
  checklistItemTextChecked: {
    color: theme.muted,
    textDecorationLine: 'line-through',
  },
  bundleSection: {
    marginTop: 18,
  },
  bundleSectionTitle: {
    color: theme.text,
    fontSize: 13,
    fontWeight: '900',
    marginBottom: 9,
  },
  bundleCategoryPill: {
    paddingHorizontal: 11,
    paddingVertical: 7,
    borderRadius: 999,
    backgroundColor: '#F1F1F5',
  },
  bundleCategoryText: {
    color: theme.text,
    fontSize: 11,
    fontWeight: '800',
  },
  bundleTagPill: {
    paddingHorizontal: 11,
    paddingVertical: 7,
    borderRadius: 999,
    backgroundColor: theme.primarySoft,
  },
  bundleTagText: {
    color: theme.primary,
    fontSize: 11,
    fontWeight: '800',
  },
  relatedEntityRow: {
    minHeight: 38,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: theme.line,
  },
  relatedEntityLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    flex: 1,
  },
  relatedEntityName: {
    color: theme.text,
    fontSize: 13,
    fontWeight: '800',
  },
  relatedEntityCount: {
    color: theme.muted,
    fontSize: 11,
  },
  highlightCard: {
    paddingVertical: 11,
    borderTopWidth: 1,
    borderTopColor: theme.line,
  },
  highlightTitle: {
    color: theme.text,
    fontSize: 13,
    fontWeight: '900',
    marginBottom: 5,
  },
  highlightSummary: {
    color: theme.muted,
    fontSize: 12,
    lineHeight: 18,
  },
  bundleLoadingRow: {
    minHeight: 54,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
  },
  bundleLoadingText: {
    color: theme.muted,
    fontSize: 12,
    flex: 1,
  },
  bundleErrorText: {
    color: theme.muted,
    fontSize: 12,
    lineHeight: 18,
  },
  relatedContentsTitle: {
    color: theme.text,
    fontSize: 18,
    fontWeight: '900',
    marginTop: 24,
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
  qualityPanel: {
    marginBottom: 14,
    padding: 14,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surface,
  },
  qualityHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  qualityHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
  },
  qualityTitle: {
    fontSize: 14,
    fontWeight: '800',
    color: theme.text,
  },
  qualityBody: {
    fontSize: 12,
    lineHeight: 18,
    color: theme.muted,
  },
  qualityWarnings: {
    gap: 5,
  },
  qualityWarningText: {
    fontSize: 12,
    lineHeight: 18,
    color: '#8A5200',
  },
  userEditedBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: '#EEF7EE',
  },
  userEditedText: {
    fontSize: 10,
    fontWeight: '700',
    color: theme.primary,
  },
  analysisEditButton: {
    marginTop: 11,
    minHeight: 40,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: theme.border,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  analysisEditButtonText: {
    fontSize: 13,
    fontWeight: '700',
    color: theme.primary,
  },
  correctionEditor: {
    marginBottom: 16,
    padding: 15,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surface,
  },
  correctionEditorTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: theme.text,
    marginBottom: 14,
  },
  correctionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: theme.text,
    marginBottom: 6,
    marginTop: 8,
  },
  correctionInput: {
    minHeight: 42,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 13,
    color: theme.text,
    backgroundColor: theme.bg,
  },
  correctionMultiline: {
    minHeight: 92,
    textAlignVertical: 'top',
  },
  correctionEntityHeader: {
    marginTop: 8,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  addEntityText: {
    fontSize: 12,
    fontWeight: '800',
    color: theme.primary,
  },
  correctionEntityCard: {
    marginTop: 8,
    padding: 10,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 14,
    backgroundColor: theme.bg,
  },
  correctionEntityTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  correctionEntityNameInput: {
    flex: 1,
  },
  entityTypeWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 9,
  },
  entityTypeChip: {
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: theme.border,
  },
  entityTypeChipActive: {
    borderColor: theme.primary,
    backgroundColor: '#EEF7EE',
  },
  entityTypeChipText: {
    fontSize: 10,
    fontWeight: '700',
    color: theme.muted,
  },
  entityTypeChipTextActive: {
    color: theme.primary,
  },
  correctionButtons: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 16,
  },
  correctionCancelButton: {
    flex: 1,
    minHeight: 44,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
  },
  correctionCancelText: {
    fontSize: 13,
    fontWeight: '700',
    color: theme.text,
  },
  correctionSaveButton: {
    flex: 1,
    minHeight: 44,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: theme.primary,
  },
  correctionSaveText: {
    fontSize: 13,
    fontWeight: '800',
    color: '#FFFFFF',
  },

  onboardingCard: {
    marginBottom: 28,
    padding: 18,
    borderRadius: 20,
    backgroundColor: theme.surface,
    borderWidth: 1,
    borderColor: theme.border,
  },
  onboardingTitle: {
    fontSize: 16,
    fontWeight: '900',
    color: theme.text,
    marginBottom: 14,
  },
  onboardingStep: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    marginBottom: 10,
  },
  onboardingNumber: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: theme.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  onboardingNumberText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '900',
  },
  onboardingStepText: {
    flex: 1,
    color: theme.text,
    fontSize: 13,
    lineHeight: 20,
  },
  saveNotice: {
    marginTop: 16,
    marginBottom: 6,
    flexDirection: 'row',
    gap: 8,
    padding: 13,
    borderRadius: 14,
    backgroundColor: '#EEF7EE',
  },
  saveNoticeText: {
    flex: 1,
    color: theme.text,
    fontSize: 12,
    lineHeight: 18,
  },
  actionCardPrimary: {
    backgroundColor: theme.accent,
    borderColor: theme.accent,
  },
  actionIconBubblePrimary: {
    backgroundColor: 'rgba(255,255,255,0.18)',
  },
  actionTitlePrimary: {
    color: '#FFFFFF',
  },
  actionDescriptionPrimary: {
    color: 'rgba(255,255,255,0.82)',
  },
  actionQueryPrimary: {
    color: 'rgba(255,255,255,0.76)',
  },
  relatedEntityTypeText: {
    marginTop: 2,
    color: theme.muted,
    fontSize: 10,
  },
  retryPanel: {
    marginBottom: 16,
    padding: 16,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#F0D9D5',
    backgroundColor: '#FFF7F5',
  },
  retryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
  },
  retryTitle: {
    color: theme.text,
    fontSize: 15,
    fontWeight: '800',
  },
  retryBody: {
    marginTop: 8,
    color: theme.muted,
    fontSize: 12,
    lineHeight: 18,
  },
  retryButton: {
    marginTop: 12,
    minHeight: 42,
    borderRadius: 12,
    backgroundColor: theme.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  retryButtonText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '800',
  },
  detailPlatformRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  detailMetaCard: {
    marginBottom: 18,
    padding: 14,
    borderRadius: 17,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: '#FAFAFD',
  },
  detailMetaHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 4,
  },
  detailMetaTitle: {
    flex: 1,
    color: theme.text,
    fontSize: 13,
    fontWeight: '900',
  },
  detailMetaEditButton: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: '#FFFFFF',
  },
  detailMetaEditText: {
    color: theme.primary,
    fontSize: 10,
    fontWeight: '800',
  },
  detailMetaRow: {
    paddingTop: 10,
    paddingBottom: 2,
    borderTopWidth: 1,
    borderTopColor: theme.line,
  },
  detailMetaLabel: {
    marginBottom: 7,
    color: theme.muted,
    fontSize: 10,
    fontWeight: '800',
  },
  detailMetaValues: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 7,
  },
  detailMetaChip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: '#DDD9F8',
    backgroundColor: '#F4F1FF',
  },
  detailMetaChipText: {
    color: theme.primary,
    fontSize: 10,
    fontWeight: '800',
  },
  detailEntityChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: '#DDD9F8',
    backgroundColor: '#FFFFFF',
  },
  detailEntityChipText: {
    color: theme.text,
    fontSize: 10,
    fontWeight: '800',
  },
  detailMetaEdited: {
    marginTop: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  detailMetaEditedText: {
    color: theme.primary,
    fontSize: 9,
    fontWeight: '700',
  },
  evidenceReviewCard: {
    marginBottom: 16,
    padding: 15,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#F0D9A8',
    backgroundColor: '#FFF9ED',
  },
  evidenceReviewHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 9,
  },
  evidenceReviewIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFF0CF',
  },
  evidenceReviewHeaderText: {
    flex: 1,
  },
  evidenceReviewTitle: {
    color: theme.text,
    fontSize: 14,
    fontWeight: '900',
  },
  evidenceReviewSubtitle: {
    marginTop: 3,
    color: theme.muted,
    fontSize: 11,
    lineHeight: 16,
  },
  evidenceReviewBadge: {
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: 999,
    backgroundColor: '#FFF0CF',
  },
  evidenceReviewBadgeText: {
    color: '#8A5A00',
    fontSize: 9,
    fontWeight: '900',
  },
  evidenceReviewMessages: {
    marginTop: 12,
    padding: 11,
    gap: 7,
    borderRadius: 13,
    backgroundColor: '#FFF3D9',
  },
  evidenceReviewMessageRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 7,
  },
  evidenceReviewDot: {
    width: 5,
    height: 5,
    marginTop: 7,
    borderRadius: 3,
    backgroundColor: '#D58A00',
  },
  evidenceReviewMessage: {
    flex: 1,
    color: '#755013',
    fontSize: 11,
    lineHeight: 17,
  },
  evidenceSourceLabel: {
    marginTop: 13,
    marginBottom: 8,
    color: theme.text,
    fontSize: 11,
    fontWeight: '900',
  },
  evidenceSourceWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 7,
  },
  evidenceSourceChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 9,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: '#E7D8B8',
    backgroundColor: '#FFFFFF',
  },
  evidenceSourceText: {
    color: theme.text,
    fontSize: 9,
    fontWeight: '700',
  },
  evidenceReviewActions: {
    marginTop: 13,
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
  },
  evidenceEditButton: {
    minHeight: 38,
    paddingHorizontal: 13,
    borderRadius: 11,
    borderWidth: 1,
    borderColor: '#E9C677',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFFFFF',
  },
  evidenceEditButtonText: {
    color: '#8A5A00',
    fontSize: 11,
    fontWeight: '800',
  },
  evidenceSourceButton: {
    minHeight: 38,
    paddingHorizontal: 13,
    borderRadius: 11,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    backgroundColor: theme.primary,
  },
  evidenceSourceButtonText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '800',
  },
  processingPanel: {
    marginBottom: 16,
    padding: 15,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surface,
    flexDirection: 'row',
    gap: 12,
    alignItems: 'center',
  },
  processingPanelText: {
    flex: 1,
  },
  processingPanelTitle: {
    color: theme.text,
    fontSize: 14,
    fontWeight: '800',
  },
  processingPanelBody: {
    marginTop: 3,
    color: theme.muted,
    fontSize: 12,
    lineHeight: 17,
  },
  userSection: {
    marginBottom: 16,
    padding: 16,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surface,
  },
  userSectionHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 12,
  },
  userSectionEyebrow: {
    color: theme.primary,
    fontSize: 11,
    fontWeight: '800',
    marginBottom: 4,
  },
  userSectionTitle: {
    color: theme.text,
    fontSize: 15,
    fontWeight: '900',
  },
  inlineEditButton: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: theme.border,
  },
  inlineEditText: {
    color: theme.primary,
    fontSize: 11,
    fontWeight: '800',
  },
  detailSummaryText: {
    marginTop: 12,
    color: theme.text,
    fontSize: 14,
    lineHeight: 22,
  },
  reviewCard: {
    marginBottom: 16,
    padding: 15,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#F0D9A8',
    backgroundColor: '#FFF9ED',
  },
  reviewHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  reviewIconBubble: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: '#FFF0CF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  reviewHeaderText: {
    flex: 1,
  },
  reviewTitle: {
    color: theme.text,
    fontSize: 14,
    fontWeight: '900',
  },
  reviewSubtitle: {
    marginTop: 2,
    color: theme.muted,
    fontSize: 11,
  },
  reviewMessages: {
    marginTop: 11,
    gap: 5,
  },
  reviewMessage: {
    color: '#755013',
    fontSize: 12,
    lineHeight: 18,
  },
  reviewButton: {
    marginTop: 12,
    minHeight: 40,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E9C677',
    alignItems: 'center',
    justifyContent: 'center',
  },
  reviewButtonText: {
    color: '#8A5A00',
    fontSize: 12,
    fontWeight: '800',
  },
  correctionEditorHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 12,
    marginBottom: 8,
  },
  correctionEditorSubtitle: {
    marginTop: 3,
    color: theme.muted,
    fontSize: 11,
  },
  categoryChoiceWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 7,
    marginBottom: 8,
  },
  categoryChoice: {
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.bg,
  },
  categoryChoiceSelected: {
    borderColor: theme.primary,
    backgroundColor: '#EEF7EE',
  },
  categoryChoiceText: {
    color: theme.muted,
    fontSize: 11,
    fontWeight: '700',
  },
  categoryChoiceTextSelected: {
    color: theme.primary,
  },
  correctionHint: {
    maxWidth: 250,
    color: theme.muted,
    fontSize: 10,
    lineHeight: 15,
  },
  entityChoiceQuestion: {
    marginTop: 10,
    color: theme.muted,
    fontSize: 11,
    fontWeight: '700',
  },
  correctionSaveButtonFull: {
    marginTop: 16,
    minHeight: 46,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: theme.primary,
  },
  editedNotice: {
    marginTop: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  editedNoticeText: {
    color: theme.primary,
    fontSize: 10,
    fontWeight: '700',
  },
  savedInfoGroup: {
    marginTop: 16,
  },
  savedInfoLabel: {
    marginBottom: 8,
    color: theme.muted,
    fontSize: 11,
    fontWeight: '800',
  },
  savedEntityList: {
    gap: 8,
  },
  savedEntityRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    padding: 10,
    borderRadius: 13,
    backgroundColor: theme.bg,
  },
  savedEntityIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#EEF7EE',
  },
  savedEntityBody: {
    flex: 1,
  },
  savedEntityName: {
    color: theme.text,
    fontSize: 13,
    fontWeight: '800',
  },
  savedEntityType: {
    marginTop: 2,
    color: theme.muted,
    fontSize: 10,
  },

  searchModeTabs: {
    marginTop: 16,
    marginBottom: 14,
    padding: 4,
    flexDirection: 'row',
    gap: 4,
    borderRadius: 14,
    backgroundColor: '#EEF0F3',
  },
  searchModeTab: {
    flex: 1,
    minHeight: 42,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    borderRadius: 11,
  },
  searchModeTabActive: {
    backgroundColor: theme.primary,
  },
  searchModeTabText: {
    color: theme.muted,
    fontSize: 13,
    fontWeight: '800',
  },
  searchModeTabTextActive: {
    color: '#FFFFFF',
  },
  knowledgePanel: {
    marginTop: 4,
  },
  knowledgeHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 12,
  },
  knowledgeIconBubble: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#EEF7EE',
  },
  knowledgeHeaderText: {
    flex: 1,
  },
  knowledgeTitle: {
    color: theme.text,
    fontSize: 16,
    fontWeight: '900',
  },
  knowledgeSubtitle: {
    marginTop: 2,
    color: theme.muted,
    fontSize: 11,
    lineHeight: 16,
  },
  knowledgeInputBox: {
    minHeight: 92,
    padding: 12,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surface,
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 10,
  },
  knowledgeInput: {
    flex: 1,
    minHeight: 58,
    maxHeight: 120,
    color: theme.text,
    fontSize: 14,
    lineHeight: 20,
    textAlignVertical: 'top',
  },
  knowledgeAskButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: theme.primary,
  },
  questionExamples: {
    marginTop: 10,
    gap: 7,
  },
  questionExampleChip: {
    alignSelf: 'flex-start',
    paddingHorizontal: 11,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: theme.surface,
    borderWidth: 1,
    borderColor: theme.border,
  },
  questionExampleText: {
    color: theme.muted,
    fontSize: 11,
    fontWeight: '700',
  },
  knowledgeLoadingRow: {
    marginTop: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
    padding: 13,
    borderRadius: 14,
    backgroundColor: theme.surface,
  },
  knowledgeLoadingText: {
    flex: 1,
    color: theme.muted,
    fontSize: 12,
  },
  knowledgeErrorBox: {
    marginTop: 16,
    padding: 13,
    borderRadius: 14,
    backgroundColor: '#FFF5F3',
  },
  knowledgeErrorText: {
    color: '#9B4537',
    fontSize: 12,
    lineHeight: 18,
  },
  knowledgeAnswerCard: {
    marginTop: 16,
    padding: 16,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surface,
  },
  knowledgeAnswerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    marginBottom: 10,
  },
  knowledgeAnswerLabel: {
    color: theme.primary,
    fontSize: 12,
    fontWeight: '900',
  },
  knowledgeAnswerText: {
    color: theme.text,
    fontSize: 14,
    lineHeight: 22,
  },
  knowledgeSources: {
    marginTop: 18,
    gap: 8,
  },
  knowledgeSourcesTitle: {
    marginBottom: 2,
    color: theme.muted,
    fontSize: 11,
    fontWeight: '800',
  },
  knowledgeSourceCard: {
    padding: 12,
    borderRadius: 14,
    backgroundColor: theme.bg,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  knowledgeSourceBody: {
    flex: 1,
  },
  knowledgeSourceTitle: {
    color: theme.text,
    fontSize: 12,
    fontWeight: '800',
    lineHeight: 17,
  },
  knowledgeSourceSummary: {
    marginTop: 3,
    color: theme.muted,
    fontSize: 10,
    lineHeight: 15,
  },
  knowledgeGroundingNote: {
    marginTop: 12,
    color: theme.muted,
    fontSize: 10,
    lineHeight: 15,
  },

  smartSectionSubtitle: {
    marginTop: 3,
    color: theme.muted,
    fontSize: 11,
  },
  smartCollectionRow: {
    gap: 12,
    paddingRight: 8,
    marginBottom: 26,
  },
  smartCollectionCard: {
    width: 210,
    minHeight: 176,
    padding: 16,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surface,
  },
  smartCollectionTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 14,
  },
  smartCollectionIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#EEF7EE',
  },
  smartCollectionCount: {
    color: theme.muted,
    fontSize: 11,
    fontWeight: '800',
  },
  smartCollectionTitle: {
    color: theme.text,
    fontSize: 17,
    lineHeight: 22,
    fontWeight: '900',
  },
  smartCollectionDescription: {
    marginTop: 7,
    flex: 1,
    color: theme.muted,
    fontSize: 11,
    lineHeight: 17,
  },
  smartCollectionFooter: {
    marginTop: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  smartCollectionLink: {
    color: theme.primary,
    fontSize: 11,
    fontWeight: '900',
  },
  smartCollectionDetail: {
    marginTop: 14,
    marginBottom: 18,
    padding: 16,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surface,
  },
  smartCollectionDetailHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  smartCollectionDetailIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#EEF7EE',
  },
  smartCollectionDetailHeaderText: {
    flex: 1,
  },
  smartCollectionDetailEyebrow: {
    color: theme.primary,
    fontSize: 10,
    fontWeight: '900',
  },
  smartCollectionDetailTitle: {
    marginTop: 2,
    color: theme.text,
    fontSize: 18,
    fontWeight: '900',
  },
  smartCollectionDetailDescription: {
    marginTop: 12,
    marginBottom: 12,
    color: theme.text,
    fontSize: 13,
    lineHeight: 20,
  },
  smartCollectionDetailMeta: {
    marginTop: 12,
    color: theme.muted,
    fontSize: 10,
  },

  collectionCompareButton: {
    marginTop: 16,
    minHeight: 46,
    borderRadius: 15,
    backgroundColor: theme.primary,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  collectionCompareButtonText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '900',
  },
  collectionCompareHint: {
    marginTop: 8,
    color: theme.muted,
    fontSize: 10,
    lineHeight: 15,
  },
  collectionCompareError: {
    marginTop: 10,
    color: '#A75B36',
    fontSize: 11,
    lineHeight: 16,
  },
  collectionComparisonPanel: {
    marginTop: 16,
    gap: 16,
  },
  collectionComparisonHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 9,
  },
  collectionComparisonHeaderText: {
    flex: 1,
  },
  collectionComparisonTitle: {
    color: theme.text,
    fontSize: 15,
    fontWeight: '900',
  },
  collectionComparisonSummary: {
    marginTop: 5,
    color: theme.muted,
    fontSize: 11,
    lineHeight: 17,
  },
  collectionComparisonSection: {
    gap: 10,
  },
  collectionComparisonSectionTitle: {
    color: theme.text,
    fontSize: 12,
    fontWeight: '900',
  },
  collectionComparisonSectionHint: {
    marginTop: -6,
    color: theme.muted,
    fontSize: 10,
    lineHeight: 15,
  },
  collectionComparisonDimension: {
    padding: 12,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: '#FAFAFC',
    gap: 8,
  },
  collectionComparisonDimensionTitle: {
    color: theme.primary,
    fontSize: 11,
    fontWeight: '900',
  },
  collectionComparisonItem: {
    paddingTop: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: theme.border,
  },
  collectionComparisonItemTitle: {
    color: theme.text,
    fontSize: 10,
    fontWeight: '800',
  },
  collectionComparisonItemValue: {
    marginTop: 4,
    color: theme.text,
    fontSize: 11,
    lineHeight: 16,
  },
  collectionComparisonEvidence: {
    marginTop: 4,
    color: theme.muted,
    fontSize: 9,
    lineHeight: 14,
  },
  collectionExternalSection: {
    padding: 13,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#EADDBB',
    backgroundColor: '#FFFBF1',
  },
  collectionExternalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
  },
  collectionExternalTitle: {
    color: '#6D531C',
    fontSize: 12,
    fontWeight: '900',
  },
  collectionExternalHint: {
    marginTop: 6,
    color: '#887449',
    fontSize: 10,
    lineHeight: 15,
  },
  collectionExternalFact: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#EADDBB',
  },
  collectionExternalFactTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  collectionExternalFactLabel: {
    flex: 1,
    color: theme.text,
    fontSize: 11,
    fontWeight: '900',
  },
  collectionExternalStatus: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: '#F4E9C9',
  },
  collectionExternalStatusText: {
    color: '#76591A',
    fontSize: 8,
    fontWeight: '900',
  },
  collectionExternalValue: {
    marginTop: 7,
    color: theme.text,
    fontSize: 11,
    lineHeight: 17,
    fontWeight: '800',
  },
  collectionExternalExplanation: {
    marginTop: 5,
    color: theme.muted,
    fontSize: 10,
    lineHeight: 15,
  },
  collectionExternalSources: {
    marginTop: 8,
    gap: 5,
  },
  collectionExternalSource: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  collectionExternalSourceText: {
    flex: 1,
    color: theme.primary,
    fontSize: 9,
    fontWeight: '700',
  },

  collectionCompareNotEligible: {
    padding: 14,
    borderRadius: 16,
    backgroundColor: '#F7F7F9',
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 9,
  },
  collectionCompareNotEligibleText: {
    flex: 1,
  },
  collectionComparisonEntity: {
    marginTop: 3,
    color: theme.primary,
    fontSize: 9,
    fontWeight: '800',
  },
  collectionComparisonSectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  collectionComparisonFindingStatement: {
    marginTop: 5,
    color: theme.text,
    fontSize: 11,
    lineHeight: 17,
    fontWeight: '700',
  },
  collectionComparisonEvidenceCard: {
    marginTop: 8,
    padding: 9,
    borderRadius: 12,
    backgroundColor: '#FFFFFF',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: theme.border,
  },
  collectionComparisonTimestamp: {
    marginTop: 4,
    color: theme.primary,
    fontSize: 9,
    fontWeight: '800',
  },
  collectionExternalSavedLabel: {
    marginTop: 8,
    color: '#8A7443',
    fontSize: 9,
    fontWeight: '900',
  },
  collectionExternalCheckedAt: {
    marginTop: 7,
    color: '#9A8B69',
    fontSize: 8,
  },
  collectionComparisonDecisionNote: {
    padding: 11,
    borderRadius: 14,
    backgroundColor: '#F7F7F9',
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 7,
  },
  collectionComparisonDecisionText: {
    flex: 1,
    color: theme.muted,
    fontSize: 9,
    lineHeight: 14,
  },

  interestTimelineSection: {
    marginTop: 24,
    marginBottom: 24,
  },
  interestTimelineCard: {
    marginTop: 12,
    padding: 16,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surface,
    gap: 14,
  },
  interestTimelineSummaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  interestTimelineIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F1EEFF',
  },
  interestTimelineSummary: {
    flex: 1,
    color: theme.text,
    fontSize: 13,
    lineHeight: 19,
    fontWeight: '800',
  },
  interestTimelineStats: {
    flexDirection: 'row',
    gap: 8,
  },
  interestTimelineStat: {
    flex: 1,
    paddingVertical: 11,
    borderRadius: 14,
    alignItems: 'center',
    backgroundColor: '#F8F8FB',
  },
  interestTimelineStatValue: {
    color: theme.text,
    fontSize: 17,
    fontWeight: '900',
  },
  interestTimelineStatLabel: {
    marginTop: 3,
    color: theme.muted,
    fontSize: 9,
    fontWeight: '700',
  },
  interestTimelineBlock: {
    gap: 8,
  },
  interestTimelineBlockTitle: {
    color: theme.muted,
    fontSize: 10,
    fontWeight: '900',
  },
  interestTrendList: {
    gap: 7,
  },
  interestTrendRow: {
    minHeight: 34,
    paddingHorizontal: 11,
    borderRadius: 12,
    backgroundColor: '#F8F8FB',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 10,
  },
  interestTrendLabel: {
    flex: 1,
    color: theme.text,
    fontSize: 11,
    fontWeight: '800',
  },
  interestTrendValueRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
  },
  interestTrendCount: {
    color: theme.text,
    fontSize: 10,
    fontWeight: '800',
  },
  interestTrendDelta: {
    minWidth: 20,
    color: '#8A7F76',
    fontSize: 10,
    fontWeight: '900',
    textAlign: 'right',
  },
  interestTrendDeltaUp: {
    color: theme.primary,
  },
  interestTimelineChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 7,
  },
  interestTimelineChip: {
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 999,
    backgroundColor: '#F4F4F7',
  },
  interestTimelineChipText: {
    color: theme.text,
    fontSize: 10,
    fontWeight: '800',
  },
  interestTimelineChipStrong: {
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 999,
    backgroundColor: '#F1EEFF',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  interestTimelineChipStrongText: {
    color: theme.primary,
    fontSize: 10,
    fontWeight: '900',
  },

  smartReminderSection: {
    marginBottom: 24,
  },
  smartReminderLoadingCard: {
    marginTop: 12,
    padding: 16,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surface,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  smartReminderList: {
    marginTop: 12,
    gap: 10,
  },
  smartReminderCard: {
    padding: 15,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#E4DEF8',
    backgroundColor: '#FBFAFF',
  },
  smartReminderCardPressed: {
    opacity: 0.78,
  },
  smartReminderCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  smartReminderIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F1EEFF',
  },
  smartReminderHeaderText: {
    flex: 1,
    alignItems: 'flex-start',
  },
  smartReminderBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: '#EEE9FF',
  },
  smartReminderBadgeText: {
    color: theme.primary,
    fontSize: 9,
    fontWeight: '900',
  },
  smartReminderTitle: {
    marginTop: 5,
    color: theme.text,
    fontSize: 13,
    lineHeight: 18,
    fontWeight: '900',
  },
  smartReminderDescription: {
    marginTop: 10,
    color: theme.text,
    fontSize: 11,
    lineHeight: 17,
  },
  smartReminderEvidence: {
    marginTop: 10,
    gap: 5,
  },
  smartReminderEvidenceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  smartReminderEvidenceText: {
    flex: 1,
    color: theme.muted,
    fontSize: 9,
  },
  smartReminderContentTitle: {
    marginTop: 11,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#ECE8F6',
    color: theme.muted,
    fontSize: 9,
    fontWeight: '700',
  },

  conflictSection: {
    marginBottom: 24,
  },
  conflictSectionHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 12,
  },
  conflictSectionSubtitle: {
    marginTop: 3,
    color: theme.muted,
    fontSize: 11,
  },
  conflictCountBadge: {
    minWidth: 26,
    height: 26,
    paddingHorizontal: 8,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFF0E8',
  },
  conflictCountText: {
    color: '#A75B36',
    fontSize: 11,
    fontWeight: '900',
  },
  conflictCard: {
    marginTop: 12,
    padding: 15,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#F0D8CA',
    backgroundColor: '#FFF9F5',
  },
  conflictCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  conflictIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFF0E8',
  },
  conflictHeaderText: {
    flex: 1,
  },
  conflictTypeText: {
    color: '#A75B36',
    fontSize: 10,
    fontWeight: '900',
  },
  conflictTitle: {
    marginTop: 2,
    color: theme.text,
    fontSize: 14,
    lineHeight: 19,
    fontWeight: '900',
  },
  conflictDescription: {
    marginTop: 10,
    color: theme.text,
    fontSize: 12,
    lineHeight: 18,
  },
  conflictEvidenceList: {
    marginTop: 12,
    gap: 7,
  },
  conflictEvidenceCard: {
    padding: 10,
    borderRadius: 13,
    backgroundColor: theme.surface,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
  },
  conflictEvidenceIndex: {
    width: 22,
    height: 22,
    borderRadius: 11,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFF0E8',
  },
  conflictEvidenceIndexText: {
    color: '#A75B36',
    fontSize: 10,
    fontWeight: '900',
  },
  conflictEvidenceBody: {
    flex: 1,
  },
  conflictEvidenceTitle: {
    color: theme.text,
    fontSize: 11,
    fontWeight: '800',
  },
  conflictEvidenceClaim: {
    marginTop: 3,
    color: theme.muted,
    fontSize: 10,
    lineHeight: 15,
  },
  conflictHint: {
    marginTop: 10,
    color: theme.muted,
    fontSize: 10,
    lineHeight: 15,
  },

  homeAlertSummary: {
    marginBottom: 20,
    padding: 14,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#F0D8CA',
    backgroundColor: '#FFF9F5',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  homeAlertIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFF0E8',
  },
  homeAlertBody: {
    flex: 1,
  },
  homeAlertTitle: {
    color: theme.text,
    fontSize: 12,
    fontWeight: '900',
  },
  homeAlertText: {
    marginTop: 3,
    color: theme.muted,
    fontSize: 10,
    lineHeight: 15,
  },
  homeInterestSummary: {
    marginBottom: 22,
    padding: 14,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surface,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  homeInterestBody: {
    flex: 1,
  },
  homeInterestLabel: {
    color: theme.text,
    fontSize: 12,
    fontWeight: '900',
  },
  homeInterestText: {
    marginTop: 4,
    color: theme.muted,
    fontSize: 11,
  },
  moreSection: {
    marginTop: 26,
  },
  moreSectionHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 12,
  },
  moreSectionSubtitle: {
    marginTop: 3,
    color: theme.muted,
    fontSize: 11,
  },
  moreCollectionGrid: {
    marginTop: 12,
    gap: 10,
  },
  moreCollectionCard: {
    padding: 16,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surface,
  },
  moreConnections: {
    marginTop: 12,
    gap: 8,
  },
  moreConnectionCard: {
    padding: 13,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surface,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  moreConnectionIcon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#EEF7EE',
  },
  moreConnectionBody: {
    flex: 1,
  },
  moreConnectionTitle: {
    color: theme.text,
    fontSize: 12,
    fontWeight: '900',
  },
  moreConnectionMeta: {
    marginTop: 3,
    color: theme.muted,
    fontSize: 10,
  },

});
