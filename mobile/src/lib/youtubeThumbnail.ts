/**
 * Derive a public YouTube thumbnail only from a valid video URL.
 * Never guess media URLs for Instagram, uploads, or unrelated hosts.
 */
export function youtubeVideoId(sourceUrl?: string | null): string | null {
  if (!sourceUrl || typeof sourceUrl !== 'string') return null;
  try {
    const parsed = new URL(sourceUrl.trim());
    if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') return null;
    const host = parsed.hostname.toLowerCase().replace(/^www\./, '').replace(/^m\./, '');
    const sections = parsed.pathname.split('/').filter(Boolean);
    let id: string | undefined;
    if (host === 'youtu.be') id = sections[0];
    else if (host === 'youtube.com' || host === 'youtube-nocookie.com') {
      if (sections[0] === 'shorts' || sections[0] === 'embed' || sections[0] === 'live') {
        id = sections[1];
      } else if (sections[0] === 'watch') {
        id = parsed.searchParams.get('v') || undefined;
      }
    }
    return id && /^[A-Za-z0-9_-]{11}$/.test(id) ? id : null;
  } catch {
    return null;
  }
}

export function youtubeThumbnailUrl(sourceUrl?: string | null): string | null {
  const id = youtubeVideoId(sourceUrl);
  return id ? `https://i.ytimg.com/vi/${id}/hqdefault.jpg` : null;
}
