export const COMMUNITY_CATEGORIES = [
  { id: 'all', label: 'All' },
  { id: 'technology', label: 'Technology' },
  { id: 'ai_ml', label: 'AI & Machine Learning' },
  { id: 'cloud_devops', label: 'Cloud & DevOps' },
  { id: 'web_development', label: 'Web Development' },
  { id: 'data_science', label: 'Data Science' },
  { id: 'cyber_security', label: 'Cyber Security' },
  { id: 'career', label: 'Career' },
  { id: 'design', label: 'Design' },
  { id: 'entrepreneurship', label: 'Entrepreneurship' },
  { id: 'other', label: 'Other' },
];

export const CATEGORY_LABELS = COMMUNITY_CATEGORIES.reduce((acc, category) => {
  acc[category.id] = category.label;
  return acc;
}, {});

export const normalizeCommunityList = (payload) => {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.communities)) return payload.communities;
  if (Array.isArray(payload?.items)) return payload.items;
  return [];
};

export const normalizeCommunityPosts = (payload) => {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.posts)) return payload.posts;
  if (Array.isArray(payload?.items)) return payload.items;
  return [];
};

export const normalizeCommunityMembers = (payload) => {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.members)) return payload.members;
  if (Array.isArray(payload?.items)) return payload.items;
  return [];
};
