import { useQuery } from '@tanstack/react-query';
import { getKnowledgeDocuments } from '../lib/api/knowledge';

export function useKnowledgeDocuments(projectId: string) {
  return useQuery({
    queryKey: ['knowledge', 'documents', projectId],
    queryFn: () => getKnowledgeDocuments(projectId),
    enabled: !!projectId,
  });
}
