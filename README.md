# GetInfoScan —— 魔兽世界 ID 区段批量扫描器

填入**起始 ID** 和**结束 ID**，一次扫描范围内的**物品 / 任务 / 法术 / 成就**，把存在的条目连同 ID、名称和可点击连结收集起来，支持复制与导出。

数据全部来自客户端自身 API，**不依赖任何第三方数据库**，所以扫出来的就是你这个服真正有的 ID。

- 作者：**Loukky**　授权：MIT
- 主要目标客户端：Titan Reforged（`GetBuildInfo` 报 `3.80.2`，Interface `38002`）
- 界面语言：简体中文 / 繁體中文 / English

---

## 安装

把 `GetInfoScan` 整个文件夹放进：

```
...\World of Warcraft\_classic_titan_\Interface\AddOns\GetInfoScan
```

最终路径应该是 `Interface\AddOns\GetInfoScan\GetInfoScan.toc`，**不要多套一层文件夹**（这是安装失败最常见的原因）。重启客户端即可，插件自带 AceGUI，不需要另装任何库。

## 使用

1. 点小地图按钮，或输入 `/gis` 打开窗口
2. 填入「起始 ID / 结束 ID」（默认 `1` ~ `5000`），选类型页签，点「开始扫描」（参数框里按回车也可以）
3. 扫的过程中结果实时出现，可随时「暂停 / 继续 / 停止」
4. 扫完：
   - 鼠标悬停某一行 → 看该条目的游戏内提示
   - 点某一行 → 把连结放进聊天输入框
   - 「复制所有结果」 → 全部 `ID + 连结` 放进下方文本框并全选，Ctrl+C 即可
   - 「导出」 → 存进存档，`/reload` 后落盘成文件

窗口从左下角可以看到**客户端自己报的**版本信息（版本、build、Interface 号、内容线、语言）。

## 斜杠命令

命令：`/gis`、`/getinfoscan`、`/infoscan`

| 命令 | 作用 |
| --- | --- |
| `/gis` | 打开 / 关闭窗口 |
| `/gis status` | 打印客户端版本信息、各类型 API 可用性、窗口状态，排查问题先看它 |
| `/gis build` | 重建窗口（窗口显示不全时用） |
| `/gis clear` | 清空结果列表 |
| `/gis copy` | 复制所有结果 |
| `/gis export` | 导出当前结果 |
| `/gis minimap` | 显示 / 隐藏小地图按钮 |
| `/gis reset` | 清空已保存的导出内容 |

## 导出格式与文件位置

```
-- GetInfoScan 导出  2026-01-01 12:00:00
-- type=quest  range=1-5000  found=812
1	|cffffff00|Hquest:1|h[任务名]|h|r
2	|cffffff00|Hquest:2|h[沙普塔隆的爪子]|h|r
```

前两行是注释（时间、类型、区段、命中数），之后每行一条：**数字 ID + 一个 Tab + 完整连结**。名称就在连结的方括号里，所以没有单独的列。

导出写在存档变量里，客户端只在**重载界面时**落盘：

```
...\WTF\Account\<你的账号>\SavedVariables\GetInfoScan.lua
```

## 注意事项

- **导出后必须 `/reload`（或退出游戏）**，文件才会更新；每种类型只保留**最后一次**导出，互不覆盖。
- **物品扫描比较慢**：客户端本地没有资料的 ID 要一个个向服务端问，插件把请求限速在 40 个/秒以免刷爆连接。把「速度」调大（如 `0.15`）或缩小区段可以更快。
- 任务 / 法术 / 成就是纯本地查询，很快。
- 显示**「无资料」不代表这个 ID 不存在**，只表示客户端现在拿不到它的资料；插件如实分成「找到」和「无资料」，不做猜测。
- **任务只导出 ID 与名称，没有描述和任务需求**。这个客户端没有"按 ID 取任务文本"的接口，唯一能给出任务短句的调用只描述**当前选中的任务日志条目**，用在整个区段上会把一个任务的文字安到别的任务头上，所以没有做。
- 只能扫**连续的整数区段**；单次区段上限 10 万个 ID，结果上限 5000 条（超出会明确提示）。
- 「复制」走的是游戏文本框，**有长度上限**：超长时插件会告诉你只接受了多少字符，完整内容请用导出。
- 扫描范围太大时建议分几次扫，一次扫太多「无资料」的 ID 会长时间占用请求配额。

