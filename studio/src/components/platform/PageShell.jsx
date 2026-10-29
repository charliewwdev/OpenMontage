export function PageShell({ eyebrow, title, description, actions, children }) {
  return (
    <main className="min-h-screen p-1.5 md:p-2">
      <div className="yc-frame mx-0 min-h-[calc(100vh-1.75rem)] w-full max-w-none overflow-hidden p-2.5 md:p-3">
        <header className="mb-3 flex flex-col gap-2 md:mb-4 md:flex-row md:items-end md:justify-between">
          <div className="min-w-0">
            {eyebrow ? <div className="label !mb-0.5">{eyebrow}</div> : null}
            <h1 className="text-[1.15rem] font-semibold leading-tight md:text-[1.35rem]">{title}</h1>
            {description ? (
              <p className="mt-1 max-w-3xl text-[12px] leading-5 text-[var(--muted)]">{description}</p>
            ) : null}
          </div>
          {actions ? <div className="flex flex-wrap gap-1.5">{actions}</div> : null}
        </header>
        {children}
      </div>
    </main>
  );
}
