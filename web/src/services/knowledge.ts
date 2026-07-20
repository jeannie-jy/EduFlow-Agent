/**
 * 知识库 API 服务。
 *
 * POST   /api/knowledge/search       语义检索
 * GET    /api/knowledge/templates     知识点模板列表
 */

import { api } from "./api-client";

// ============================================================================
// 类型
// ============================================================================

export interface SearchRequest {
  query: string;
  top_k?: number;
}

export interface SearchResultItem {
  id: string;
  concept: string;
  content: string;
  subject: string | null;
  difficulty: number;
  similarity: number;
  object_types?: string[];
  animation_types?: string[];
}

export interface SearchResponse {
  results: SearchResultItem[];
}

export interface TemplateItem {
  id: string;
  concept: string;
  subject: string | null;
  difficulty: number;
  object_types: string[];
}

export interface TemplateListResponse {
  templates: TemplateItem[];
}

// ============================================================================
// 方法
// ============================================================================

export function searchKnowledge(query: string, topK = 5) {
  return api.post<SearchResponse>("/knowledge/search", {
    query,
    top_k: topK,
  } as SearchRequest);
}

export function listTemplates(params?: { subject?: string; difficulty?: number }) {
  return api.get<TemplateListResponse>("/knowledge/templates", params as Record<string, string>);
}