### 关于多份 TOC

插件带了 7 份 TOC，客户端会按自己的游戏类型挑一份用（`_Wrath` / `_Vanilla` / `_TBC` / `_Cata` / `_Mists` / `_Forever`，都不匹配时用不带后缀的 `GetInfoScan.toc`）。各份除了 Interface 号之外内容完全一致。

- `_Wrath` 写的是 Titan Reforged 的 `38002`；官方 WotLK Classic（`30405`）共用同一个游戏类型，会显示「过期」但照常能用。
- 如果你要自己加 Lua 文件，**记得同步加进全部 7 份 TOC**，漏掉哪一份那部分玩家就会加载到不完整的插件。

## 发布（维护者）

打版本标签即自动发到 CurseForge：

```bash
git tag v1.5.0 && git push origin v1.5.0
```

- 触发：推送 `v*` 标签，或在 GitHub 上发布 Release。**普通 push 到主分支不会上传**。
- 项目 ID `1734764`，令牌来自仓库 secret **`CURSEFORGE_TOKEN`**（Settings → Secrets and variables → Actions）。
- 版本号取自标签（`v1.5.0` → `1.5.0`），没有标签时回落到 TOC 里的 `## Version`。
- 标签含 `alpha` / `beta` 时对应 alpha / beta 发布，否则为正式版。
- 游戏版本按 7 份 TOC 的 Interface 号自动映射，无需手工维护。
- 想只验证打包不上传：手动运行 Release workflow，`dry_run` 保持勾选即可，zip 会作为 artifact 留下。

## 授权

**MIT License**，版权归 **Loukky**，完整文本见 [LICENSE](LICENSE)。

