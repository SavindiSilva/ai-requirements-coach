// Mirrors app/rag/schemas.py. Keep in sync by hand — do not add fields the
// backend doesn't actually return.

export type DocumentType =
  | 'general'
  | 'definition_of_ready'
  | 'engineering_guideline'
  | 'security_guideline'
  | 'product_rule'
  | 'architecture_guideline'
  | 'project_requirement';

export interface IngestResult {
  document_id: string;
  chunk_count: number;
}

export interface DocumentSummary {
  document_id: string;
  title: string;
  document_type: DocumentType;
}
