import { useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Field } from '../ui/Field';
import { fieldInputClasses } from '../../lib/fieldStyles';
import { useUploadKnowledgeDocument } from '../../hooks/useUploadKnowledgeDocument';
import { useKnowledgeDocuments } from '../../hooks/useKnowledgeDocuments';
import { ApiError } from '../../lib/api/client';

interface KnowledgeContextPanelProps {
  projectId: string;
}

const SUPPORTED_EXTENSIONS = '.pdf,.docx,.txt,.md';

export function KnowledgeContextPanel({ projectId }: KnowledgeContextPanelProps) {
  const [isManaging, setIsManaging] = useState(false);
  const [title, setTitle] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mutation = useUploadKnowledgeDocument();
  const documentsQuery = useKnowledgeDocuments(projectId);
  const documents = documentsQuery.data ?? [];

  function handleFile(file: File) {
    mutation.mutate(
      { file, projectId, title: title.trim() || undefined },
      { onSuccess: () => setTitle('') },
    );
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function handleInputChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  return (
    <Card className="p-5">
      <div className="mb-2.5 flex items-center gap-2">
        <div className="text-sm font-medium">Relevant Company &amp; Project Knowledge</div>
        <span className="inline-flex items-center rounded-[5px] border border-[var(--color-divider)] px-2 py-0.5 text-[10px] text-[color-mix(in_srgb,var(--color-text)_50%,transparent)]">
          Optional
        </span>
      </div>
      <p className="mb-3.5 text-[12.5px] leading-relaxed text-[color-mix(in_srgb,var(--color-text)_50%,transparent)]">
        AI can use relevant company and project guidelines when analysing this ticket.
      </p>

      <div className="mb-3.5 flex flex-col gap-1.5 text-sm">
        {documentsQuery.isLoading ? (
          <p className="text-[12.5px] text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">
            Loading documents…
          </p>
        ) : documents.length === 0 ? (
          <p className="text-[12.5px] text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">
            No documents uploaded yet.
          </p>
        ) : (
          documents.map((doc) => (
            <div key={doc.document_id} className="flex items-center gap-2">
              <span className="text-[var(--color-success)]">✓</span> {doc.title}
            </div>
          ))
        )}
      </div>

      {documents.length > 0 && (
        <div className="mb-3 text-xs text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">
          {documents.length} relevant document{documents.length === 1 ? '' : 's'} available
        </div>
      )}

      <Button variant="secondary" className="mb-3 w-full" onClick={() => setIsManaging((v) => !v)}>
        {isManaging ? 'Close Manage Knowledge' : 'Manage Knowledge'}
      </Button>

      {isManaging && (
        <div className="flex flex-col gap-3">
          <Field label="Title (optional)" htmlFor="knowledge-title">
            <input
              id="knowledge-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Defaults to the file name"
              className={fieldInputClasses(false)}
              disabled={mutation.isPending}
            />
          </Field>

          <div
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragOver(true);
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
            className={`cursor-pointer rounded-[var(--radius-md)] border border-dashed p-4 text-center transition-colors ${
              isDragOver
                ? 'border-[var(--color-accent)] bg-[color-mix(in_srgb,var(--color-accent)_8%,transparent)]'
                : 'border-[color-mix(in_srgb,var(--color-text)_20%,transparent)]'
            } ${mutation.isPending ? 'pointer-events-none opacity-60' : ''}`}
          >
            <div className="mb-1 text-[12.5px] text-[color-mix(in_srgb,var(--color-text)_50%,transparent)]">
              {mutation.isPending ? 'Uploading…' : 'Drop files here or click to upload'}
            </div>
            <div className="text-[11px] text-[color-mix(in_srgb,var(--color-text)_35%,transparent)]">
              PDF · DOCX · TXT · MD
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept={SUPPORTED_EXTENSIONS}
              onChange={handleInputChange}
              disabled={mutation.isPending}
              className="hidden"
            />
          </div>

          {mutation.isError && (
            <div className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)] px-3.5 py-3 text-sm text-[var(--color-danger)]">
              {mutation.error instanceof ApiError ? mutation.error.message : 'Upload failed. Please try again.'}
            </div>
          )}

          {mutation.isSuccess && (
            <div className="text-[12.5px] text-[var(--color-success)]">✓ Document uploaded and indexed.</div>
          )}
        </div>
      )}
    </Card>
  );
}