`Libs/` 里是上游库的原样副本（LibStub 为公有领域；CallbackHandler-1.0、AceGUI-3.0 来自 [Ace3](https://github.com/WoWUIDev/Ace3)），遵循各自上游的许可。

## English

### GetInfoScan — batch ID range scanner for World of Warcraft

Enter a **start ID** and an **end ID** to scan a whole range of **items / quests / spells / achievements**, and collect everything that exists along with its ID, name and a clickable link. Results can be copied or exported.

All data comes from the client's own APIs — **no third-party databases, no network** — so what you get is exactly what your server really has.

- Author: **Loukky** · License: MIT
- Target client: Titan Reforged (`GetBuildInfo` reports `3.80.2`, Interface `38002`)
- UI languages: 简体中文 / 繁體中文 / English

### Install

Drop the whole `GetInfoScan` folder into:

```
...\World of Warcraft\_classic_titan_\Interface\AddOns\GetInfoScan
```

The final path must be `Interface\AddOns\GetInfoScan\GetInfoScan.toc` — **do not nest another folder level** (that is the most common installation mistake). Restart the client. AceGUI is bundled, so no other library is needed.

### Usage

1. Click the minimap button or type `/gis` to open the window
2. Fill in *Start ID* / *End ID* (default `1` – `5000`), pick a type tab, press *Start Scan* (Enter in a parameter box works too)
3. Results appear live while scanning; you can *Pause* / *Continue* / *Stop* at any time
4. When it finishes:
   - Hover a row → its in-game tooltip
   - Click a row → the link goes into the chat edit box
   - *Copy All Results* → every `ID + link` goes into the box below, fully selected; just press Ctrl+C
   - *Export* → written to SavedVariables; `/reload` writes it to disk

The bottom-left of the window shows what the **client itself reports**: version, build, Interface number, content line and language.

### Slash commands

Commands: `/gis`, `/getinfoscan`, `/infoscan`

| Command | Effect |
| --- | --- |
| `/gis` | Open / close the window |
| `/gis status` | Print client version info, per-type API availability and window state — the first thing to check when something is wrong |
| `/gis build` | Rebuild the window (use when it renders incomplete) |
| `/gis clear` | Clear the result list |
| `/gis copy` | Copy all results |
| `/gis export` | Export the current results |
| `/gis minimap` | Show / hide the minimap button |
| `/gis reset` | Clear the saved export |

### Export format and location

```
-- GetInfoScan export  2026-01-01 12:00:00
-- type=quest  range=1-5000  found=812
1	|cffffff00|Hquest:1|h[Quest Name]|h|r
2	|cffffff00|Hquest:2|h[Shaputalon's Claw]|h|r
```

The first two lines are comments (time, type, range, hit count); every line after that is one hit: **numeric ID, a Tab, then the full hyperlink**. The name is inside the link's brackets, so there is no separate name column.

The export is stored in SavedVariables, and the client only writes it to disk when the UI reloads:

```
...\WTF\Account\<your account>\SavedVariables\GetInfoScan.lua
```

### Notes

- **You must `/reload` (or log out) after exporting** for the file to be updated. Each type keeps only its **most recent** export; the types do not overwrite each other.
- **Item scans are slow**: IDs the client has no local data for have to be requested from the server one by one, and the addon rate-limits those requests to 40 per second so the connection is not flooded. Raise *Speed* (e.g. `0.15`) or shrink the range to go faster.
- Quests / spells / achievements are purely local lookups and are fast.
- **"No data" does not mean the ID does not exist.** It only means the client cannot get its data right now. The addon counts *found* and *no data* separately instead of guessing.
- **Quests export only the ID and the name — no description and no objectives.** This client has no per-ID quest text getter, and the only call that returns a quest's short objective sentence describes whichever quest log entry is currently *selected*; using it across an ID range would attribute one quest's text to another, so it was left out.
- Only **contiguous integer ranges**; one scan covers at most 100,000 IDs and returns at most 5000 results (exceeding that is reported explicitly).
- *Copy* goes through a game text box, which **has a length limit**: when the text is too long the addon tells you how many characters were accepted and points you to Export.
- Very large scans are better split into several runs — a range full of "no data" IDs ties up the request budget for a long time.

#### About the multiple TOCs

The addon ships 7 TOC files and the client picks one according to its game type (`_Wrath` / `_Vanilla` / `_TBC` / `_Cata` / `_Mists` / `_Forever`, and `GetInfoScan.toc` without a suffix when none of them match). Apart from the Interface number they are identical.

- `_Wrath` carries `38002` (Titan Reforged). Retail WotLK Classic (`30405`) shares the same game type, so it will show as "out of date" but still works.
- If you add a Lua file of your own, **add it to all 7 TOCs** — miss one and players on that client get an incomplete addon.

### Releasing (maintainer)

Tagging a version publishes to CurseForge automatically:

```bash
git tag v1.5.0 && git push origin v1.5.0
```

- Triggers on a pushed `v*` tag or a published GitHub Release. **A normal push to main never uploads.**
- Project ID `1734764`; the token comes from the repository secret **`CURSEFORGE_TOKEN`** (Settings → Secrets and variables → Actions).
- The version comes from the tag (`v1.5.0` → `1.5.0`), falling back to `## Version` in the TOC.
- A tag containing `alpha` / `beta` publishes as alpha / beta, anything else as a release.
- Game versions are mapped from the `## Interface` value in all 7 TOCs, so there is nothing to maintain by hand.
- To check packaging without publishing, run the Release workflow manually and leave `dry_run` ticked — the zip is kept as an artifact.

### License

**MIT License**, copyright **Loukky** — see [LICENSE](LICENSE) for the full text.

`Libs/` contains unmodified copies of upstream libraries (LibStub is public domain; CallbackHandler-1.0 and AceGUI-3.0 come from [Ace3](https://github.com/WoWUIDev/Ace3)) and follows their own upstream licenses.
