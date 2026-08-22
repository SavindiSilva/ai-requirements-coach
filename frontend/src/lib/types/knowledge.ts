// Mirrors app/rag/schemas.py. Keep in sync by hand — do not add fields the
// backend doesn't actually return.

export type DocumentType =
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

export type KnowledgeScope = 'company' | 'project';

interface DocumentTypeOption {
  value: DocumentType;
  label: string;
}

// CLAUDE.md section 18: Company-level (Definition of Ready, Security
// guidelines, Engineering standards) vs Project-level (Project
// requirements, Architecture guidelines, Product/notification rules).
export const DOCUMENT_TYPES_BY_SCOPE: Record<KnowledgeScope, DocumentTypeOption[]> = {
  company: [
    { value: 'definition_of_ready', label: 'Definition of Ready' },
    { value: 'security_guideline', label: 'Security Guideline' },
    { value: 'engineering_guideline', label: 'Engineering Guideline' },
  ],
  project: [
    { value: 'project_requirement', label: 'Project Requirement' },
    { value: 'architecture_guideline', label: 'Architecture Guideline' },
    { value: 'product_rule', label: 'Product / Notification Rule' },
  ],
};
