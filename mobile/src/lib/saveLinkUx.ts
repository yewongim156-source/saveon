/** Pure, UI-only link helpers. Does not rewrite URLs before sending them to the API. */
export function isSaveLinkValid(value: string): boolean {
  const trimmed = value.trim();
  const match = trimmed.match(/^https?:\/\/([^\s/?#]+)(?:[/?#]|$)/i);
  if (!match || !/^https?:\/\/\S+$/i.test(trimmed)) return false;
  const authority = match[1];
  if (authority.includes('@')) return false;
  const hostname = authority.replace(/:\d+$/, '').toLowerCase();
  if (!/^[a-z0-9.-]+$/.test(hostname)) return false;
  if (hostname.startsWith('.') || hostname.endsWith('.') || hostname.includes('..')) return false;
  return hostname === 'localhost' || hostname.includes('.');
}

/** Same Instagram Reel / YouTube Short can arrive with different share-query parameters. */
export function saveLinkIdentity(value: string): string {
  const trimmed = value.trim();
  const instagram = trimmed.match(
    /^https?:\/\/(?:www\.|m\.)?instagram\.com\/(?:reel|reels)\/([a-z0-9_-]+)(?:[/?#]|$)/i,
  );
  if (instagram) return `instagram:reel:${instagram[1]}`;

  const youtubeShort = trimmed.match(
    /^https?:\/\/(?:www\.|m\.)?youtube\.com\/shorts\/([a-z0-9_-]+)(?:[/?#]|$)/i,
  );
  if (youtubeShort) return `youtube:video:${youtubeShort[1]}`;

  const youtubeShare = trimmed.match(
    /^https?:\/\/(?:www\.)?youtu\.be\/([a-z0-9_-]+)(?:[/?#]|$)/i,
  );
  if (youtubeShare) return `youtube:video:${youtubeShare[1]}`;

  return trimmed;
}

export function saveLinkPlatform(value: string): string {
  const host = value.trim().match(/^https?:\/\/([^/?#\s]+)/i)?.[1]?.toLowerCase() ?? '';
  if (host === 'instagram.com' || host.endsWith('.instagram.com')) return 'Instagram';
  if (host === 'youtube.com' || host.endsWith('.youtube.com') || host === 'youtu.be') return 'YouTube';
  if (host === 'tiktok.com' || host.endsWith('.tiktok.com')) return 'TikTok';
  return '웹';
}
