# Agent 沙箱机制：分层实现与自研/开源选型

> 说明：本文为工程备忘，供 agent-service 生产化演进参考。核心结论——
> **隔离原语（运行时/浏览器底层）以第三方开源为主（约 80%），工具治理与编排策略以自主开发为主（约 70%）**；
> 不存在通用的"Agent 沙箱全家桶"，云厂商（OpenAI Code Interpreter 等）方案封闭且与平台绑定。

## 一、四层沙箱全景

| 层 | 要隔离什么 | 典型实现（开源） | 自研/开源倾向 |
| --- | --- | --- | --- |
| L1 编排与治理 | 会话生命周期、审计、配额、异常检测 | 无通用开源（结合 opentelemetry / langfuse 自建） | **自研为主** |
| L2 工具调用治理 | API/文件/网络的权限面 | 工具注册中心 + RBAC、出站白名单（eBPF/代理）、Vault 秘密管理 | **自研为主**（工具面是项目特有的） |
| L3 浏览器与桌面 | 页面操作、桌面操作 | 容器化 Playwright + CDP 代理（Steel / Browserbase）；云 VM（Windows Sandbox / QEMU）；computer-use（UI-TARS） | 底层开源为主，接入自研 |
| L4 代码运行时 | 不可信代码执行 | Docker → gVisor / Firecracker / Kata；WASM（WasmEdge / Wasmtime / Pyodide）；托管 E2B / Daytona / Modal | **开源为主** |

## 二、按能力面的实现要点

### 1. 代码执行沙箱（L4）
- **容器级（起步）**：每任务一个临时容器，只读根文件系统、无网络或出站白名单、内存/CPU/磁盘配额、超时强制销毁。Docker 是事实标准。
- **更强隔离**：gVisor（用户态内核，逃逸面小）、Firecracker/Kata（微 VM，适合多租户）。
- **极致轻量**：WASM 运行时（WasmEdge 为 CNCF 项目），Python 可用 Pyodide 编译到 WASM——确定性、无内核攻击面、启动毫秒级。
- **托管**：E2B / Daytona / Modal（云上现成沙箱 API，省运维，但有外发数据合规问题）。

### 2. 工具调用治理（L2）
- 工具注册中心声明权限（读/写/高危），高危工具走人工审批（项目已具备该模型）。
- 出站网络白名单（容器网络命名空间 / 代理层），文件系统按工具挂载只读卷。
- 秘密最小化：工具凭证独立于 agent 主凭证，经 Vault 注入。

### 3. 浏览器/桌面操作（L3）
- 浏览器：容器化 Chromium + Playwright，CDP 走代理限制导航目标与下载；开源参考 Steel，托管参考 Browserbase。
- 桌面：云虚拟机（Windows Sandbox / QEMU + RDP）或 remote browser isolation——成本最高，一般最后引入。

### 4. 编排治理（L1）
- 会话级身份 + 最小凭据、操作全量审计（可复用现有 observability / audit 模块）、资源配额与限流、会话快照/销毁。
- Prompt 注入防护：工具结果与指令隔离标注（现有 MCP 结果已带来源）。

## 三、对 x-QingChuan 的建议
1. 当前 agent-service 工具面仅为只读检索（rag.retrieve），**无需重型沙箱**；先把 L2 权限模型与 L1 审计补齐即可。
2. 未来引入代码执行：**Docker 临时容器起步**（阿里云 ECS 直接可用），需要更强隔离再评估 gVisor；轻量场景用 WASM/Pyodide。
3. 浏览器操作用**容器化 Playwright + CDP 白名单代理**（开源成熟），桌面操作最后考虑。
4. 治理层（工具权限/审批/审计/会话）**自主开发**，与现有 observability、eval 体系同构扩展。
