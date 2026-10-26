# 常见运维故障处理 SOP 手册

> 本文档为 OpsRAG Copilot 知识库演示样例，覆盖企业内网常见故障场景。
> 实际使用请替换为真实运维手册与 SOP。

## Nginx 502 Bad Gateway 排查

### 现象
访问业务页面返回 502 Bad Gateway，Nginx 错误日志出现 `upstream prematurely closed connection` 或 `connect() failed (111: Connection refused)`。

### 可能原因
1. 后端应用进程未启动或已崩溃
2. 后端监听端口错误或绑定在 localhost 无法对外
3. 上游超时时间配置过短
4. 后端连接数打满，拒绝新连接

### 排查步骤
1. 确认后端进程存活：`ps -ef | grep java`（或对应进程名）
2. 验证后端端口连通：`curl -v http://127.0.0.1:8080/healthz`
3. 查看 Nginx 错误日志：`tail -100f /var/log/nginx/error.log`
4. 检查 upstream 配置是否指向正确地址与端口
5. 检查后端 JVM 线程数、连接数是否达到上限

### 处理命令
```bash
# 重启后端应用
systemctl restart app-server
# 或 docker 方式
docker compose restart backend

# 查看连接数
ss -ant | grep :8080 | wc -l
```

### 预防措施
- 为 upstream 配置健康检查与备用节点
- 适当调大 proxy_read_timeout（建议 180s）
- 后端进程由 systemd/docker 守护，异常自动拉起

## Oracle 表空间满应急处理

### 现象
应用报错 `ORA-01653: unable to extend table`，DBA 巡检发现表空间使用率超过 95%。

### 可能原因
1. 数据增长过快，未设置自动扩展
2. 归档日志或临时表空间异常增长
3. 历史分区未及时归档清理

### 应急步骤
1. 查看表空间使用率：
```sql
SELECT tablespace_name, ROUND(SUM(bytes)/1024/1024/1024,2) AS size_gb
FROM dba_data_files GROUP BY tablespace_name;
```
2. 为数据文件增加自动扩展：
```sql
ALTER DATABASE DATAFILE '/u01/app/oracle/oradata/data01.dbf'
AUTOEXTEND ON NEXT 1G MAXSIZE 32G;
```
3. 若磁盘空间不足，先清理临时段与回收站：
```sql
PURGE DBA_RECYCLEBIN;
```
4. 通知业务方核查异常写入任务

### 预防措施
- 建立表空间使用率监控告警（阈值 80%/90%）
- 制定历史数据归档与分区清理计划
- 磁盘扩容前评估增长率

## Kubernetes Pod CrashLoopBackOff 排查

### 现象
Pod 反复重启，状态为 CrashLoopBackOff，`kubectl get pods` 中 RESTARTS 持续增长。

### 可能原因
1. 应用启动即崩溃（配置错误、依赖服务未就绪）
2. 健康检查失败导致被反复杀掉
3. 资源限制（CPU/内存）不足触发 OOMKilled
4. 镜像入口命令或环境变量配置错误

### 排查步骤
1. 查看崩溃日志：`kubectl logs <pod> --previous`
2. 查看事件：`kubectl describe pod <pod>`
3. 确认是否为 OOM：检查 Last State 是否为 OOMKilled
4. 检查依赖服务（数据库、注册中心）是否就绪
5. 验证 ConfigMap/Secret 是否挂载正确

### 处理命令
```bash
kubectl logs <pod> --previous --tail=200
kubectl describe pod <pod> | grep -A5 "Events"
kubectl get events --sort-by=.lastTimestamp | tail -20
```

### 预防措施
- 为容器设置合理的 requests/limits 与启动探针
- 依赖服务先行部署，应用侧增加重试机制
- 规范镜像启动脚本，避免前台进程提前退出

## Java 应用 OOM 处理

### 现象
应用日志出现 `java.lang.OutOfMemoryError: Java heap space`，服务响应缓慢或不可用。

### 可能原因
1. 堆内存配置过小（-Xmx）
2. 内存泄漏（集合类未清理、连接未释放）
3. 单次请求数据量过大（大文件导入、批量查询）

### 应急处理
1. 重启应用恢复服务（临时手段）
2. 保留现场：`jmap -dump:format=b,file=heap.hprof <pid>`
3. 增大堆内存：修改 `-Xmx` 后重启验证
4. 使用 MAT 分析堆转储文件，定位大对象与泄漏点

### 预防措施
- 监控堆内存使用率与 GC 频率
- 压测确定合理堆内存与并发参数
- 代码评审关注集合与流式资源释放

## Fastjson 漏洞修复

### 现象
安全扫描报告 Fastjson 存在反序列化远程代码执行漏洞（如 CVE-2022-25845），需尽快修复。

### 修复步骤
1. 定位引入位置：`mvn dependency:tree | grep fastjson`
2. 升级到安全版本（≥ 1.2.83 或 2.0.x）：
```xml
<dependency>
    <groupId>com.alibaba</groupId>
    <artifactId>fastjson</artifactId>
    <version>1.2.83</version>
</dependency>
```
3. 升级后重启应用并执行安全回归
4. 若无法升级，启用 safeMode 并关闭 autoType

### 预防措施
- 建立依赖漏洞扫描（Sonatype/OWASP）纳入 CI
- 新项目优先使用 Jackson 等维护活跃的序列化框架
- 安全公告跟进与补丁时效管理
