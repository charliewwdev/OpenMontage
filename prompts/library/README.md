# 提示词库 / Prompt Library

素材页「提示词库」标签用到的数据，以及重新生成这些数据所需的原始文件。
Source files for the Assets page "Prompt Library" tab, and what is needed to rebuild it.

| 路径 / Path | 内容 / Contents |
|:--|:--|
| `originals/*.txt` | OpenMontage 原创提示词（CC BY 4.0） / OpenMontage original prompts (CC BY 4.0) |
| `curation/` | 为英文第三方提示词撰写的中文翻译（AI 辅助）与被过滤条目清单 / Chinese translations (AI-assisted) of English third-party prompts, and the list of filtered-out entries |
| `ATTRIBUTION.md` | 每个来源与每条第三方条目的出处、许可和改动 / Source, license and changes for every source and third-party entry |
| `LICENSES/` | 第三方许可全文 / Third-party license texts |
| `../../studio/config/prompt_library/` | 生成结果，随 studio 镜像发布 / Generated data shipped with the studio image |

重新生成 / Rebuild:

```bash
scripts/fetch_prompt_sources.sh      # third-party files at pinned revisions → prompts/library/sources/ (git-ignored)
python3 scripts/import_prompts.py    # needs pandas + pyarrow for the Rapidata parquet
```

许可 / Licensing: 原创条目以 CC BY 4.0 发布；第三方条目保留原许可（Apache-2.0、CC BY 4.0、CC0 1.0），逐条见 `ATTRIBUTION.md`。
OpenMontage 代码本身仍按仓库根目录的 AGPL-3.0 `LICENSE` 授权。
Original entries are CC BY 4.0; third-party entries keep their own licenses (Apache-2.0, CC BY 4.0, CC0 1.0), listed per entry in `ATTRIBUTION.md`.
The OpenMontage code itself remains under the AGPL-3.0 `LICENSE` at the repository root.
