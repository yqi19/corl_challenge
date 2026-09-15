# Exposing your policy server for free (Cloudflare Quick Tunnel)

[English](#english) · [中文](#中文)

## English

The evaluator must reach your policy server over the Internet. You do **not** need a
public IP, a domain, a Cloudflare account, or any payment: a Cloudflare **Quick Tunnel**
(TryCloudflare) gives your local port a temporary public HTTPS/WebSocket address.

Official links:

| What | Link |
|---|---|
| Quick Tunnel documentation | <https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/> |
| `cloudflared` downloads (all platforms) | <https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/> |
| `cloudflared` releases on GitHub | <https://github.com/cloudflare/cloudflared/releases> |

### 1. Install `cloudflared`

```bash
# Linux x86_64 (most GPU servers); use cloudflared-linux-arm64 on ARM
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared

# macOS
brew install cloudflared

# Windows (PowerShell)
winget install --id Cloudflare.cloudflared
```

### 2. Start your policy server, then the tunnel

```bash
# terminal 1
export TOWER_API_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')
python policy_server/serve_policy.py --port 8000 --checkpoint /path/to/ckpt

# terminal 2 (on macOS/Windows run `cloudflared` instead of `./cloudflared`)
./cloudflared tunnel --url http://localhost:8000
```

`cloudflared` prints a line like:

```text
https://random-words-here.trycloudflare.com
```

Your submission endpoint is the same host with `wss://`:

```text
wss://random-words-here.trycloudflare.com
```

### 3. Check it from outside and submit

```bash
python tools/check_policy.py wss://random-words-here.trycloudflare.com \
    --api-key-env TOWER_API_KEY --output check_report.json
```

Put the `wss://` address in `submission.json` and follow
[Submit your run](../README.md#submit-your-run).

### Things to know

- **Free, no account.** Cloudflare states Quick Tunnels are meant for testing and
  development, with no uptime guarantee.
- **The address changes on every restart.** Keep both terminals running for your whole
  availability window (use `tmux` or `screen` on remote servers). If the address changes,
  email us the new one.
- **Limits.** At most 200 concurrent in-flight requests (the evaluator uses far fewer);
  Server-Sent Events are unsupported, WebSocket works.
- **Keep the API key on.** The tunnel address is public; the key is what keeps others out.
- **Alternative:** [ngrok](https://ngrok.com/download) also has a free plan, but it needs
  an account and has usage limits.

## 中文

评测服务器需要通过公网访问你的策略服务。你**不需要**公网 IP、域名、Cloudflare 账号，也**不用付费**：
Cloudflare **Quick Tunnel**（TryCloudflare）会给本机端口分配一个临时的公网 HTTPS/WebSocket 地址。

官方链接：

| 内容 | 链接 |
|---|---|
| Quick Tunnel 官方文档 | <https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/> |
| `cloudflared` 下载页（全平台） | <https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/> |
| `cloudflared` GitHub 发布页 | <https://github.com/cloudflare/cloudflared/releases> |

### 1. 安装 `cloudflared`

```bash
# Linux x86_64（大多数 GPU 服务器）；ARM 机器换成 cloudflared-linux-arm64
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared

# macOS
brew install cloudflared

# Windows（PowerShell）
winget install --id Cloudflare.cloudflared
```

### 2. 先启动策略服务，再开隧道

```bash
# 终端 1
export TOWER_API_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')
python policy_server/serve_policy.py --port 8000 --checkpoint /path/to/ckpt

# 终端 2（macOS/Windows 上直接运行 `cloudflared`，不带 `./`）
./cloudflared tunnel --url http://localhost:8000
```

`cloudflared` 会输出类似下面的地址：

```text
https://random-words-here.trycloudflare.com
```

提交时把 `https://` 换成 `wss://`：

```text
wss://random-words-here.trycloudflare.com
```

### 3. 从外网自检并提交

```bash
python tools/check_policy.py wss://random-words-here.trycloudflare.com \
    --api-key-env TOWER_API_KEY --output check_report.json
```

把 `wss://` 地址填进 `submission.json`，然后按 [提交内容](../README_zh.md#提交内容submit-your-run) 发送邮件。

### 注意事项

- **免费、无需注册。** Cloudflare 官方说明 Quick Tunnel 用于测试和开发，不保证稳定在线。
- **每次重启地址都会变。** 在你填写的可用时间窗口内，两个终端都不能关（远程服务器上建议用 `tmux` 或 `screen`）。
  地址变化后请邮件告知新地址。
- **限制。** 同时最多 200 个进行中的请求（评测远用不到）；不支持 Server-Sent Events，WebSocket 可以正常使用。
- **务必开启 API key。** 隧道地址是公开的，只有 key 能挡住其他人。
- **备选：** [ngrok](https://ngrok.com/download) 也有免费版，但需要注册账号，且有用量限制。
