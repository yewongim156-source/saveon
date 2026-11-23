import type { PipelineStage } from '../design/pipelineStage';

/** save:on TRUE_PROGRESS_V1 - persisted status + live analysis stage. */
export type ApiContentProgress = {
  contentId: number;
  status: ApiContent['status'];
  stage: PipelineStage;
};

export type ApiContent = {
  id: number;
  sourceUrl: string;
  thumbnailAvailable?: boolean;
  platform: 'INSTAGRAM' | 'YOUTUBE' | 'WEB' | 'UPLOAD';
  title: string | null;
  summary: string | null;
  status: 'PENDING' | 'ANALYZING' | 'COMPLETED' | 'FAILED';
  createdAt: string;
  analyzedAt: string | null;
  categories: string[];
  keywords: string[];
  entities: string[];
  structuredAnalysis?: string | null;
  userEdited?: boolean;
  editedAt?: string | null;
};

export type ApiContentConnection = {
  entity: string;
  type: 'PLACE' | 'PRODUCT' | 'BRAND' | 'PERSON' | 'SERVICE';
  count: number;
  confidence: number;
};

export type ApiRelatedEntity = {
  entity: string;
  type: ApiContentConnection['type'];
  count: number;
};

export type ApiContentHighlight = {
  contentId: number;
  title: string;
  summary: string;
};

export type ApiInterestSynthesis = {
  source: 'AGENT' | 'RULE_BASED';
  summary: string;
  keyInterests: string[];
  takeaways: string[];
};


export type ApiContentAction = {
  kind:
    | 'MAP_SEARCH'
    | 'WEB_SEARCH'
    | 'COMPARE_SEARCH'
    | 'CALENDAR_ADD'
    | 'CHECKLIST_CREATE';
  title: string;
  description: string;
  query: string;
  eventTitle?: string;
  eventDate?: string;
  checklistItems?: string[];
};

export type ApiContentActionPlan = {
  source: 'AGENT' | 'RULE_BASED';
  actions: ApiContentAction[];
};

export type ApiContentBundle = {
  entity: string;
  type: ApiContentConnection['type'];
  count: number;
  overview: string;
  categories: string[];
  commonKeywords: string[];
  commonTags: string[];
  relatedEntities: ApiRelatedEntity[];
  highlights: ApiContentHighlight[];
  contentTypes: string[];
  actionFacts: {
    contentId: number | null;
    text: string;
    type: string;
    confidence: number;
  }[];
  synthesis?: ApiInterestSynthesis | null;
};


export type ApiContentQualityWarning = {
  type: string;
  field: string;
  severity: 'WARN' | 'ERROR';
  message: string;
};

export type ApiContentQuality = {
  valid: boolean;
  requiresReview: boolean;
  warnings: ApiContentQualityWarning[];
};

export type ApiEntityCorrection = {
  name: string;
  type:
    | 'PLACE'
    | 'PRODUCT'
    | 'BRAND'
    | 'PERSON'
    | 'SERVICE'
    | 'EVENT'
    | 'DATE'
    | 'OTHER';
};

export type ApiContentCorrectionRequest = {
  title: string;
  summary: string;
  categories: string[];
  keywords: string[];
  entityDetails: ApiEntityCorrection[];
};

export type ApiCorrectionStats = {
  totalCorrections: number;
  errorTypes: Record<string, number>;
};

export type ApiKnowledgeSource = {
  contentId: number;
  title: string;
  summary: string;
  platform: 'INSTAGRAM' | 'YOUTUBE' | 'WEB' | 'UPLOAD' | string;
  sourceUrl: string;
};

export type ApiKnowledgeAnswer = {
  answer: string;
  grounded: boolean;
  sources: ApiKnowledgeSource[];
};


export type ApiSmartCollectionItem = {
  contentId: number;
  title: string;
  summary: string;
  platform: string;
  sourceUrl: string;
};

export type ApiSmartCollection = {
  key: string;
  seed: string;
  title: string;
  description: string;
  count: number;
  categories: string[];
  commonKeywords: string[];
  commonEntities: string[];
  contents: ApiSmartCollectionItem[];
  source: 'AGENT' | 'RULE_BASED' | string;
};


export type ApiCollectionComparisonEvidence = {
  contentId: number;
  title: string;
  quote: string;
  timestampSeconds: number | null;
};

export type ApiCollectionComparisonFinding = {
  topic: string;
  statement: string;
  evidences: ApiCollectionComparisonEvidence[];
};

export type ApiCollectionObjectiveDisagreement = {
  field: string;
  label: string;
  entity: string;
  values: string[];
  evidences: ApiCollectionComparisonEvidence[];
};

export type ApiCollectionComparisonSource = {
  title: string;
  url: string;
};

