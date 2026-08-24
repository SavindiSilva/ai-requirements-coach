import { useMutation, useQueryClient } from '@tanstack/react-query';
import { uploadKnowledgeDocument } from '../lib/api/knowledge';

export function useUploadKnowledgeDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: uploadKnowledgeDocument,
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: ['knowledge', 'documents', variables.projectId] });
    },
  });
}
