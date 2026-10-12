import { useRef, useState } from "react";
import { ArrowLeft, Clapperboard, FileUp, Loader2, Plus } from "lucide-react";
import { api } from "../api";

const CREATION_STEPS = ["专业剧本", "角色造型", "空镜场景", "关键道具", "分镜视频", "剪辑成片"];

const GENRES = ["都市逆袭", "重生复仇", "甜宠恋爱", "悬疑反转", "古风权谋", "职场商战", "玄幻修仙"];

const STYLES = [
  { id: "urban-night", label: "都市夜戏", value: "当代都市夜戏，霓虹冷暖对比，电影感浅景深" },
  { id: "warm-drama", label: "暖调剧情", value: "暖调室内光，柔和肤色，电视剧质感" },
  { id: "noir", label: "悬疑冷调", value: "冷调悬疑，硬光阴影，胶片颗粒" },
  { id: "costume", label: "古风雅致", value: "古风雅致，绢帛质感，柔光写意" },
];

const BRIEF_PLACEHOLDER = `粘贴小说正文，或写一句话故事想法。

【主角设定】
• 姓名、身份、核心困境与目标

【故事框架】
• 开场危机 / 核心冲突 / 反转与结局

【可选】
• 必须保留的情节、禁忌、感情线`;

export function CreateProjectPage({ onBack, onCreated }) {
  const fileRef = useRef(null);
  const [creating, setCreating] = useState(false);
  const [err, setErr] = useState("");
  const [form, setForm] = useState({
    title: "",
    brief: "",
    genre: GENRES[0],
    visualStyle: STYLES[0].value,
    ratio: "9:16",
  });

  const onFile = async (file) => {
    if (!file) return;
    const text = await file.text();
    setForm((f) => ({
      ...f,
      brief: text.slice(0, 100_000),
      title: f.title || file.name.replace(/\.(txt|md|text)$/i, ""),
    }));
  };

  const create = async () => {
    if (!form.title.trim()) return setErr("先给项目起个名字");
    if (form.brief.trim().length < 20) return setErr("请粘贴小说或至少写 20 字创作需求");
    setCreating(true);
    setErr("");
    try {
      const res = await api("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: form.title.trim(),
          source_text: form.brief.trim(),
          aspect_ratio: form.ratio,
          visual_style: form.visualStyle,
          genre: form.genre,
        }),
      });
      onCreated?.(res.created.name, res.bundle);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setCreating(false);
    }
  };

  return (
    <main className="mx-auto min-h-screen max-w-[1500px] px-4 py-5 md:px-8 md:py-8">
      <header className="overflow-hidden rounded-[26px] bg-[var(--navy)] text-white shadow-float">
        <div className="grid lg:grid-cols-[1fr_360px]">
          <div className="p-6 md:p-9">
            <button
              type="button"
              onClick={onBack}
              className="inline-flex items-center gap-2 text-xs font-semibold text-white/55 transition hover:text-white"
            >
              <ArrowLeft className="h-4 w-4" /> 返回片库
            </button>
            <div className="mt-10 flex items-center gap-3 text-xs font-bold uppercase tracking-[.2em] text-white/45">
              <Clapperboard className="h-4 w-4 text-[var(--timecode)]" /> New production
            </div>
            <h1 className="display-type mt-3 text-4xl font-semibold md:text-5xl">从小说建立新片场</h1>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-white/60 md:text-base">
              上传或粘贴小说正文 → 自动拆场次、角色、场景、道具与分镜 → 生成镜头板与成片。覆盖完整短剧制作六步。
            </p>
          </div>
          <div className="relative border-t border-white/10 bg-[var(--navy-soft)] p-6 lg:border-l lg:border-t-0 md:p-8">
            <div className="timecode text-[10px] text-[var(--timecode)]">PIPELINE / 06</div>
            <ol className="mt-5 space-y-2">
              {CREATION_STEPS.map((label, i) => (
                <li key={label} className="flex items-center gap-3 border-b border-white/10 py-2 text-sm">
                  <span className="timecode w-7 text-xs text-white/35">{String(i + 1).padStart(2, "0")}</span>
                  {label}
                </li>
              ))}
            </ol>
          </div>
        </div>
      </header>

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <section className="panel p-5 md:p-7">
            <div className="label">Basic setup</div>
            <h2 className="display-type text-2xl font-semibold">故事身份</h2>
            <div className="mt-5 space-y-5">
              <label>
                <span className="label">片名</span>
                <input
                  className="field"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  placeholder="例如：雨夜最后一班车"
                  autoFocus
                  disabled={creating}
                />
              </label>
              <div>
                <span className="label">题材</span>
                <div className="mt-2 flex flex-wrap gap-2">
                  {GENRES.map((g) => (
                    <button
                      key={g}
                      type="button"
                      disabled={creating}
                      className={`rounded-xl border px-3 py-2 text-sm font-semibold ${
                        form.genre === g
                          ? "border-[var(--projector)] bg-[var(--projector)]/15 text-[var(--navy)]"
                          : "border-[var(--line)] bg-white text-[var(--muted)]"
                      }`}
                      onClick={() => setForm({ ...form, genre: g })}
                    >
                      {g}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </section>

          <section className="panel p-5 md:p-7">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="label">Novel / brief</div>
                <h2 className="display-type text-2xl font-semibold">小说正文 / 创作需求</h2>
                <p className="mt-1 text-sm text-[var(--muted)]">支持 .txt / .md 上传，或直接粘贴。空行分段即场次。</p>
              </div>
              <div className="flex gap-2">
                <input
                  ref={fileRef}
                  type="file"
                  accept=".txt,.md,.text,text/plain"
                  className="hidden"
                  onChange={(e) => void onFile(e.target.files?.[0])}
                />
                <button type="button" className="btn-secondary" disabled={creating} onClick={() => fileRef.current?.click()}>
                  <FileUp className="h-4 w-4" /> 上传小说
                </button>
              </div>
            </div>
            <textarea
              className="field mt-5 min-h-[420px] resize-y leading-7"
              value={form.brief}
              onChange={(e) => setForm({ ...form, brief: e.target.value })}
              placeholder={BRIEF_PLACEHOLDER}
              maxLength={100_000}
              disabled={creating}
            />
            <div className="mt-3 flex justify-between text-xs text-[var(--muted)]">
              <span>创建后进入剧本页，可继续编辑并推进六步。</span>
              <span className="timecode">{form.brief.length} / 100000</span>
            </div>
          </section>

          <section className="panel p-5 md:p-7">
            <div className="label">Visual language</div>
            <h2 className="display-type text-2xl font-semibold">视觉风格</h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {STYLES.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  disabled={creating}
                  className={`rounded-2xl border p-4 text-left ${
                    form.visualStyle === s.value
                      ? "border-[var(--projector)] bg-[var(--projector)]/10"
                      : "border-[var(--line)] hover:bg-[var(--panel-muted)]"
                  }`}
                  onClick={() => setForm({ ...form, visualStyle: s.value })}
                >
                  <div className="text-sm font-semibold">{s.label}</div>
                  <div className="mt-1 text-xs leading-5 text-[var(--muted)]">{s.value}</div>
                </button>
              ))}
            </div>
          </section>
        </div>

        <aside className="space-y-5 xl:sticky xl:top-6 xl:self-start">
          <section className="panel p-5">
            <div className="label">Frame</div>
            <h2 className="display-type text-xl font-semibold">画面比例</h2>
            <div className="mt-4 flex flex-col gap-2">
              {[
                ["9:16", "竖屏短剧"],
                ["16:9", "横屏剧集"],
                ["1:1", "方屏社媒"],
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  disabled={creating}
                  className={`rounded-xl border px-4 py-3 text-left text-sm font-semibold ${
                    form.ratio === value
                      ? "border-[var(--projector)] bg-[var(--projector)]/15 text-[var(--navy)]"
                      : "border-[var(--line)] text-[var(--muted)]"
                  }`}
                  onClick={() => setForm({ ...form, ratio: value })}
                >
                  {label} · {value}
                </button>
              ))}
            </div>
          </section>

          <section className="panel p-5">
            {err ? <p className="mb-3 text-sm text-[var(--danger)]">{err}</p> : null}
            <button
              type="button"
              className="btn-primary w-full !border-[var(--projector)] !bg-[var(--projector)] !text-[var(--navy)]"
              disabled={creating}
              onClick={() => void create()}
            >
              {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              {creating ? "正在拆解小说…" : "创建片场并拆解"}
            </button>
            <p className="mt-3 text-xs leading-5 text-[var(--muted)]">
              无需登录。本地拆章拆镜后，可在分镜页批量出板，剪辑室导出 MP4。
            </p>
          </section>
        </aside>
      </div>
    </main>
  );
}
