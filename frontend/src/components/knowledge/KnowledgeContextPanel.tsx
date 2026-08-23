import { useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Field } from '../ui/Field';
import { fieldInputClasses } from '../../lib/fieldStyles';
import { useUploadKnowledgeDocument } from '../../hooks/useUploadKnowledgeDocument';
import { ApiError } from '../../lib/api/client';
import { DOCUMENT_TYPES_BY_SCOPE } from '../../lib/types/knowledge';
import type { DocumentType, KnowledgeScope } from '../../lib/types/knowledge';

interface KnowledgeContextPanelProps {
  projectId: string;
}

interface UploadedDocument {
  id: string;
  title: string;
  scope: KnowledgeScope;
}

const SUPPORTED_EXTENSIONS = '.pdf,.docx,.txt,.md';

export function KnowledgeContextPanel({ projectId }: KnowledgeContextPanelProps) {
  const [isManaging, setIsManaging] = useState(false);
  const [scope, setScope] = useState<KnowledgeScope>('company');
  const [documentType, setDocumentType] = useState<DocumentType>(DOCUMENT_TYPES_BY_SCOPE.company[0].value);
  const [title, setTitle] = useState('');
  const [uploadedDocs, setUploadedDocs] = useState<UploadedDocument[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mutation = useUploadKnowledgeDocument();

  const companyDocs = uploadedDocs.filter((doc) => doc.scope === 'company');
  const projectDocs = uploadedDocs.filter((doc) => doc.scope === 'project');

  function handleScopeChange(nextScope: KnowledgeScope) {
    setScope(nextScope);
    setDocumentType(DOCUMENT_TYPES_BY_SCOPE[nextScope][0].value);
  }

  function handleFile(file: File) {
    const resolvedTitle = title.trim() || file.name;
    mutation.mutate(
      { file, projectId, documentType, title: title.trim() || undefined },
      {
        onSuccess: (result) => {
          setUploadedDocs((prev) => [...prev, { id: result.document_id, title: resolvedTitle, scope }]);
          setTitle('');
        },
      },
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

      <div className="mb-1.5 text-[10.5px] tracking-wide text-[color-mix(in_srgb,var(--color-text)_45%,transparent)] uppercase">
        Company Knowledge
      </div>
      <div className="mb-3 flex flex-col gap-1.5 text-sm">
        {companyDocs.length === 0 ? (
          <p className="text-[12.5px] text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">
            No company documents uploaded yet.
          </p>
        ) : (
          companyDocs.map((doc) => (
            <div key={doc.id} className="flex items-center gap-2">
              <span className="text-[var(--color-success)]">✓</span> {doc.title}
            </div>
          ))
        )}
      </div>

      <div className="mb-1.5 text-[10.5px] tracking-wide text-[color-mix(in_srgb,var(--color-text)_45%,transparent)] uppercase">
        Project Knowledge
      </div>
      <div className="mb-3.5 flex flex-col gap-1.5 text-sm">
        {projectDocs.length === 0 ? (
          <p className="text-[12.5px] text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">
            No project documents uploaded yet.
          </p>
        ) : (
          projectDocs.map((doc) => (
            <div key={doc.id} className="flex items-center gap-2">
              <span className="text-[var(--color-success)]">✓</span> {doc.title}
            </div>
          ))
        )}
      </div>

      {uploadedDocs.length > 0 && (
        <div className="mb-3 text-xs text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">
          {uploadedDocs.length} relevant document{uploadedDocs.length === 1 ? '' : 's'} available
        </div>
      )}

      <Button variant="secondary" className="mb-3 w-full" onClick={() => setIsManaging((v) => !v)}>
        {isManaging ? 'Close Manage Knowledge' : 'Manage Knowledge'}
      </Button>

      {isManaging && (
        <div className="flex flex-col gap-3">
          <div className="flex gap-2">
            <Button
              variant={scope === 'company' ? 'primary' : 'secondary'}
              className="flex-1"
              onClick={() => handleScopeChange('company')}
            >
              Company Knowledge
            </Button>
            <Button
              variant={scope === 'project' ? 'primary' : 'secondary'}
              className="flex-1"
              onClick={() => handleScopeChange('project')}
            >
              Project Knowledge
            </Button>
          </div>

          <Field label="Document Type" htmlFor="knowledge-document-type">
            <select
              id="knowledge-document-type"
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value as DocumentType)}
              className={fieldInputClasses(false)}
              disabled={mutation.isPending}
            >
              {DOCUMENT_TYPES_BY_SCOPE[scope].map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>

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
