# TOWER Challenge @ CoRL 2026 Workshop

[English](README.md)

仿真中的长程双臂积木塔操作。参赛者用 **TOWER-SimData** 训练策略，把策略部署成一个
WebSocket 服务；组委会在 TOWER Isaac Sim 评测平台上调用你的服务完成评测。
**参赛者不需要安装 Isaac Sim 或评测代码。**

> 状态：草稿。标注 **TBD** 的内容将在本仓库和 Workshop 微信群公布。

## 资源

| 资源 | 链接 |
|---|---|
| 训练数据（331 条，225 GiB，HDF5） | [tower-benchmark/TOWER-SimData](https://huggingface.co/datasets/tower-benchmark/TOWER-SimData) |
| 仿真资产 | [tower-benchmark/TOWER-Assets](https://huggingface.co/datasets/tower-benchmark/TOWER-Assets) |
| 评测平台 | [tower-benchmark/TOWER](https://github.com/tower-benchmark/TOWER) |
| 策略服务协议 | [docs/protocol.md](docs/protocol.md) |
| 排行榜 | **TBD** |

## 任务

六个任务：Tower Transfer（2/3 层）、Cross Tower Transfer（2/3 层）、Vertical Stacking（2/3 层），
文件夹命名见 [README.md](README.md#tasks)。两台 AgileX Nero 7 自由度机械臂（`left`、`back`），
四路 RGB 相机，18 维绝对动作。SimData 没有官方划分，全部可用于训练。

## 参赛流程

1. **报名**：**TBD**（表单链接）。
2. **训练**：基于 TOWER-SimData 训练策略，架构不限；使用额外数据须申报。
3. **起服务**：使用 [`policy_server/serve_policy.py`](policy_server/serve_policy.py)，
   或沿用你现有的 openpi 服务，只需实现 `Policy.infer`：

   ```bash
   pip install -r requirements.txt
   export TOWER_API_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')
   python policy_server/serve_policy.py --port 8000 --checkpoint /path/to/ckpt
   ```

4. **暴露端口**：公网 IP、带 TLS 的反向代理（`wss://`），或 frp / cloudflared / ngrok 等隧道。
5. **自检**：在外网机器上运行，与评测端调用方式完全一致：

   ```bash
   python tools/check_policy.py wss://your-host:8000 --api-key-env TOWER_API_KEY \
       --output check_report.json
   ```

6. **提交**（见下），并在填写的可用时间窗口内保持服务在线。

## 提交内容（Submit your run）

发送邮件至 **TBD**，标题 `[TOWER Challenge] <队名> <模型版本>`：

| 内容 | 必需 | 说明 |
|---|---|---|
| `submission.json` | 是 | 按 [`submission/submission_template.json`](submission/submission_template.json) 填写：队伍、联系人、模型、服务地址、可用时间窗口 |
| `check_report.json` | 是 | 提交前 24 小时内对该地址运行 `tools/check_policy.py` 的输出 |
| API key | 是 | 只写在邮件正文里，使用专用 key |
| 方法说明 | 决赛 | 1–2 页 PDF：模型结构、训练数据、训练算力 |

提交后：组委会先复跑自检（失败不计次数）→ 在你的时间窗口内跑完全部任务（初始布局和种子固定且不公开）→
核验后更新排行榜。

规则：每轮每队最多评测 **TBD** 次，取最好成绩；评测期间不得更换模型；策略只能使用提供的观测，
禁止人工干预、读取仿真器内部状态或针对测试布局硬编码；前列队伍需提供推理代码或 Docker 镜像供复核。

## 评测指标

| 层级 | 指标 | 定义 |
|---|---|---|
| 任务级 | 任务成功率 ↑ | 完整成功 episode 数 ÷ 有效 episode 数 |
| 操作级 | 抓取成功率 ↑ | 成功抓取的目标块 ÷ 全部预定目标块 |
| 操作级 | 放置成功率 ↑ | 稳定放置的目标块 ÷ 全部预定目标块 |
| 长程级 | 长程进度率 ↑ | 按顺序连续完成的任务点 ÷ 全部任务点 |
| 安全级 | 扰动物块数 DBC ↓ | 每个 episode 被扰动的非目标块数（同一块只计一次） |

排名（草案）：六个任务的平均任务成功率；并列时依次比较平均长程进度率、更低的 DBC、更早的提交时间。
推理期间仿真暂停，网络延迟不影响分数，但单次请求超过 60 秒未回复记为失败。

## 联系方式

- 邮箱：**TBD**
- 微信群：**TBD**（二维码）
- 问题反馈：在本仓库提 issue
