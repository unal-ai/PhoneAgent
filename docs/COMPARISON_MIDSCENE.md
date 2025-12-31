# PhoneAgent vs Midscene.js 对比分析

> 本文档分析 PhoneAgent 与 [Midscene.js](https://github.com/web-infra-dev/midscene) 在实现方式和原理上的异同。

## 项目概述对比

| 维度 | PhoneAgent | Midscene.js |
|------|------------|-------------|
| **定位** | Android 手机自动化平台 | 全平台 UI 自动化框架 |
| **语言** | Python + Vue.js | TypeScript (Node.js) |
| **平台支持** | Android | Web + Android + iOS + 桌面 |
| **AI 模型** | 智谱AI (GLM-4.1V) + OpenAI 兼容 | UI-TARS + Qwen-VL + Gemini + GPT |
| **许可证** | AGPL-3.0 | MIT |
| **成熟度** | 原型/Beta | v1.0 正式版 |

---

## 架构对比

### PhoneAgent 架构

```
┌─────────────────────────────────────────────────┐
│                Web Frontend (Vue 3)             │
├─────────────────────────────────────────────────┤
│              Server (FastAPI + WebSocket)       │
├─────────────────────────────────────────────────┤
│          phone_agent Core (Python)              │
│  ┌─────────────┬─────────────┬────────────┐    │
│  │ PhoneAgent  │ ModelClient │ ADB 操作    │    │
│  │ (Vision)    │ (API调用)   │ (截图/点击) │    │
│  └─────────────┴─────────────┴────────────┘    │
├─────────────────────────────────────────────────┤
│          Termux Client (FRP + ADB)              │
└─────────────────────────────────────────────────┘
```

### Midscene.js 架构

```
┌─────────────────────────────────────────────────┐
│        SDK (npm packages)                       │
│  @midscene/web | @midscene/android | @midscene/ios │
├─────────────────────────────────────────────────┤
│              @midscene/core                     │
│  ┌─────────────┬─────────────┬────────────┐    │
│  │ Agent       │ TaskRunner  │ Service    │    │
│  │ (状态机)    │ (任务调度)  │ (AI服务)   │    │
│  └─────────────┴─────────────┴────────────┘    │
├─────────────────────────────────────────────────┤
│          Device Abstraction Layer              │
│  (AbstractInterface - Puppeteer/Playwright/ADB/WDA) │
└─────────────────────────────────────────────────┘
```

---

## 核心实现原理对比

### 1. AI 决策流程

**PhoneAgent (Step-by-Step)**:
```python
# 循环执行，每步都调用 AI
while not finished:
    screenshot = get_screenshot()
    response = model.request(context + screenshot)  # AI 决策
    action = parse_action(response)                 # 解析动作
    result = action_handler.execute(action)         # 执行动作
```

**Midscene.js (Plan & Execute)**:
```typescript
// 先规划完整计划，再批量执行
const plans = await plan(userInstruction, context);  // AI 生成计划
for (const action of plans) {
    await taskExecutor.runPlans(action);             // 执行动作
    // 可选: 重新规划 (replanning)
}
```

### 2. 元素定位策略

| 策略 | PhoneAgent | Midscene.js |
|------|------------|-------------|
| **纯视觉** | Vision Agent (主要) | 默认模式 |
| **UI 树** | XML Kernel (Beta, 已废弃) | 已在 v1.0 移除 |
| **坐标系统** | 相对坐标 (0-1000) | 绝对坐标 (像素) |
| **缩放处理** | 手动转换 | 自动缩放 (screenshotScale) |

### 3. 缓存机制

**PhoneAgent**: 无系统性缓存

**Midscene.js**: 
```typescript
// 任务级缓存
const matchedCache = this.taskCache?.matchPlanCache(taskPrompt);
if (matchedCache) {
    return this.runYaml(matchedCache.yamlWorkflow);  // 命中缓存，直接执行
}
```

---

## Midscene.js 核心亮点 (可借鉴)

### 1. YAML 脚本驱动

**优势**: 将 AI 自动化步骤持久化为可复用的 YAML 脚本

```yaml
# Midscene YAML 示例
tasks:
  - name: "登录测试"
    flow:
      - aiTap: "用户名输入框"
      - aiInput: 
          prompt: "用户名输入框"
          value: "testuser"
      - aiTap: "登录按钮"
      - aiAssert: "登录成功"
```

**PhoneAgent 可借鉴**: 
- 将成功的任务执行序列保存为 YAML
- 支持从 YAML 脚本回放，减少 AI 调用

### 2. 智能重规划 (Replanning)

**优势**: 执行失败时自动重新规划，提高成功率

```typescript
// Midscene 重规划机制
const replanningCycleLimit = 20;
while (retryCount < replanningCycleLimit) {
    try {
        await execute(plan);
        break;
    } catch (error) {
        plan = await replan(task, error, context);
        retryCount++;
    }
}
```

**PhoneAgent 可借鉴**:
- 添加执行失败后的智能重试
- 根据错误信息调整执行策略

### 3. 可视化调试报告

**优势**: 自动生成 HTML 报告，包含截图和执行轨迹

```typescript
// Midscene 报告生成
this.reportFile = writeLogFile({
    fileName: this.reportFileName,
    fileContent: this.dumpDataString(),
    type: 'dump',
    generateReport: true,
});
```

**PhoneAgent 可借鉴**:
- 当前仅保存 JSONL 日志
- 可添加 HTML 可视化报告生成

### 4. 上下文冻结 (Context Freezing)

**优势**: 减少重复截图，提高批量操作效率

```typescript
// 冻结上下文
await agent.freezePageContext();
await agent.aiTap("按钮1");
await agent.aiTap("按钮2");  // 复用上次截图
await agent.unfreezePageContext();
```

**PhoneAgent 可借鉴**:
- 连续操作时复用截图
- 减少 ADB 截图开销

### 5. 设备抽象层 (AbstractInterface)

**优势**: 统一接口，支持多平台扩展

```typescript
// Midscene 设备抽象
interface AbstractInterface {
    screenshotBase64(): Promise<string>;
    size(): Promise<Size>;
    actionSpace(): DeviceAction[];
}

// 不同平台实现
class AndroidDevice implements AbstractInterface { ... }
class PuppeteerPage implements AbstractInterface { ... }
class IOSDevice implements AbstractInterface { ... }
```

**PhoneAgent 可借鉴**:
- 当前 ADB 操作直接调用命令
- 可抽象为统一接口，便于扩展 iOS 等平台

### 6. MCP 集成

**优势**: 支持 Model Context Protocol，可被上层 Agent 调用

```typescript
// Midscene MCP Server
export const mcpTools = [
    { name: "screenshot", handler: async () => { ... } },
    { name: "tap", handler: async (x, y) => { ... } },
];
```

**PhoneAgent 可借鉴**:
- 可将核心操作暴露为 MCP Tools
- 便于与 Claude、Cursor 等集成

---

## 单机 MVP 运行流程

### PhoneAgent 单机 MVP (最简方案)

**前提条件**:
1. 一台 Android 手机 (Android 7.0+)
2. 一台电脑 (Windows/macOS/Linux)
3. USB 数据线
4. 智谱AI API Key (免费)

**步骤**:

```bash
# 1. 克隆项目
git clone https://github.com/unal-ai/PhoneAgent.git
cd PhoneAgent

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 配置 API Key
cp env.example .env
# 编辑 .env，填写 ZHIPU_API_KEY

# 4. 手机连接电脑，开启 USB 调试
adb devices  # 确认设备已连接

# 5. 启动后端服务
python -m uvicorn server.api.app:app --host 0.0.0.0 --port 8000

# 6. 启动前端 (另一个终端)
cd web && npm install && npm run dev

# 7. 访问 http://localhost:5173
```

**命令行使用**:

```python
# cli_demo.py - 单机命令行 MVP
from phone_agent import PhoneAgent
from phone_agent.model import ModelConfig

# 配置模型
config = ModelConfig(
    api_key="your-zhipu-api-key",
    base_url="https://open.bigmodel.cn/api/paas/v4/",
    model_name="glm-4.1v-thinking-flash"
)

# 创建 Agent (默认使用第一个设备)
agent = PhoneAgent(model_config=config)

# 执行任务
result = agent.run("打开设置，找到关于手机")
print(f"结果: {result}")
```

### Midscene.js 单机 MVP

**前提条件**:
1. Node.js 18+
2. Android 设备 + ADB
3. OpenAI API Key 或其他 VLM

**步骤**:

```bash
# 1. 安装 CLI
npm install -g @midscene/cli

# 2. 配置模型
export OPENAI_API_KEY="sk-xxx"
# 或使用智谱
export MIDSCENE_MODEL_NAME="qwen-vl-max"
export MIDSCENE_USE_OPENAI_SDK=1
export OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export OPENAI_API_KEY="sk-xxx"

# 3. 运行 Android Playground
npx @midscene/cli android

# 4. 在 Playground 中输入指令
# "打开设置"
```

---

## 关键差异总结

| 特性 | PhoneAgent | Midscene.js | 建议 |
|------|------------|-------------|------|
| **执行模式** | 逐步决策 | 规划后执行 | PhoneAgent 更稳定，Midscene 更高效 |
| **缓存** | 无 | YAML 缓存 | 应借鉴 |
| **重规划** | 无 | 支持 | 应借鉴 |
| **报告** | JSONL | HTML 可视化 | 应借鉴 |
| **多平台** | Android | Web/Android/iOS | 按需扩展 |
| **部署模式** | Server + Client | SDK 本地运行 | 各有优势 |

---

## 行动建议

### 短期 (1-2 周)

1. **添加 YAML 脚本支持**
   - 保存成功任务为 YAML
   - 支持从 YAML 回放

2. **添加任务缓存**
   - 相同指令复用历史结果
   - 减少 AI 调用成本

### 中期 (2-4 周)

3. **实现智能重规划**
   - 执行失败自动重试
   - 根据错误调整策略

4. **生成 HTML 报告**
   - 可视化执行轨迹
   - 便于调试和分享

### 长期 (4+ 周)

5. **设备抽象层重构**
   - 统一接口
   - 支持扩展 iOS、Web

6. **MCP 集成**
   - 暴露为 MCP Tools
   - 与更多 AI Agent 集成

---

**文档版本**: v1.0  
**最后更新**: 2025-01
