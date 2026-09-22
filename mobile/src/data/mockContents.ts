import { ContentItem } from '../types';

export const initialContents: ContentItem[] = [
  {
    id: '1',
    platform: 'Instagram',
    title: '성수 데이트 카페 5곳',
    summary: '성수동에서 데이트하기 좋은 카페들을 분위기와 대표 메뉴 중심으로 소개한 콘텐츠입니다.',
    sourceUrl: 'https://www.instagram.com/reel/example1/',
    category: ['카페', '데이트', '서울'],
    keywords: ['성수', '카페', '데이트'],
    entities: ['성수동', '카페 모노'],
    savedAt: '2026-09-17',
    thumbnailEmoji: '☕️'
  },
  {
    id: '2',
    platform: 'YouTube',
    title: '대만 타이베이 맛집 정리',
    summary: '타이베이 여행에서 방문하기 좋은 현지 음식점과 메뉴를 정리한 영상입니다.',
    sourceUrl: 'https://youtube.com/shorts/example2',
    category: ['여행', '맛집'],
    keywords: ['대만', '타이베이', '맛집'],
    entities: ['타이베이', '우육면'],
    savedAt: '2026-09-15',
    thumbnailEmoji: '🍜'
  },
  {
    id: '3',
    platform: 'Instagram',
    title: '올리브영 가을 메이크업 추천',
    summary: '가을 메이크업에 활용하기 좋은 아이섀도와 립 제품을 소개합니다.',
    sourceUrl: 'https://www.instagram.com/reel/example3/',
    category: ['뷰티', '쇼핑'],
    keywords: ['메이크업', '립', '아이섀도'],
    entities: ['올리브영', '립'],
    savedAt: '2026-09-12',
    thumbnailEmoji: '💄'
  },
  {
    id: '4',
    platform: 'Upload',
    title: '성수 하루 코스',
    summary: '성수동 카페와 편집숍을 묶어서 이동하기 좋은 순서로 소개한 영상입니다.',
    category: ['여행', '카페', '쇼핑'],
    keywords: ['성수', '서울', '하루코스'],
    entities: ['성수동', '카페 모노'],
    savedAt: '2026-09-10',
    thumbnailEmoji: '🗺️'
  }
];
