export type ApiContent = {
  id: number;
  sourceUrl: string;
  platform: 'INSTAGRAM' | 'YOUTUBE' | 'WEB' | 'UPLOAD';
  title: string | null;
  summary: string | null;
  status: 'PENDING' | 'ANALYZING' | 'COMPLETED' | 'FAILED';
  createdAt: string;
  analyzedAt: string | null;
  categories: string[];
  keywords: string[];
  entities: string[];
};

const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ??
  'http://localhost:8080/api/v1';

export async function createContent(
  sourceUrl: string,
  platform: ApiContent['platform'],
): Promise<ApiContent> {
  const response = await fetch(`${API_BASE_URL}/contents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sourceUrl, platform }),
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

  const response = await fetch(`${API_BASE_URL}/contents/upload`, {
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

export async function getContents(): Promise<ApiContent[]> {
  const response = await fetch(`${API_BASE_URL}/contents`);

  if (!response.ok) {
    throw new Error(`콘텐츠 조회 실패: HTTP ${response.status}`);
  }

  return response.json();
}

export async function searchContents(
  query: string,
): Promise<ApiContent[]> {
  const searchTerm = encodeURIComponent(query.trim());
  const response = await fetch(
    `${API_BASE_URL}/contents/search?q=${searchTerm}`,
  );

  if (!response.ok) {
    throw new Error(`콘텐츠 검색 실패: HTTP ${response.status}`);
  }

  return response.json();
}

export { API_BASE_URL };
