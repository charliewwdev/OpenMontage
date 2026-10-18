export function PageShell({ eyebrow, title, description, actions, children, wide = false }) {
  return (
    <main className={`min-h-screen ${wide ? "p-2 md:p-3" : "p-3 md:p-5 lg:p-6"}`}>
      <div
        className={`yc-frame min-h-[calc(100vh-2.5rem)] overflow-hidden ${
          wide
            ? "mx-0 w-full max-w-none p-3 md:p-4"
            : "mx-auto max-w-[1480px] p-4 md:p-7"
        }`}
      >
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
