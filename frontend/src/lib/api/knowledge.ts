import { apiGet, apiPostForm } from './client';
import type { DocumentSummary, IngestResult } from '../types/knowledge';

export interface UploadKnowledgeDocumentParams {
  file: File;
  projectId: string;
  title?: string;
}

export function uploadKnowledgeDocument({
  file,
  projectId,
  title,
}: UploadKnowledgeDocumentParams): Promise<IngestResult> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('project_id', projectId);
  if (title) formData.append('title', title);

  return apiPostForm<IngestResult>('/api/knowledge/upload', formData);
}

export function getKnowledgeDocuments(projectId: string): Promise<DocumentSummary[]> {
  return apiGet<DocumentSummary[]>(`/api/knowledge/documents?project_id=${encodeURIComponent(projectId)}`);
}
