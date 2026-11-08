# Drama Studio × Google Colab（可重复出片手册）

每次要用「免费 / 低成本 GPU 出片」时，按本文走一遍即可。目标：在 Colab 里跑起 **ComfyUI**，用 **cloudflared** 得到公网 URL，填进 Drama Studio 的 `COMFYUI_SERVER_URL`。

配套笔记本：[`notebooks/comfyui_openmontage_colab.ipynb`](../notebooks/comfyui_openmontage_colab.ipynb)  
总览免费额度：[`FREE_GPU.md`](FREE_GPU.md)

---

## 别人怎么用（社区共识）

公开实践高度一致，OpenMontage 也沿用同一套路：

| 做法 | 代表 | 说明 |
|:---|:---|:---|
| Colab 装 ComfyUI + **cloudflared** → `*.trycloudflare.com` | [nazdridoy/ComfyUI-On-Colab](https://github.com/nazdridoy/ComfyUI-On-Colab)、[atlassc 教程](https://atlassc.net/2025/01/16/deploy-comfyui-on-google-colab.md)、[Stable Diffusion Art](https://stable-diffusion-art.com/comfyui-colab/) | 免注册隧道，URL 会话级，重启会变 |
| **挂载 Google Drive** 持久化模型 | 同上多数 notebook | 否则每次重下几十 GB |
| 免费档用 **量化 / 小模型** | [comfyui_colab_Flux](https://github.com/sayantan-2/comfyui_colab_Flux) 等 | T4≈16GB，大视频权重装不下 |
| 备选隧道 | localtunnel / zrok / ngrok | cloudflared 挂了再换 |

**Drama Studio 额外要求（比「只开网页玩 Comfy」更严）：**

1. 公网 URL 必须能 `GET /system_stats` → HTTP 200（不是登录页 / 404）
2. 当前出片默认认 **MiniMax H3** 本地栈（`fl2va` UNET + Qwen3-VL + video/audio VAE + `MiniMaxH3ImageToVideo` 节点）
3. 把 URL 写进线上密钥：`COMFYUI_SERVER_URL`（及 image/video 同址），`STUDIO_VIDEO_BACKEND=auto` 或 `comfyui`

---

## 重要：显存现实（先看再下模型）

| 运行时 | 大约显存 | 能否跑 Studio 默认 **MiniMax H3** |
|:---|:---|:---|
| Colab **免费 T4** | ~16 GB | **基本不行**（仅 pruned INT8 UNET 就约 20GB+） |
| Colab **Pro / Pro+**（L4 / A100 等） | 24 GB+ | **可以**（用 pruned INT8 + nvfp4 文本编码器） |
| Vast / 自租 4090 | 24 GB | **可以**（我们已验证过） |

免费 Colab 更适合：定妆图（SDXL/RealVis）、或以后若 Studio 接入 **Wan GGUF** 等轻量视频。  
**要稳定 H3 出片：用 Colab Pro（高显存）或租机，不要指望免费 T4。**

---

## 每次开机会话（标准流程）

### 0. 打开笔记本

- 本仓库：上传 / 打开 `notebooks/comfyui_openmontage_colab.ipynb`
- 或社区一键：[ComfyUI-On-Colab](https://colab.research.google.com/github/nazdridoy/ComfyUI-On-Colab/blob/main/ComfyUIonColab.ipynb)（通用 Comfy，再按下面「接 Studio」）

菜单：**Runtime → Change runtime type → GPU**（尽量选高显存；免费档多为 T4）。

### 1. 挂载 Drive（强烈建议）

```text
/content/drive/MyDrive/OpenMontageComfy
```

模型、自定义节点放这里，下次会话只 `git pull` + 启动，不必重下 H3。

### 2. 安装 / 启动 ComfyUI + 隧道

笔记本会：

1. clone ComfyUI（或复用 Drive 里的目录）
2. `pip install -r requirements.txt`
3. `python main.py --listen 127.0.0.1 --port 8188`
4. `cloudflared tunnel --url http://127.0.0.1:8188`
5. 打印一行：`COMFY_URL=https://xxxx.trycloudflare.com`

### 3. 自检（在你电脑或笔记本里）

```bash
curl -sS "$COMFY_URL/system_stats" | head
# 期望 JSON，含 devices / cuda
```

### 4. 写入 Drama Studio

**UI：** 模型配置 → ComfyUI 服务器地址 → 粘贴 `https://xxxx.trycloudflare.com` → 保存并「检测」。

**或 ops / `.env`（宿主）：**

```bash
COMFYUI_SERVER_URL=https://xxxx.trycloudflare.com
COMFYUI_IMAGE_SERVER_URL=https://xxxx.trycloudflare.com
COMFYUI_VIDEO_SERVER_URL=https://xxxx.trycloudflare.com
COMFYUI_VIDEO_MODEL=minimax-h3
STUDIO_VIDEO_BACKEND=auto
```

线上：`STUDIO_URL=https://openmontage.dtok.io ./scripts/restore_studio_keys.sh`  
（若 Cloudflare 挡 urllib，用带浏览器 UA 的 `curl` POST `/api/settings/keys`。）

### 5. 确认 Studio 已认到

```bash
curl -sS -A 'Mozilla/5.0' 'https://openmontage.dtok.io/api/settings/keys?probe=1'
# comfyui.reachable == true
# 有 H3 权重时 videoReady == true
```

---

## MiniMax H3 权重（仅当 GPU ≥ ~24GB）

放到 Comfy 目录（与 [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3) 一致）：

| 文件 | 目录 |
|:---|:---|
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | `models/diffusion_models/` |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | `models/text_encoders/` |
| `minimax_h3_video_vae_fp16.safetensors` | `models/vae/` |
| `minimax_h3_audio_vae_fp32.safetensors` | `models/vae/` |
| （可选）`minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` | `models/loras/` |

合计约 **40GB+**，务必放 Drive。Comfy ≥ 0.30 已带 `MiniMaxH3ImageToVideo` 等原生节点。

---

## 每次收工

1. Colab：**Runtime → Disconnect and delete runtime**（停 GPU 计时）
2. Studio：清空或改掉失效的 `COMFYUI_*_SERVER_URL`（否则 `auto` 会先撞死链再回退 Seedance）
3. Drive 里的模型**保留**，下次只重新跑「启动 + 隧道」单元格

---

## 故障速查

| 现象 | 处理 |
|:---|:---|
| 没有 `trycloudflare.com` | 等 Comfy 完全起来再跑隧道格；或换 localtunnel |
| `/system_stats` 401 | Vast 门户才要 token；Colab 直隧道一般无 auth |
| Studio `reachable: false` | URL 过期 / 会话掉线 → 重新开隧道并更新密钥 |
| CUDA OOM | 免费 T4 不要硬上 H3；换 Pro 高显存或租 4090 |
| 会话无故断开 | 免费档空闲约 90 分钟会踢；保持标签页活跃或缩短任务 |
| 隧道偶发不通 | Cloudflare quick tunnel 不稳属常态；重跑隧道格即可 |

---

## 和其它路径怎么选

1. **只想尽快试一条片、有充值余额** → Vast / RunPod（`scripts/provision_comfy_gpu.py` 可参考）  
2. **愿意点几下、要可重复、少花钱** → **本文 Colab + Drive**（H3 请 Pro）  
3. **只出图** → 不必 Colab；用 NVIDIA / Pollinations 等（见 `FREE_GPU.md`）  
4. **付费稳质量** → Seedance（Volcengine）

把本文 + 笔记本当作「每次开机清单」即可；社区 notebook 可当安装参考，**接 Studio 以本文第 3–5 步为准**。
