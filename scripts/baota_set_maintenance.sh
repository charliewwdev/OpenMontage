#!/usr/bin/env bash
# Install OpenMontage maintenance.html + nginx error_page on aaPanel (宝塔).
# Avoids the default white "502 Bad Gateway · nginx" page during Coolify redeploys.
#
# Requires in env (e.g. dtok-workspace/.env):
#   BT_PANEL_URL  BT_PANEL_USER  BT_PANEL_PASS
#
# Usage:
#   set -a; source /path/to/dtok-workspace/.env; set +a
#   ./scripts/baota_set_maintenance.sh
#   SITE_NAME=openmontage.dtok.io ./scripts/baota_set_maintenance.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HTML_SRC="${MAINTENANCE_HTML:-$ROOT/studio/public/maintenance.html}"
SITE_NAME="${SITE_NAME:-openmontage.dtok.io}"
UPSTREAM="${MAINTENANCE_UPSTREAM:-127.0.0.1:8787}"

: "${BT_PANEL_URL:?BT_PANEL_URL required}"
: "${BT_PANEL_USER:?BT_PANEL_USER required}"
: "${BT_PANEL_PASS:?BT_PANEL_PASS required}"

if [[ ! -f "$HTML_SRC" ]]; then
  echo "missing $HTML_SRC"
  exit 1
fi

export BT_PANEL_URL BT_PANEL_USER BT_PANEL_PASS SITE_NAME UPSTREAM HTML_SRC

python3 <<'PY'
import hashlib, json, os, re, ssl, time, urllib.error, urllib.parse, urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

base = os.environ["BT_PANEL_URL"].rstrip("/")
user = os.environ["BT_PANEL_USER"]
password = os.environ["BT_PANEL_PASS"]
site = os.environ["SITE_NAME"]
upstream = os.environ["UPSTREAM"]
html = Path(os.environ["HTML_SRC"]).read_text(encoding="utf-8")

ctx = ssl._create_unverified_context()
jar = CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=ctx),
    urllib.request.HTTPCookieProcessor(jar),
)
UA = "Mozilla/5.0 OpenMontage-maintenance/1.0"


