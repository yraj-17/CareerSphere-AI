export const RESOURCE_TYPES = [
  { id: 'all', label: 'All types' },
  { id: 'ARTICLE', label: 'Articles' },
  { id: 'COURSE', label: 'Courses' },
  { id: 'VIDEO', label: 'Videos' },
  { id: 'DOCUMENTATION', label: 'Docs' },
  { id: 'GITHUB_REPOSITORY', label: 'GitHub' },
  { id: 'TOOL', label: 'Tools' },
  { id: 'BOOK', label: 'Books' },
  { id: 'TUTORIAL', label: 'Tutorials' },
  { id: 'OTHER', label: 'Other' },
];

export const RESOURCE_TYPE_OPTIONS = RESOURCE_TYPES.filter((item) => item.id !== 'all');

export const RESOURCE_CATEGORIES = [
  { id: 'all', label: 'All categories' },
  { id: 'frontend', label: 'Frontend' },
  { id: 'backend', label: 'Backend' },
  { id: 'ai_ml', label: 'AI & ML' },
  { id: 'cloud_devops', label: 'Cloud & DevOps' },
  { id: 'data_science', label: 'Data Science' },
  { id: 'career', label: 'Career' },
  { id: 'design', label: 'Design' },
  { id: 'productivity', label: 'Productivity' },
  { id: 'other', label: 'Other' },
];

export const CATEGORY_OPTIONS = RESOURCE_CATEGORIES.filter((item) => item.id !== 'all');

export function resourceTypeLabel(type) {
  return RESOURCE_TYPES.find((item) => item.id === type)?.label || 'Resource';
}

export function categoryLabel(category) {
  return RESOURCE_CATEGORIES.find((item) => item.id === category)?.label || category || 'General';
}

export function normalizeResourceList(payload) {
  if (Array.isArray(payload?.resources)) return payload.resources;
  if (Array.isArray(payload)) return payload;
  return [];
}

export function normalizeResourceTags(tags) {
  if (!Array.isArray(tags)) return [];
  const seen = new Set();
  const cleaned = [];
  tags.forEach((raw) => {
    const tag = String(raw || '').trim();
    const normalized = tag.toLowerCase();
    if (!tag || seen.has(normalized)) return;
    seen.add(normalized);
    cleaned.push(tag);
  });
  return cleaned;
}
