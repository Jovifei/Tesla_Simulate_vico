# S12 评审页面刷新阻塞：大 HTML 与单线程服务

状态：`RESOLVED / REUSABLE_DEBUGGING_KNOWLEDGE`

## 症状

打开一个新的 Hellcat A/B 页面或刷新 `http://localhost:8188/` 超时/拒绝连接；服务进程和监听端口看起来仍存在，而其他候选端口可能正常。页面是原工作台生成的自包含 HTML，单页约 34.5 MB，包含内嵌 WAV/Base64 数据。

## 根因定位

不要先改 HTML 或端口。按以下顺序收集证据：

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8188
Get-NetTCPConnection -LocalPort 8188
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
  Where-Object { $_.CommandLine -like '*serve_dashboards.py*' } |
  Select-Object ProcessId,CommandLine
curl.exe --max-time 10 -sS -D - http://127.0.0.1:8188/ -o NUL
```

若端口进程属于预期 `serve_dashboards.py`，但有多条 `ESTABLISHED` 连接且新请求失败，回溯服务实现：`ReusableTCPServer` 如果只是 `socketserver.TCPServer`，它每次只处理一个客户端。一个浏览器/下载器慢慢读取几十 MB HTML 时，handler 会阻塞在 socket 写入，主 server 就不能及时接受刷新连接。

## 修复原则

保留页面、根目录和端口映射，只把 server class 改为：

```python
class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = True
```

`ThreadingMixIn` 让每个客户端由独立线程处理；daemon/thread-close 选项避免慢客户端阻止服务退出。它不改变 HTML 内容，也不改变声音 renderer。

## 最小回归与现场验证

先写失败测试，确认旧实现不是并发 server：

```python
assert issubclass(ReusableTCPServer, socketserver.ThreadingMixIn)
assert ReusableTCPServer.daemon_threads is True
```

修复后再做真实并发检查：用 socket 连接 8188，发送 GET 但不读取响应；等待 0.5 秒后发第二个 HTTP 请求。第二请求必须在 10 秒内返回 200。最后检查 8188/8488/8388 都返回 200。

## 不要重复的错误处理

- 不要因为刷新失败就删除或重生成原始试听包；
- 不要把 `localhost` 解析差异当作根因，先用 `127.0.0.1` 和 TCP 连接状态确认；
- 不要终止无关端口或用户服务；
- 不要用缓存头、换 URL 或复制 HTML 掩盖单线程阻塞；
- 不要把页面能打开写成声音 Human PASS。
