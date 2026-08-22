import { useMutation } from '@tanstack/react-query';
import { uploadKnowledgeDocument } from '../lib/api/knowledge';

export function useUploadKnowledgeDocument() {
  return useMutation({
    mutationFn: uploadKnowledgeDocument,
  });
}
