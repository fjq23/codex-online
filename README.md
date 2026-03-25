# Codex Mobile Workbench

一个面向手机浏览器使用的轻量 Codex 自托管工作台。

核心仍然只有四层：

- `ttyd` 提供网页终端
- `File Browser` 提供网页文件管理
- `Codex CLI` 作为实际执行主体
- `Caddy` 提供统一入口和基础认证

它不是网页版 IDE，不自研终端、不自研文件上传、不做聊天系统，也不引入数据库业务层。

## 当前交互模型

这版不再把“全局 workspace”暴露给用户，而是改成“每个用户任务一个独立 workspace”。

- `/` 首页就是极简工作区页面
- 页面上同时提供已有 workspace 列表、新建入口和文件入口
- 选中后浏览器会跳到 `/terminal/session/`，再 attach 到对应的 `tmux` session
- 直接回车：进入最近使用的 workspace
- 输入已有 workspace 名：打开原 workspace
- 输入新名字：自动创建新 workspace
- 每个 workspace 对应一个独立 `tmux` session
- `/files` 只显示 `workspaces/`，不再暴露系统脚本和状态目录

这更接近手机使用习惯，因为用户只需要关心“我要进入哪个工作区”，而不是去理解脚本放在哪。

## 目录结构

```text
/workspace
  /workspaces
    /demo
  /.state
```

- `workspaces/<name>`：默认是空目录，不预置模板
- `workspaces/<name>/logs`：首次执行 `run` 时自动创建
- `workspaces/<name>/archive`：首次执行 `pack` 时自动创建
- `.state`：最近使用的 workspace 等内部状态，不对文件页暴露

## 运行要求

- 一台 Linux 服务器
- Docker Engine
- Docker Compose (`docker-compose` 或新版 `docker compose`)
- 手机浏览器可访问这台服务器

## 快速部署

### 1. 准备环境变量

优先用初始化脚本：

```bash
./scripts/init-env.sh --site codex.example.com --password '替换成强密码'
```

它会自动：

- 复制 `.env.example` 到 `.env`（如果 `.env` 还不存在）
- 生成 Caddy 的 bcrypt 哈希
- 自动把哈希里的 `$` 转义成 `$$`
- 写入 `BASIC_AUTH_USER`、`BASIC_AUTH_HASH`、`CADDY_SITE_ADDR`、端口、UID/GID、时区

如果你是内网/IP 访问，也可以这样：

```bash
./scripts/init-env.sh --site :80 --http-port 8080 --https-port 8443 --password '替换成强密码'
```

如果你仍想手工处理，也可以继续用：

```bash
cp .env.example .env
./scripts/hash-password.sh '替换成强密码'
```

内网/IP 直连可保留：

```dotenv
CADDY_SITE_ADDR=:80
HTTP_PORT=8080
```

公网 HTTPS 可以改成：

```dotenv
CADDY_SITE_ADDR=codex.example.com
HTTP_PORT=80
HTTPS_PORT=443
```

### 2. 启动服务

```bash
docker-compose build ttyd
docker-compose up -d
```

如果要启用 `Mihomo/Clash` 侧车代理，先准备配置：

```bash
mkdir -p proxy/mihomo
cp proxy/mihomo/config.yaml.example proxy/mihomo/config.yaml
```

如果你不想依赖 Docker Hub 里的 `mihomo` 镜像，可以直接把官方 release 二进制放进项目里。本仓库当前默认路径是：

- `proxy/mihomo/bin/mihomo`

当前示例下载的是 `linux amd64 compatible` 版本，来源是 Mihomo 官方 release：
https://github.com/MetaCubeX/mihomo/releases

也可以直接用脚本按当前机器架构下载：

```bash
./scripts/download-mihomo.sh
```

把 `proxy/mihomo/config.yaml` 替换成你自己的可用配置后，再用代理模式启动：

```bash
docker-compose -f docker-compose.yml -f docker-compose.proxy.yml up -d
```

如果宿主机上的 `7890/7891/9090` 已被其他代理占用，可以在 `.env` 中改成别的宿主机端口，例如：

```dotenv
MIHOMO_HTTP_PORT=17890
MIHOMO_SOCKS_PORT=17891
MIHOMO_API_PORT=19090
```

这只影响宿主机映射端口，不影响容器内 `ttyd -> mihomo` 的通信。

### 3. 打开工作台

- `http://SERVER_IP:8080/`
- 或 `https://codex.example.com/`

先通过 Caddy 的 Basic Auth，再进入首页。

## Codex 登录

### 方式 A：终端里登录 ChatGPT 账号

进入 `/terminal/session/` 后执行：

```bash
codex login --device-auth
```

### 方式 B：使用 API Key

把 `.env` 中的 `OPENAI_API_KEY` 填好，然后重启：

```bash
docker-compose up -d ttyd
```

## 手机端最常用命令

这一版把命令尽量压短了，避免在手机上敲长路径。

- `w`
  - 打开工作区选择器
- `w open demo`
  - 打开 `demo` 工作区，不存在就创建
- `run`
  - 在当前工作区内运行 Codex，并交互输入 prompt
- `run "处理 inbox 里的文件，把结果放到 output/"`
  - 直接带 prompt 运行
- `pack`
  - `output/` 有内容时优先打包 `output/`，否则打包整个 workspace 到 `archive/`
- `recent`
  - 回到最近使用的工作区
