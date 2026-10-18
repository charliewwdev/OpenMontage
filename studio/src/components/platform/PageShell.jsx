export function PageShell({ eyebrow, title, description, actions, children }) {
  return (
    <main className="min-h-screen p-2 md:p-3">
      <div className="yc-frame mx-0 min-h-[calc(100vh-2.5rem)] w-full max-w-none overflow-hidden p-3 md:p-4">
        <header className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            {eyebrow ? <div className="label !mb-1">{eyebrow}</div> : null}
            <h1 className="text-2xl font-semibold md:text-3xl">{title}</h1>
            {description ? <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--muted)]">{description}</p> : null}
          </div>
          {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
        </header>
        {children}
      </div>
    </main>
  );
}
