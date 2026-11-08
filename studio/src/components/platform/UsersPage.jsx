import { useEffect, useState } from "react";
import { ExternalLink, Github, Loader2, Star, Users } from "lucide-react";
import { api } from "../../api";
import { PageShell } from "./PageShell";
import { tr, useLocale } from "../../lib/i18n";

export function UsersPage({ config }) {
  useLocale();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [roster, setRoster] = useState({ total: 0, users: [], starUrl: "", repo: "" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError("");
      try {
        const data = await api("/api/community/users?limit=200");
        if (!cancelled) {
          setRoster({
            total: Number(data?.total) || 0,
            users: Array.isArray(data?.users) ? data.users : [],
            starUrl: data?.starUrl || config?.links?.github || "https://github.com/charliewwdev/OpenMontage",
            repo: data?.repo || "charliewwdev/OpenMontage",
          });
        }
      } catch (e) {
        if (!cancelled) setError(String(e.message || e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [config?.links?.github]);

  const starUrl = roster.starUrl || config?.links?.github || "https://github.com/charliewwdev/OpenMontage";

  return (
    <PageShell
      eyebrow="Community"
      title={tr("ui_users_title")}
      description={tr("ui_users_description")}
      actions={
        <a className="btn-secondary inline-flex items-center gap-2" href={starUrl} target="_blank" rel="noreferrer">
          <Github className="h-3.5 w-3.5" />
          {tr("ui_users_open_repo")}
          <ExternalLink className="h-3 w-3 opacity-60" />
        </a>
      }
    >
      {loading ? (
        <div className="panel flex items-center gap-2 px-5 py-10 text-sm text-[var(--muted)]">
          <Loader2 className="h-4 w-4 animate-spin" /> {tr("ui_users_loading")}
        </div>
      ) : error ? (
        <div className="panel px-5 py-8 text-sm text-rose-300">{error}</div>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-white/10 bg-white/[.03] px-4 py-3 text-sm text-white/70">
            <Users className="h-4 w-4 text-[#c4b5fd]" />
            <span>
              {tr("ui_users_total", { count: roster.total })}
              {roster.repo ? <span className="text-white/35"> · {roster.repo}</span> : null}
            </span>
          </div>

          {roster.users.length === 0 ? (
            <div className="panel flex flex-col items-start gap-3 px-5 py-10">
              <Star className="h-5 w-5 text-amber-300" />
              <p className="text-sm text-white/70">{tr("ui_users_empty")}</p>
              <a className="btn-primary inline-flex items-center gap-2" href={starUrl} target="_blank" rel="noreferrer">
                <Github className="h-4 w-4" />
                {tr("ui_users_be_first")}
              </a>
            </div>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {roster.users.map((user) => (
                <a
                  key={user.login}
                  href={user.profileUrl || `https://github.com/${user.login}`}
                  target="_blank"
                  rel="noreferrer"
                  className="panel flex items-center gap-3 p-3 transition hover:border-white/25 hover:bg-white/[.04]"
                >
                  <img
                    src={user.avatarUrl || `https://github.com/${user.login}.png?size=96`}
                    alt=""
                    className="h-10 w-10 rounded-full bg-white/10 object-cover"
                    loading="lazy"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-white">@{user.login}</div>
                    <div className="mt-0.5 flex items-center gap-1 text-[11px] text-amber-200/80">
                      <Star className="h-3 w-3" />
                      {tr("ui_users_starred")}
                    </div>
                  </div>
                  <ExternalLink className="h-3.5 w-3.5 shrink-0 text-white/30" />
                </a>
              ))}
            </div>
          )}
        </>
      )}
    </PageShell>
  );
}
