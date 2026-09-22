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

  sourceUrl?: string;

  category: string[];

  keywords: string[];

  entities: string[];

  savedAt: string;

  thumbnailEmoji: string;
};

export type TabScreenName =
  | 'home'
  | 'save'
  | 'library'
  | 'search';

export type Screen =
  | {
      name: TabScreenName;
    }
  | {
      name: 'detail';
      itemId: string;
    };