- `resume_last`
  - 运行 `codex resume --last`
- `netcheck`
  - 在终端里检查代理环境、Mihomo 控制面和 OpenAI 连通性

## 工作流

### 场景 A：上传素材并运行 Codex

1. 打开 `/files`
2. 进入某个 workspace；没有的话先新建一个文件夹，例如 `demo`
3. 上传文件到 `demo/`，或你自己创建的子目录里
4. 打开 `/`
5. 在页面里点选 `demo`，或输入新名字创建
6. 页面会自动跳到 `/terminal/session/`
7. 在终端中执行：

```bash
run
```

然后按提示输入 prompt，或者直接执行：

```bash
run "处理当前 workspace 里的文件，并把成品放到你创建的目录里"
```

8. 完成后回 `/files` 下载结果
9. 如需 zip：

```bash
pack
```

然后去 `demo/archive/` 下载压缩包。

### 场景 B：只看进度

1. 手机打开 `/`
2. 点选最近 workspace
3. 自动跳到 `/terminal/session/` 并 attach 到该 workspace 对应的 `tmux` session
4. 断线后再次打开 `/`，再点选即可恢复

## 终端行为

- 每个 workspace 一个独立 `tmux` session
- `w open <name>` 会 attach 到对应 session
- `run` 会在该 workspace 的 tmux session 中创建新窗口运行 `codex exec`
- 日志保存在 `workspaces/<name>/logs/`

注意：`run` 默认使用 `--dangerously-bypass-approvals-and-sandbox`，前提是你把容器当作执行边界，不要开放给不可信用户。

## 初始化验证

### 验证路由

打开并确认以下页面可访问：

- `/`
- `/`
- `/terminal/session/`
- `/files/`

### 验证工作区互通

1. 在 `/files` 中新建 `demo/`
2. 上传一个测试文件到 `demo/`
3. 在 `/` 页面点选 `demo`
4. 页面跳到 `/terminal/session/`
5. 执行：

```bash
pwd
ls -lah
```

如果能看到刚上传的文件，说明文件页和终端共享同一个 workspace。

## 网络排查

在工作区终端里：

```bash
netcheck
```

在 WSL / 宿主机里：

```bash
sudo ./scripts/debug-network.sh
```

这个脚本会检查：

- 宿主机代理环境变量
- Mihomo 监听端口
- `mihomo` / `ttyd` 日志
- 宿主机通过 Mihomo 访问 OpenAI
- `ttyd` 容器里的代理环境变量
- `ttyd` 容器里访问 `mihomo:9090`
- `ttyd` 容器里访问 `https://api.openai.com`

## 代理说明

这个项目现在支持一个可选的 `Mihomo/Clash` 侧车代理：

- 目的：给 `ttyd` 容器里的 `codex`、`curl`、`npm`、`pip` 等命令提供稳定的运行时代理
- 启动文件：[docker-compose.proxy.yml](/home/jiaqi/codex-online/docker-compose.proxy.yml)
- 配置模板：[proxy/mihomo/config.yaml.example](/home/jiaqi/codex-online/proxy/mihomo/config.yaml.example)

几个边界要说清楚：

- 这个代理覆盖的是 `ttyd` 容器里的运行时网络请求
- 它不负责宿主机上的 Docker daemon 拉镜像
- 也就是说，`docker pull` / `docker-compose build` 如果要走代理，仍然需要你给宿主机 Docker daemon 单独配代理
- 如果 `ttyd` 容器里访问 `mihomo:7890` 失败，而 `http://mihomo:9090/version` 能通，通常是 Mihomo 只监听了 `127.0.0.1`。当前示例配置已使用 `allow-lan: true` 和 `bind-address: 0.0.0.0`，用于容器间访问。

### 验证 tmux 恢复

1. 打开 `/terminal/`
2. 点选最近工作区
3. 执行：

```bash
watch -n 2 date
```

4. 关闭浏览器标签页
5. 再次打开 `/terminal/`
6. 再次点选最近工作区

如果还能看到原窗口，说明 tmux 恢复正常。

## 权限与持久化

持久化目录：

- `./workspace`
- `./data/codex-home`
- `./data/filebrowser`
- `./data/caddy`
- `./data/caddy_config`

默认通过 `.env` 里的 `APP_UID` / `APP_GID` 让上传文件和 Codex 生成文件保持一致所有权。

## 安全注意事项

已做的基础防护：

- 只暴露 `Caddy` 到外部
- 整个站点统一 Basic Auth
- `File Browser` 关闭命令执行功能
- 文件页只暴露 `workspaces/`
- `Codex` 状态单独持久化在 `data/codex-home`

上线公网前建议你自己补强：

- 使用正式域名和 HTTPS
- 使用强密码，不要复用密码
- 尽量加 IP 白名单、VPN、Cloudflare Tunnel 或 Zero Trust
- 定期更新镜像与 `@openai/codex`
- 保护好 `data/codex-home/auth.json`
- 不要把这个工作台开放给不可信用户

## 常见维护命令

```bash
docker-compose logs -f caddy
docker-compose logs -f ttyd
docker-compose logs -f filebrowser
docker-compose build --no-cache ttyd
docker-compose up -d
```

## 参考

- Codex docs: <https://developers.openai.com/codex/>
- Codex auth: <https://developers.openai.com/codex/auth>
- File Browser docs: <https://filebrowser.org/cli/filebrowser.html>