def post(path, data: dict, retries=2):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        base + path,
        data=body,
        method="POST",
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"},
    )
    last = None
    for _ in range(retries + 1):
        try:
            with opener.open(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
        except Exception as exc:
            last = exc
            time.sleep(1)
    raise RuntimeError(f"POST {path} failed: {last}")


# md5 double-hash password (classic Baota login)
pwd_md5 = hashlib.md5(password.encode()).hexdigest()
login = post("/login", {"username": user, "password": pwd_md5})
if not (login.get("status") is True or login.get("msg") in ("登录成功", "Success", True) or "success" in str(login).lower()):
    # some panels want plain password
    login2 = post("/login", {"username": user, "password": password})
    if not (login2.get("status") is True or "成功" in str(login2.get("msg") or "")):
        raise SystemExit(f"baota login failed: {login} / {login2}")

sites = post("/data?action=getData", {"table": "sites", "limit": 100, "p": 1, "search": site})
rows = sites.get("data") or sites.get("list") or []
hit = None
for row in rows:
    name = str(row.get("name") or row.get("siteName") or "")
    if name == site or site in name:
        hit = row
        break
if not hit:
    raise SystemExit(f"site not found: {site} (got {len(rows)} rows)")

site_id = hit.get("id")
print("site", site, "id", site_id)

# Prefer site root under wwwroot
path_info = post("/site?action=GetDirUserINI", {"path": f"/www/wwwroot/{site}", "id": site_id})
root = f"/www/wwwroot/{site}"
# Save maintenance.html
save = post(
    "/files?action=SaveFileBody",
    {
        "path": f"{root}/maintenance.html",
        "data": html,
        "encoding": "utf-8",
    },
)
print("save_html", save.get("status"), save.get("msg") or save)

# Patch nginx site config: error_page + proxy_intercept_errors
conf_path = f"/www/server/panel/vhost/nginx/{site}.conf"
conf_get = post("/files?action=GetFileBody", {"path": conf_path})
conf = conf_get.get("data") or ""
if not conf:
    # alternate path
    conf_path = f"/www/server/panel/vhost/nginx/proxy/{site}.conf"
    conf_get = post("/files?action=GetFileBody", {"path": conf_path})
    conf = conf_get.get("data") or ""
if not conf:
    raise SystemExit(f"nginx conf not readable for {site}")

snippet = f"""
    # OpenMontage: branded standby (never white nginx 502 page)
    proxy_intercept_errors on;
    error_page 502 503 504 =200 /maintenance.html;
    location = /maintenance.html {{
        root {root};
        default_type text/html;
        charset utf-8;
        add_header Cache-Control "no-store" always;
    }}
""".rstrip()

if "error_page 502 503 504 =200 /maintenance.html" in conf or "error_page 502 503 504 /maintenance.html" in conf:
    # Upgrade legacy snippet to =200 if needed
    if "error_page 502 503 504 =200 /maintenance.html" not in conf and "error_page 502 503 504 /maintenance.html" in conf:
        conf = conf.replace(
            "error_page 502 503 504 /maintenance.html;",
            "error_page 502 503 504 =200 /maintenance.html;",
        )
        conf = re.sub(
            r"location = /maintenance\.html \{\s*root [^;]+;\s*internal;\s*\}",
            f"location = /maintenance.html {{\n        root {root};\n        default_type text/html;\n        charset utf-8;\n        add_header Cache-Control \"no-store\" always;\n    }}",
            conf,
            count=1,
        )
        save_conf = post(
            "/files?action=SaveFileBody",
            {"path": conf_path, "data": conf, "encoding": "utf-8"},
        )
        print("upgraded_error_page_to_200", save_conf.get("status"))
    else:
        print("nginx already has maintenance error_page")
else:
    # Insert before the last closing brace of the first server block if possible
    if "proxy_pass" in conf and "server {" in conf:
        conf2 = conf
        # Prefer placing just inside server { after listen/server_name
        m = re.search(r"(server_name\s+[^;]+;)", conf2)
        if m:
            insert_at = m.end()
            conf2 = conf2[:insert_at] + "\n" + snippet + conf2[insert_at:]
        else:
            conf2 = conf2.replace("server {", "server {\n" + snippet, 1)
        save_conf = post(
            "/files?action=SaveFileBody",
            {"path": conf_path, "data": conf2, "encoding": "utf-8"},
        )
        print("save_conf", conf_path, save_conf.get("status"), save_conf.get("msg") or save_conf)
        reload = post("/system?action=ServiceAdmin", {"name": "nginx", "type": "reload"})
        print("nginx_reload", reload.get("status"), reload.get("msg") or reload)
    else:
        print("WARN: could not auto-patch nginx; paste snippet manually:")
        print(snippet)

# Also expose maintenance as public (non-internal) so users can open /maintenance.html
# Re-save location without internal for direct access during outages when root can serve static.
# Many Baota reverse-proxy sites already map / to upstream only — add a public location.
conf_get = post("/files?action=GetFileBody", {"path": conf_path})
conf = conf_get.get("data") or conf
public_loc = f"""
    location = /maintenance.html {{
        root {root};
        default_type text/html;
    }}
"""
if "location = /maintenance.html" in conf and "internal;" in conf:
    conf = conf.replace(
        f"""location = /maintenance.html {{
        root {root};
        internal;
    }}""",
        public_loc.strip(),
    )
    # Keep error_page; allow both internal rewrite and public GET
    if "proxy_intercept_errors on" not in conf:
        pass
    # Add error_page still pointing to /maintenance.html
    save_conf = post(
        "/files?action=SaveFileBody",
        {"path": conf_path, "data": conf, "encoding": "utf-8"},
    )
    post("/system?action=ServiceAdmin", {"name": "nginx", "type": "reload"})
    print("public_maintenance_location", save_conf.get("status"))

print("OK maintenance installed for", site, "upstream", upstream)
print("Verify: curl -sI https://" + site + "/maintenance.html | head")
PY