export type ApiCollectionComparisonExternalFact = {
  label: string;
  field: string;
  entity: string;
  savedValues: string[];
  status:
    | 'SUPPORTED'
    | 'UPDATED'
    | 'CONFLICTING'
    | 'INSUFFICIENT_EVIDENCE'
    | string;
  currentValue: string;
  explanation: string;
  checkedAt: string;
  sources: ApiCollectionComparisonSource[];
};

export type ApiCollectionComparison = {
  eligible: boolean;
  reason: string;
  comparisonEntity: string;
  title: string;
  summary: string;
  commonPoints: ApiCollectionComparisonFinding[];
  disagreements: ApiCollectionComparisonFinding[];
  uniqueMentions: ApiCollectionComparisonFinding[];
  objectiveDisagreements: ApiCollectionObjectiveDisagreement[];
  externalFacts: ApiCollectionComparisonExternalFact[];
  citedContentIds: number[];
};

export type ApiContentConflictEvidence = {
  contentId: number;
  title: string;
  claimText: string;
  value: string;
};

export type ApiContentConflict = {
  key: string;
  subject: string;
  claimType: string;
  title: string;
  description: string;
  severity: 'WARN' | 'ERROR' | string;
  evidences: ApiContentConflictEvidence[];
  source: 'AGENT' | 'RULE_BASED' | string;
};



export type ApiSmartReminder = {
  key: string;
  type:
    | 'DATE_CHECK'
    | 'EVENT_CHECK'
    | 'TRAVEL_REVISIT'
    | 'REVISIT'
    | string;
  title: string;
  description: string;
  badge: string;
  contentId: number;
  contentTitle: string;
  sourceUrl: string;
  evidence: string[];
  score: number;
};

export type ApiInterestTimelineTrend = {
  label: string;
  currentCount: number;
  previousCount: number;
  delta: number;
  direction: 'NEW' | 'UP' | 'DOWN' | 'STEADY' | string;
};

export type ApiInterestTimelineItem = {
  label: string;
  type: 'KEYWORD' | 'ENTITY' | string;
  count: number;
};

export type ApiInterestTimeline = {
  recentDays: number;
  recentCount: number;
  previousCount: number;
  last30DaysCount: number;
  summary: string;
  categoryTrends: ApiInterestTimelineTrend[];
  emergingInterests: ApiInterestTimelineItem[];
  topInterests: ApiInterestTimelineItem[];
};

const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ??
  'http://localhost:8080/api/v1';

const EVALUATION_WEB =
  process.env.EXPO_PUBLIC_EVALUATION_MODE === 'true' &&
  typeof window !== 'undefined';
const EVALUATION_CODE_STORAGE = 'saveon-evaluation-access-code';
let evaluationPromptCancelled = false;

function readEvaluationCode(): string {
  if (!EVALUATION_WEB || evaluationPromptCancelled) return '';
  try {
    const existing = window.sessionStorage.getItem(EVALUATION_CODE_STORAGE);
    if (existing) return existing;
    const entered = window.prompt(
      'SAVEON 평가용 접속 코드를 입력해 주세요.\\n' +
      '이 평가판은 모든 참가자가 저장 목록을 공유합니다. ' +
      '개인정보가 포함된 링크나 영상을 저장하지 마세요.',
    )?.trim() ?? '';
    if (!entered) {
      evaluationPromptCancelled = true;
      return '';
    }
    window.sessionStorage.setItem(EVALUATION_CODE_STORAGE, entered);
    return entered;
  } catch {
    evaluationPromptCancelled = true;
    return '';
  }
}

async function apiFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  if (!EVALUATION_WEB) return globalThis.fetch(input, init);
  const send = (code: string) => {
    const headers = new Headers(init?.headers);
    if (code) headers.set('X-Saveon-Evaluation-Code', code);
    return globalThis.fetch(input, { ...init, headers });
  };
  const code = readEvaluationCode();
  let response = await send(code);
  if (response.status === 401 && !evaluationPromptCancelled) {
    try {
      window.sessionStorage.removeItem(EVALUATION_CODE_STORAGE);
    } catch {
      // Session storage may be blocked.
    }
    const replacement = readEvaluationCode();
    if (replacement) response = await send(replacement);
  }
  return response;
}

export async function createContent(
  sourceUrl: string,
  platform: ApiContent['platform'],
  thumbnailAllowed = false,
): Promise<ApiContent> {
  const response = await apiFetch(`${API_BASE_URL}/contents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sourceUrl, platform, thumbnailAllowed }),
  });

  if (!response.ok) {
    throw new Error(`콘텐츠 저장 실패: HTTP ${response.status}`);
  }

  return response.json();
}

export async function uploadVideo(
  file: { uri: string; name: string; type: string },
): Promise<ApiContent> {
  const formData = new FormData();

  formData.append(
    'file',
    {
      uri: file.uri,
      name: file.name,
      type: file.type,
    } as any,
  );

  const response = await apiFetch(`${API_BASE_URL}/contents/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(
      `영상 업로드 실패: HTTP ${response.status} ${text}`,
    );
  }

  return response.json();
}

