# ATTRIBUTION / 署名与许可

提示词库中的原创条目（`source.name` 为 `OpenMontage`）以 **CC BY 4.0** 发布；OpenMontage 代码本身仍按仓库根目录的 AGPL-3.0 `LICENSE` 授权。
第三方提示词保留其原始许可，下表逐条列出来源、许可与改动说明。中文翻译由 OpenMontage 完成，标注为 `translated: machine`（AI 辅助翻译）。

Original prompt entries (source `OpenMontage`) are released under **CC BY 4.0**; the OpenMontage code itself stays under the AGPL-3.0 `LICENSE` at the repository root.
Third-party prompts keep their original licenses. Every imported entry is listed below with its source, license and changes.
Chinese translations of English-only prompts were written by OpenMontage (`translated: machine`, AI-assisted). No third-party media is rehosted.

## Sources / 来源

| Source | License | Revision | Entries | License evidence |
|---|---|---|---|---|
| [OpenMontage](https://github.com/charliewwdev/OpenMontage) | [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) | `—` | 272 | Original content written for this library; released under CC BY 4.0. |
| [Vchitect/VBench prompt suite](https://github.com/Vchitect/VBench/tree/master/prompts) | [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) | `fd18b3d055cb` | 134 | GitHub API license=Apache-2.0; LICENSE file at pinned commit. |
| [LichAmnesia/awesome-ad-video-prompts](https://github.com/LichAmnesia/awesome-ad-video-prompts) | [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) | `ac5b61177a81` | 17 | LICENSE file: CC BY 4.0, 'All prompts in this repository are original works'. |
| [Rapidata/text-2-video-human-preferences-veo3](https://huggingface.co/datasets/Rapidata/text-2-video-human-preferences-veo3) | [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) | `51fd4dfc8b7c` | 20 | Hugging Face dataset card: license: apache-2.0 (prompt text only; videos not used). |
| [fka/prompts.chat](https://huggingface.co/datasets/fka/prompts.chat) | [CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/) | `be0e61647a60` | 4 | Hugging Face dataset card: license: cc0-1.0. |

Apache-2.0 sources (VBench, Rapidata): a copy of the Apache License 2.0 is in `LICENSES/Apache-2.0.txt`. VBench prompts are used verbatim (English and the official Chinese version). Rapidata prompts are used verbatim with an added Chinese translation; the Rapidata videos are not included.

License texts / 许可全文: `LICENSES/Apache-2.0.txt` (Apache License 2.0, identical to the VBench `LICENSE` at the pinned commit), `LICENSES/CC-BY-4.0.txt` (CC BY 4.0 legal code), `LICENSES/awesome-ad-video-prompts-LICENSE.txt` (the LichAmnesia/awesome-ad-video-prompts `LICENSE` file, kept verbatim), `LICENSES/CC0-1.0.txt` (CC0 1.0).

## Not imported / 未收录的来源

- songguoxs/awesome-video-prompts: no license
- WenhaoWang/VidProM: CC BY-NC 4.0 (non-commercial)
- facebookresearch/MovieGenBench: CC BY-NC 4.0 (non-commercial)
- Gustavosta/Stable-Diffusion-Prompts: license unknown
- YouMind-OpenLab/awesome-seedance-2-prompts, ZeroLu/awesome-seedance: repo license does not clearly cover third-party creators' prompts
- ai-boost/awesome-image-video-prompts: GPL-3.0; kept out to keep the dataset under permissive terms

## Per-entry list / 逐条清单

| id | Source | Original reference | License | Changes |
|---|---|---|---|---|
| `rapidata-002` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `rapidata-003` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `rapidata-009` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `rapidata-001` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `rapidata-014` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `rapidata-016` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `rapidata-017` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `vbench-act-002` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 159 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-040` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 200 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-043` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 204 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-051` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 212 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-085` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 247 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `rapidata-004` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `vbench-act-004` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 162 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-019` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 178 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-021` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 180 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-070` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 232 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-084` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 246 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `rapidata-018` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `vbench-act-006` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 165 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-010` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 169 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-022` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 181 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-034` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 193 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-041` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 202 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-048` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 209 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-049` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 210 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-052` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 213 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-053` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 214 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-054` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 215 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-056` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 217 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-058` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 219 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-059` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 220 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-060` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 221 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-061` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 222 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-063` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 224 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-064` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 225 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-066` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 227 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-067` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 228 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-069` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 230 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-079` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 241 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-090` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 252 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-092` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 254 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-093` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 255 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-094` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 256 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-008` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 167 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-035` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 195 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-071` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 233 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `rapidata-005` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `rapidata-006` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `rapidata-011` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `rapidata-012` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `rapidata-013` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `vbench-act-005` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 163 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-007` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 166 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-013` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 172 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-015` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 174 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-018` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 177 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-023` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 182 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-027` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 186 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-030` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 189 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-032` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 191 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-033` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 192 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-037` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 197 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-042` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 203 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-046` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 207 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-050` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 211 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-062` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 223 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-073` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 235 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-080` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 242 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-081` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 243 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-089` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 251 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-091` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 253 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `rapidata-015` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `vbench-act-026` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 185 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-039` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 199 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-065` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 226 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-077` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 239 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-078` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 240 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-086` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 248 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `promptschat-004` | fka/prompts.chat | prompts.csv › act='Romantic Rainy Scene Video' | CC0-1.0 | Chinese translation added |
| `vbench-act-055` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 216 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-088` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 250 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `rapidata-007` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `rapidata-008` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `rapidata-010` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `rapidata-020` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `vbench-act-001` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 158 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-003` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 160 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-009` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 168 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-011` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 170 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-012` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 171 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-014` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 173 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-016` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 175 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-017` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 176 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-020` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 179 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-024` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 183 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-025` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 184 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-028` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 187 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-029` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 188 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-031` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 190 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-036` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 196 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-038` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 198 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-044` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 205 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-045` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 206 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-047` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 208 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-057` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 218 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-068` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 229 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-072` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 234 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-074` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 236 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-075` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 237 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-076` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 238 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-082` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 244 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-083` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 245 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-087` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 249 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-act-095` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 257 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `promptschat-001` | fka/prompts.chat | prompts.csv › act='Screenwriter' | CC0-1.0 | Chinese translation added |
| `promptschat-003` | fka/prompts.chat | prompts.csv › act='Screenplay Script with Cinematography Details' | CC0-1.0 | Chinese translation added |
| `vbench-cam-008` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 591 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-018` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 601 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-028` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 661 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-004` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 587 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-005` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 588 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-014` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 597 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-015` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 598 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-024` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 657 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-025` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 658 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-003` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 586 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-013` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 596 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-023` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 656 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-002` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 585 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-012` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 595 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-022` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 655 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-010` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 593 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-020` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 603 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-030` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 663 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-001` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 584 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-011` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 594 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-021` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 654 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-009` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 592 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-019` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 602 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-029` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 662 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-006` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 589 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-007` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 590 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-016` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 599 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-017` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 600 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-026` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 659 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-cam-027` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 660 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `rapidata-019` | Rapidata/text-2-video-human-preferences-veo3 | data/train-00000-of-00001.parquet › prompt | Apache-2.0 | Chinese translation added |
| `vbench-style-001` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 557 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-style-002` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 558 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-style-003` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 559 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-style-004` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 560 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-style-005` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 561 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-style-006` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 562 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-style-007` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 563 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-style-008` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 564 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `vbench-style-009` | Vchitect/VBench prompt suite | prompts/all_dimension.txt line 565 (+ all_dimension_cn.txt) | Apache-2.0 | verbatim |
| `promptschat-002` | fka/prompts.chat | prompts.csv › act='6-Panel Storyboard Mastery' | CC0-1.0 | Chinese translation added |
| `lich-coffee-bloom-resurrection` | LichAmnesia/awesome-ad-video-prompts | prompts.json › before-after › coffee-bloom-resurrection | CC-BY-4.0 | Chinese translation added |
| `lich-dull-skin-to-glow` | LichAmnesia/awesome-ad-video-prompts | prompts.json › before-after › dull-skin-to-glow | CC-BY-4.0 | Chinese translation added |
| `lich-sneaker-out-of-mud` | LichAmnesia/awesome-ad-video-prompts | prompts.json › before-after › sneaker-out-of-mud | CC-BY-4.0 | Chinese translation added |
| `lich-cold-brew-pour-cascade` | LichAmnesia/awesome-ad-video-prompts | prompts.json › food-beverage › cold-brew-pour-cascade | CC-BY-4.0 | Chinese translation added |
| `lich-espresso-pour-crema-physics` | LichAmnesia/awesome-ad-video-prompts | prompts.json › product-showcase › espresso-pour-crema-physics | CC-BY-4.0 | Chinese translation added |
| `lich-honey-drizzle-on-toast` | LichAmnesia/awesome-ad-video-prompts | prompts.json › food-beverage › honey-drizzle-on-toast | CC-BY-4.0 | Chinese translation added |
| `lich-ramen-steam-ritual` | LichAmnesia/awesome-ad-video-prompts | prompts.json › food-beverage › ramen-steam-ritual | CC-BY-4.0 | Chinese translation added |
| `lich-black-serum-cold-marble` | LichAmnesia/awesome-ad-video-prompts | prompts.json › luxury-premium › black-serum-cold-marble | CC-BY-4.0 | Chinese translation added |
| `lich-espresso-slow-pour` | LichAmnesia/awesome-ad-video-prompts | prompts.json › luxury-premium › espresso-slow-pour | CC-BY-4.0 | Chinese translation added |
| `lich-sneaker-wet-concrete` | LichAmnesia/awesome-ad-video-prompts | prompts.json › luxury-premium › sneaker-wet-concrete | CC-BY-4.0 | Chinese translation added |
| `lich-frost-glass-serum-condensation-macro` | LichAmnesia/awesome-ad-video-prompts | prompts.json › product-showcase › frost-glass-serum-condensation-macro | CC-BY-4.0 | Chinese translation added |
| `lich-sneaker-360-turntable-studio` | LichAmnesia/awesome-ad-video-prompts | prompts.json › product-showcase › sneaker-360-turntable-studio | CC-BY-4.0 | Chinese translation added |
| `lich-bathroom-mirror-skincare-truth` | LichAmnesia/awesome-ad-video-prompts | prompts.json › ugc-authentic › bathroom-mirror-skincare-truth | CC-BY-4.0 | Chinese translation added |
| `lich-desk-coffee-morning-ritual` | LichAmnesia/awesome-ad-video-prompts | prompts.json › ugc-authentic › desk-coffee-morning-ritual | CC-BY-4.0 | Chinese translation added |
| `lich-sneaker-unboxing-on-stairs` | LichAmnesia/awesome-ad-video-prompts | prompts.json › ugc-authentic › sneaker-unboxing-on-stairs | CC-BY-4.0 | Chinese translation added |
| `lich-glass-serum-unbox` | LichAmnesia/awesome-ad-video-prompts | prompts.json › unboxing-asmr › glass-serum-unbox | CC-BY-4.0 | Chinese translation added |
| `lich-watch-drawer-slide` | LichAmnesia/awesome-ad-video-prompts | prompts.json › unboxing-asmr › watch-drawer-slide | CC-BY-4.0 | Chinese translation added |
