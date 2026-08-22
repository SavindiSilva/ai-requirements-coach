import { apiPostForm } from './client';
import type { DocumentType, IngestResult } from '../types/knowledge';

export interface UploadKnowledgeDocumentParams {
  file: File;
  projectId: string;
  documentType: DocumentType;
  title?: string;
}

export function uploadKnowledgeDocument({
  file,
  projectId,
  documentType,
  title,
}: UploadKnowledgeDocumentParams): Promise<IngestResult> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('project_id', projectId);
  formData.append('document_type', documentType);
  if (title) formData.append('title', title);

  return apiPostForm<IngestResult>('/api/knowledge/upload', formData);
}