export async function getContentProgress(contentId: number): Promise<ApiContentProgress> {
  const response = await apiFetch(`${API_BASE_URL}/contents/${contentId}/progress`);
  if (!response.ok) {
    throw new Error(`분석 진행 상태 조회 실패: HTTP ${response.status}`);
  }
  return response.json();
}

/** Private Spring image endpoint. Never expose a MinIO URL to the mobile app. */
export function getInstagramThumbnailUrl(id: string | number): string {
  return `${API_BASE_URL}/contents/${encodeURIComponent(String(id))}/thumbnail`;
}

export async function getContents(): Promise<ApiContent[]> {
  const response = await apiFetch(`${API_BASE_URL}/contents`);

  if (!response.ok) {
    throw new Error(`콘텐츠 조회 실패: HTTP ${response.status}`);
  }

  return response.json();
}

export async function searchContents(
  query: string,
): Promise<ApiContent[]> {
  const searchTerm = encodeURIComponent(query.trim());
  const response = await apiFetch(
    `${API_BASE_URL}/contents/search?q=${searchTerm}`,
  );

  if (!response.ok) {
    throw new Error(`콘텐츠 검색 실패: HTTP ${response.status}`);
  }

  return response.json();
}

export async function semanticSearchContents(
  query: string,
  limit = 20,
): Promise<ApiContent[]> {
  const searchTerm = encodeURIComponent(query.trim());
  const safeLimit = Math.max(1, Math.min(limit, 50));
  const response = await apiFetch(
    `${API_BASE_URL}/contents/search/semantic?q=${searchTerm}&limit=${safeLimit}`,
  );

  if (!response.ok) {
    throw new Error(
      `의미 검색 실패: HTTP ${response.status}`,
    );
  }

  return response.json();
}

export async function getContentConnections(
  limit = 8,
): Promise<ApiContentConnection[]> {
  const safeLimit = Math.max(1, Math.min(limit, 30));

  const response = await apiFetch(
    `${API_BASE_URL}/content-connections?limit=${safeLimit}`,
  );

  if (!response.ok) {
    throw new Error(
      `콘텐츠 연결 조회 실패: HTTP ${response.status}`,
    );
  }

  return response.json();
}

export async function getConnectedContents(
  type: ApiContentConnection['type'],
  entity: string,
): Promise<ApiContent[]> {
  const typeParam = encodeURIComponent(type);
  const entityParam = encodeURIComponent(entity.trim());

  const response = await apiFetch(
    `${API_BASE_URL}/content-connections/contents?type=${typeParam}&entity=${entityParam}`,
  );

  if (!response.ok) {
    throw new Error(
      `연결 콘텐츠 조회 실패: HTTP ${response.status}`,
    );
  }

  return response.json();
}

export async function getContentBundle(
  type: ApiContentConnection['type'],
  entity: string,
): Promise<ApiContentBundle> {
  const typeParam = encodeURIComponent(type);
  const entityParam = encodeURIComponent(entity.trim());

  const response = await apiFetch(
    `${API_BASE_URL}/content-connections/bundle?type=${typeParam}&entity=${entityParam}`,
  );

  if (!response.ok) {
    throw new Error(
      `관심 정보 묶음 조회 실패: HTTP ${response.status}`,
    );
  }

  return response.json();
}



export async function reanalyzeContent(
  contentId: number,
): Promise<ApiContent> {
  const response = await apiFetch(
    `${API_BASE_URL}/contents/${contentId}/analyze`,
    {
      method: 'POST',
    },
  );

  if (!response.ok) {
    throw new Error(
      `콘텐츠 다시 정리 요청 실패: HTTP ${response.status}`,
    );
  }

  return response.json();
}


export async function getContent(
  contentId: number,
): Promise<ApiContent> {
  const response = await apiFetch(
    `${API_BASE_URL}/contents/${contentId}`,
  );

  if (!response.ok) {
    throw new Error(
      `콘텐츠 상세 조회 실패: HTTP ${response.status}`,
    );
  }

  return response.json();
}

export async function getContentQuality(
  contentId: number,
): Promise<ApiContentQuality> {
  const response = await apiFetch(
    `${API_BASE_URL}/content-quality/${contentId}`,
  );

  if (!response.ok) {
    throw new Error(
      `AI 검증 결과 조회 실패: HTTP ${response.status}`,
    );
  }

  return response.json();
}

