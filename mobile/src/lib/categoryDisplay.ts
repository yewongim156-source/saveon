/** UI-only cleanup for older analyzed videos; no DB or filtering semantics change. */
export function displayContentCategories(
  categories: string[],
  title: string,
): string[] {
  if (!Array.isArray(categories)) return [];
  const unique = Array.from(new Set(categories.filter((x) => typeof x === 'string' && x.trim()).map((x) => x.trim())));
  let visible = unique.some((x) => x !== '기타')
    ? unique.filter((x) => x !== '기타')
    : unique;
  const isRecipe = /레시피|볶음밥|계란밥|비빔밥|조리법|요리법|만드는\s*법|만들기|조리\s*과정/i.test(title || '');
  if (visible.includes('음식/레시피') && isRecipe) {
    visible = visible.filter((x) => x !== '생활정보');
  }
  return visible;
}
