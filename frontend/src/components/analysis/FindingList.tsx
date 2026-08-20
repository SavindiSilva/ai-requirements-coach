interface FindingListProps {
  title: string;
  items: string[];
  emptyLabel?: string;
}

export function FindingList({ title, items, emptyLabel = 'None identified.' }: FindingListProps) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-medium tracking-wide text-[color-mix(in_srgb,var(--color-text)_50%,transparent)] uppercase">
        {title}
      </h3>
      {items.length === 0 ? (
        <p className="text-sm text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">
          {emptyLabel}
        </p>
      ) : (
        <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-[color-mix(in_srgb,var(--color-text)_80%,transparent)]">
          {items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
