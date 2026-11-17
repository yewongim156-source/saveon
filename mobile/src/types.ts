export type Platform =
  | 'Instagram'
  | 'YouTube'
  | 'Upload'
  | 'Web';

export type ContentItem = {
  id: string;

  platform: Platform;

  title: string;

  summary: string;

  videoBasedSummary?: boolean;

  sourceUrl?: string;

  category: string[];

  keywords: string[];

  entities: string[];

  /** Original API status, not a guess based on categories. */
  analysisStatus?: 'PENDING' | 'ANALYZING' | 'COMPLETED' | 'FAILED';
  savedAt: string;

  thumbnailEmoji: string;
  thumbnailAvailable?: boolean;
};

export type TabScreenName =
  | 'home'
  | 'save'
  | 'library'
  | 'search'
  | 'more';

export type Screen =
  | {
      name: TabScreenName;
    }
  | {
      name: 'detail';
      itemId: string;
    };
// SAVEON_INSTAGRAM_THUMBNAIL_V1
