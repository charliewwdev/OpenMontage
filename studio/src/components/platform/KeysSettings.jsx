import { useEffect, useState } from "react";
import { CheckCircle2, KeyRound, Loader2, ShieldCheck } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

export function KeysSettings({ config, onUpdated }) {
  const defaults = config?.defaults || {};
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [status, setStatus] = useState(null);
  const [form, setForm] = useState({
    DEEPSEEK_API_KEY: "",
    DEEPSEEK_BASE_URL: defaults.deepseekBaseUrl || "",
    DEEPSEEK_MODEL: defaults.deepseekModel || "",
    VOLCENGINE_API_KEY: "",
  });

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await api("/api/settings/keys");
      setStatus(data.keys);
      setForm((current) => ({
        ...current,
        DEEPSEEK_BASE_URL: data.keys?.deepseek?.baseUrl || current.DEEPSEEK_BASE_URL,
        DEEPSEEK_MODEL: data.keys?.deepseek?.model || current.DEEPSEEK_MODEL,
        DEEPSEEK_API_KEY: "",
        VOLCENGINE_API_KEY: "",
      }));
      onUpdated?.(data);
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        DEEPSEEK_BASE_URL: form.DEEPSEEK_BASE_URL,
        DEEPSEEK_MODEL: form.DEEPSEEK_MODEL,
      };
      if (form.DEEPSEEK_API_KEY.trim()) payload.DEEPSEEK_API_KEY = form.DEEPSEEK_API_KEY.trim();
      if (form.VOLCENGINE_API_KEY.trim()) payload.VOLCENGINE_API_KEY = form.VOLCENGINE_API_KEY.trim();
      const data = await api("/api/settings/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setStatus(data.keys);
      setForm((current) => ({ ...current, DEEPSEEK_API_KEY: "", VOLCENGINE_API_KEY: "" }));
      onUpdated?.(data);
      toast.success("密钥已保存并立即生效");
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    setTesting(true);
    try {
      const data = await api("/api/settings/keys/test", { method: "POST" });
      const ds = data.results?.deepseek;
      const volc = data.results?.volcengine;
      if (ds?.ok && volc?.ok) toast.success("DeepSeek 与火山 Key 检测通过");
      else if (ds?.ok) toast.success(`DeepSeek 可用；火山：${volc?.error || "未配置"}`);
      else toast.error(ds?.error || volc?.error || "检测失败");
      setStatus(data.keys);
      onUpdated?.(data);
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setTesting(false);
    }
  };

  return (
    <PageShell
      eyebrow="Settings"
      title="密钥配置"
      description="一键写入 DeepSeek 与火山方舟密钥。保存后立刻注入服务进程，无需重启容器；密钥落在项目卷的本地加密文件中。"
      actions={
        <>
          <button type="button" className="btn-secondary" disabled={testing || loading} onClick={() => void test()}>
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
            检测连通
          </button>
          <button type="button" className="btn-primary" disabled={saving || loading} onClick={() => void save()}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
            一键保存并生效
          </button>
        </>
      }
    >
      {loading ? (
        <div className="panel flex items-center gap-2 px-5 py-10 text-sm text-[var(--muted)]">
          <Loader2 className="h-4 w-4 animate-spin" /> 读取配置…
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[1.2fr_.8fr]">
          <section className="panel space-y-5 p-5 md:p-6">
            <div>
              <div className="label">DeepSeek</div>
              <h2 className="text-lg font-semibold">剧本 / 拆镜文本模型</h2>
            </div>
            <label>
              <span className="label">API Key {status?.deepseek?.configured ? `· 已配置 ${status.deepseek.masked}` : "· 未配置"}</span>
              <input
                className="field"
                type="password"
                autoComplete="off"
                placeholder={status?.deepseek?.configured ? "留空则保留现有 Key" : "sk-..."}
                value={form.DEEPSEEK_API_KEY}
                onChange={(e) => setForm({ ...form, DEEPSEEK_API_KEY: e.target.value })}
              />
            </label>
            <div className="grid gap-4 md:grid-cols-2">
              <label>
                <span className="label">Base URL</span>
                <input
                  className="field"
                  value={form.DEEPSEEK_BASE_URL}
                  onChange={(e) => setForm({ ...form, DEEPSEEK_BASE_URL: e.target.value })}
                />
              </label>
              <label>
                <span className="label">Model</span>
                <input
                  className="field"
                  value={form.DEEPSEEK_MODEL}
                  onChange={(e) => setForm({ ...form, DEEPSEEK_MODEL: e.target.value })}
                />
              </label>
            </div>

            <div className="border-t border-[var(--line)] pt-5">
              <div className="label">Volcengine / Ark</div>
              <h2 className="text-lg font-semibold">Seedream 出图 · Seedance 视频</h2>
            </div>
            <label>
              <span className="label">
                API Key {status?.volcengine?.configured ? `· 已配置 ${status.volcengine.masked}` : "· 未配置"}
              </span>
              <input
                className="field"
                type="password"
                autoComplete="off"
                placeholder={status?.volcengine?.configured ? "留空则保留现有 Key" : "火山方舟 API Key"}
                value={form.VOLCENGINE_API_KEY}
                onChange={(e) => setForm({ ...form, VOLCENGINE_API_KEY: e.target.value })}
              />
            </label>
          </section>

          <aside className="space-y-4">
            <section className="panel p-5">
              <div className="label">Status</div>
              <ul className="mt-3 space-y-3 text-sm">
                {[
                  ["DeepSeek", status?.deepseek?.configured],
                  ["Seedream / Seedance", status?.volcengine?.configured],
                ].map(([label, ok]) => (
                  <li key={label} className="flex items-center justify-between rounded-xl border border-[var(--line)] px-3 py-2.5">
                    <span>{label}</span>
                    <span className={ok ? "text-[var(--ok)]" : "text-[var(--muted)]"}>
                      {ok ? (
                        <span className="inline-flex items-center gap-1">
                          <CheckCircle2 className="h-3.5 w-3.5" /> 已就绪
                        </span>
                      ) : (
                        "未配置"
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
            <section className="panel-muted p-4 text-xs leading-6 text-[var(--muted)]">
              <strong className="block text-[var(--ink)]">说明</strong>
              密钥保存在 `PROJECTS_ROOT/.studio_secrets.json`，不会回显明文。Coolify 环境变量仍可覆盖；页面保存会写入卷并热更新当前进程。
            </section>
          </aside>
        </div>
      )}
    </PageShell>
  );
}
