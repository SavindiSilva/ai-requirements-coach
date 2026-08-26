interface FindingListProps {
  title: string;
  items: string[];
  emptyLabel?: string;
}

export function FindingList({ title, items, emptyLabel = 'None identified.' }: FindingListProps) {
  return (
    <div>
      <h3 className="mb-2 text-[10.5px] font-medium tracking-wide text-[var(--color-text-tertiary)] uppercase">
        {title}
      </h3>
      {items.length === 0 ? (
        <p className="text-sm text-[var(--color-text-tertiary)]">
          {emptyLabel}
        </p>
      ) : (
        <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-[var(--color-text-secondary)]">
          {items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