export async function correctContent(
  contentId: number,
  correction: ApiContentCorrectionRequest,
): Promise<ApiContent> {
  const response = await apiFetch(
    `${API_BASE_URL}/ai-corrections/content/${contentId}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(correction),
    },
  );

  if (!response.ok) {
    const text = await response.text();
    throw new Error(
      `AI 결과 수정 실패: HTTP ${response.status} ${text}`,
    );
  }

  return response.json();
}

export async function logActionCorrection(
  payload: {
    contentId: number | null;
    fieldName: string;
    aiValue: string;
    correctedValue: string;
    errorType: string;
  },
): Promise<void> {
  const response = await apiFetch(
    `${API_BASE_URL}/ai-corrections/action`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    throw new Error(
      `Action 수정 로그 저장 실패: HTTP ${response.status}`,
    );
  }
}

export async function getCorrectionStats(): Promise<ApiCorrectionStats> {
  const response = await apiFetch(
    `${API_BASE_URL}/ai-corrections/stats`,
  );

  if (!response.ok) {
    throw new Error(
      `교정 통계 조회 실패: HTTP ${response.status}`,
    );
  }

  return response.json();
}

export async function planSingleContentActions(
  contentId: number,
): Promise<ApiContentActionPlan> {
  const response = await apiFetch(
    `${API_BASE_URL}/content-actions/plan/content/${contentId}`,
    {
      method: 'POST',
    },
  );

  if (!response.ok) {
    throw new Error(
      `단일 콘텐츠 Action Agent 요청 실패: HTTP ${response.status}`,
    );
  }

  return response.json();
}


export async function planContentActions(
  bundle: ApiContentBundle,
): Promise<ApiContentActionPlan> {
  const response = await apiFetch(
    `${API_BASE_URL}/content-actions/plan`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bundle),
    },
  );

  if (!response.ok) {
    throw new Error(
      `Action Agent 요청 실패: HTTP ${response.status}`,
    );
  }

  return response.json();
}


export async function askSavedKnowledge(
  question: string,
  limit = 5,
): Promise<ApiKnowledgeAnswer> {
  const response = await apiFetch(
    `${API_BASE_URL}/knowledge/ask`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: question.trim(),
        limit: Math.max(1, Math.min(limit, 8)),
      }),
    },
  );

  if (!response.ok) {
    const text = await response.text();
    throw new Error(
      `저장물 질문 실패: HTTP ${response.status} ${text}`,
    );
  }

  return response.json();
}



export async function getSmartCollections(
  limit = 6,
): Promise<ApiSmartCollection[]> {
  const safeLimit = Math.max(1, Math.min(limit, 10));

  const response = await apiFetch(
    `${API_BASE_URL}/smart-collections?limit=${safeLimit}`,
  );

  if (!response.ok) {
    throw new Error(
      `스마트 컬렉션 조회 실패: HTTP ${response.status}`,
    );
  }

  return response.json();
}



export async function compareSmartCollection(
  collectionTitle: string,
  contentIds: number[],
): Promise<ApiCollectionComparison> {
  const response = await apiFetch(
    `${API_BASE_URL}/collection-comparisons`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        collectionTitle,
        contentIds,
      }),
    },
  );

  if (!response.ok) {
    // The API maps downstream Gemini quota exhaustion to HTTP 429.
    if (response.status === 429) {
      throw new Error('COLLECTION_COMPARISON_RATE_LIMIT');
    }
    const text = await response.text();
    throw new Error(
      `컬렉션 비교 실패: HTTP ${response.status} ${text.slice(0, 400)}`,
    );
  }

  return response.json();
}


export async function getContentConflicts(
  limit = 6,
): Promise<ApiContentConflict[]> {
  const safeLimit = Math.max(1, Math.min(limit, 12));

  const response = await apiFetch(
    `${API_BASE_URL}/content-conflicts?limit=${safeLimit}`,
  );

  if (!response.ok) {
    throw new Error(
      `상충 정보 조회 실패: HTTP ${response.status}`,
    );
  }

  return response.json();
}


export async function getSmartReminders(
  limit = 6,
): Promise<ApiSmartReminder[]> {
  const safeLimit = Math.max(1, Math.min(limit, 12));

  const response = await apiFetch(
    `${API_BASE_URL}/smart-reminders?limit=${safeLimit}`,
  );

  if (!response.ok) {
    throw new Error(
      `스마트 리마인더 조회 실패: HTTP ${response.status}`,
    );
  }

  return response.json();
}


export async function getInterestTimeline(): Promise<ApiInterestTimeline> {
  const response = await apiFetch(
    `${API_BASE_URL}/interest-timeline`,
  );

  if (!response.ok) {
    throw new Error(
      `관심사 타임라인 조회 실패: HTTP ${response.status}`,
    );
  }

  return response.json();
}

export { API_BASE_URL };

// save:on TRUE_PROGRESS_V1
// SAVEON_INSTAGRAM_THUMBNAIL_V1
