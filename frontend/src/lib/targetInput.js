export function targetTemplate(value) {
  return value.split(/[?#]/, 1)[0];
}

export function targetOrigin(value) {
  const input = value.trim();
  if (!/^https?:\/\//i.test(input) || /[\s\\]/.test(input)) return null;
  try {
    const url = new URL(input);
    if (url.username || url.password || url.port === '0') return null;
    return url.origin;
  } catch {
    return null;
  }
}

export function restoreTargetQuery(template, draft, sameGuard) {
  if (!sameGuard || !template) return template;
  try {
    const current = new URL(draft);
    const query = current.search;
    current.search = '';
    current.hash = '';
    return current.href === new URL(template).href ? template + query : template;
  } catch {
    return template;
  }
}
