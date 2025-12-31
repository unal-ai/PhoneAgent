# 第三方许可证声明

本项目使用了以下开源项目的代码和灵感：

## PhoneAgent-Enterprise 主项目

- **许可证**: AGPL-3.0
- **版权**: Copyright (C) 2025 PhoneAgent Contributors
- **说明**: 本项目的核心代码

---

## Open-AutoGLM

- **许可证**: Apache-2.0
- **版权**: Copyright (c) 2024 ZAI Organization
- **项目地址**: https://github.com/zai-org/Open-AutoGLM
- **使用范围**: 
  - Vision模式智能体架构基础 (`phone_agent/agent.py`)
  - 动作处理逻辑 (`phone_agent/actions/`)
  - 屏幕分析和UI交互逻辑

---

## YADB - ADB 功能增强工具

- **许可证**: LGPL-3.0
- **作者**: ysbing
- **项目地址**: https://github.com/ysbing/YADB
- **使用方式**: 独立工具调用（subprocess，动态链接）
- **兼容性**: ✅ 完全兼容 - 作为独立二进制工具使用

**说明**:
- yadb 是一个 ADB 功能增强工具（DEX 文件，12KB）
- 主要功能：
  * ✅ **中文键盘输入** - 无需安装 APK，完美支持中文/Emoji
  * ✅ **强制截图** - 绕过应用截图限制（重要功能！）
  * ✅ **剪贴板操作** - 读写设备剪贴板
  * ✅ **高效布局 dump** - 替代 uiautomator
  * ✅ **长按操作** - 模拟长按手势
- 本项目通过 subprocess 调用 yadb（不嵌入源码）
- yadb 作为独立二进制文件运行，通过 ADB shell 调用
- 根据 LGPL-3.0，动态链接/独立调用完全合法

**使用示例**:
```python
# 通过 subprocess 调用（动态链接，不受 LGPL 传染）
subprocess.run([
    "adb", "shell", 
    "app_process", "-Djava.class.path=/data/local/tmp/yadb",
    "/data/local/tmp", "com.ysbing.yadb.Main",
    "-keyboard", "你好世界"  # 中文输入
])

# 强制截图（绕过应用限制）
subprocess.run([
    "adb", "shell",
    "app_process", "-Djava.class.path=/data/local/tmp/yadb",
    "/data/local/tmp", "com.ysbing.yadb.Main",
    "-screenshot"  # 输出到 stdout
])
```

**LGPL-3.0 许可证要点**:
- ✅ 允许作为独立工具调用（IPC 通信）
- ✅ 不要求主项目开源（因为是动态链接）
- ✅ 可用于商业项目
- ⚠️ 必须保留 yadb 的版权声明和许可证
- ⚠️ 必须提供 yadb 官方仓库链接
- ⚠️ 如果修改 yadb 源码，修改部分需以 LGPL-3.0 发布
- ✅ 本项目未修改 yadb 源码，仅作为工具调用

**文件位置**:
- 二进制文件：`phone_agent/resources/yadb` (12KB DEX 文件)
- 许可证：`phone_agent/resources/YADB_LICENSE.txt`
- 工具封装：`phone_agent/adb/yadb.py`

**来源**:
- 从 GELab-Zero 项目参考集成方式（他们也是直接调用）
- 或从官方仓库获取：https://github.com/ysbing/YADB/blob/master/yadb

---

## 许可证兼容性说明

### Apache-2.0 + AGPL-3.0 兼容性 ✅

根据 [GNU 许可证兼容性矩阵](https://www.gnu.org/licenses/license-compatibility.html)：

- **Apache-2.0** 是宽松许可证（Permissive License）
- **AGPL-3.0** 是 Copyleft 许可证
- **兼容性**: ✅ **完全兼容** - Apache-2.0 代码可以整合到 AGPL-3.0 项目中

**整合规则**:
1. Apache-2.0 代码可以在 AGPL-3.0 项目中使用
2. 整合后的代码必须遵循 AGPL-3.0 许可证
3. 必须保留 Apache-2.0 代码的版权声明、许可证文本和NOTICE文件
4. 必须在文件头部标注来源

### LGPL-3.0 + AGPL-3.0 兼容性 ⚠️

根据 [GNU 许可证兼容性](https://www.gnu.org/licenses/gpl-faq.html#AllCompatibility)：

- **LGPL-3.0** (Lesser GPL) 是弱 Copyleft 许可证
- **AGPL-3.0** (Affero GPL) 是强 Copyleft 许可证
- **兼容性**: ⚠️ **有条件兼容** - 需要遵循特定规则

**关键点**:

1. **动态链接 LGPL 库**: ✅ **允许**
   - 可以通过动态链接（如 pip 安装）使用 LGPL 库
   - 不需要开源你的 AGPL 代码
   - 示例：使用 `yadb` (LGPL-3.0) 作为依赖

2. **静态链接或修改 LGPL 代码**: ⚠️ **需要特殊处理**
   - 如果修改了 LGPL 库的代码，修改部分必须以 LGPL-3.0 发布
   - 如果静态链接，需要提供对象文件以便用户替换 LGPL 部分

3. **整体项目许可证**: 
   - 主项目保持 AGPL-3.0
   - LGPL 库保持 LGPL-3.0
   - 两者可以共存

**推荐方案**:

```python
# ✅ 推荐：作为依赖使用（动态链接）
# requirements.txt
yadb>=1.0.0  # LGPL-3.0

# 在代码中导入使用
from yadb import ADB
```

**不推荐**:
```python
# ❌ 不推荐：复制 LGPL 代码到项目中
# 这会导致许可证冲突
```

### 许可证兼容性总结表

| 依赖许可证 | AGPL-3.0 兼容性 | 使用方式 | 注意事项 |
|-----------|----------------|---------|---------|
| **Apache-2.0** | ✅ 完全兼容 | 可整合、可修改 | 保留版权和NOTICE |
| **LGPL-3.0** | ⚠️ 有条件兼容 | 动态链接（推荐） | 不要修改LGPL代码 |
| **MIT** | ✅ 完全兼容 | 可整合、可修改 | 保留版权声明 |
| **GPL-3.0** | ✅ 兼容 | 可整合 | 整体项目变为GPL-3.0+ |
| **BSD** | ✅ 完全兼容 | 可整合、可修改 | 保留版权声明 |

### yadb (LGPL-3.0) 使用建议

**当前状态**: 
- yadb 是 LGPL-3.0 许可证
- PhoneAgent-Enterprise 是 AGPL-3.0 许可证

**推荐方案**: ✅ **作为依赖使用**

```python
# requirements.txt
yadb>=1.0.0  # LGPL-3.0 - 动态链接，兼容AGPL-3.0

# 在代码中使用
from yadb import ADB

# 这种方式完全合法且兼容
```

**需要做的**:
1. ✅ 在 `LICENSES_THIRD_PARTY.md` 中声明 yadb 的使用
2. ✅ 保留 yadb 的 LGPL-3.0 许可证文本
3. ✅ 不要修改 yadb 的源代码
4. ✅ 如果用户想替换 yadb，提供接口抽象

**不需要做的**:
- ❌ 不需要将主项目改为 LGPL-3.0
- ❌ 不需要开源使用 yadb 的部分
- ❌ 不需要提供对象文件

### 文件头部标注示例

对于包含 Apache-2.0 代码的文件：

```python
#!/usr/bin/env python3
# Copyright (C) 2025 PhoneAgent Contributors
# Licensed under AGPL-3.0
#
# This file incorporates code from Open-AutoGLM (Apache-2.0 License)
# Copyright (c) 2024 ZAI Organization
# Original: https://github.com/zai-org/Open-AutoGLM
```

---

## 依赖项许可证

本项目使用的主要 Python 依赖项及其许可证：

| 依赖项 | 许可证 | 用途 |
|--------|--------|------|
| openai | MIT | AI 模型调用 |
| fastapi | MIT | Web 框架 |
| pydantic | MIT | 数据验证 |
| Pillow | HPND | 图像处理 |
| sqlalchemy | MIT | 数据库 ORM |

所有依赖项许可证均与 AGPL-3.0 兼容。

---

## 贡献者协议

向本项目贡献代码即表示您同意：

1. 您的贡献将以 AGPL-3.0 许可证发布
2. 您拥有贡献代码的版权或已获得授权
3. 您理解并接受 AGPL-3.0 的条款

---

## 致谢

感谢以下开源项目为本项目提供灵感和技术支持：

- **Open-AutoGLM** - 提供了视觉智能体架构基础和动作处理逻辑
- **YADB** - 提供了ADB增强功能（中文输入、强制截图）
- **智谱 AI** - 提供了优秀的中文多模态模型
- **FRP** - 提供了内网穿透解决方案
- **Scrcpy** - 提供了高效的屏幕镜像技术
- **Vue.js / FastAPI / Element Plus** - 提供了优秀的Web开发框架

---

## 联系方式

如有许可证相关问题，请联系：

- 项目主页: https://github.com/unal-ai/PhoneAgent
- Issue 追踪: https://github.com/unal-ai/PhoneAgent/issues

---

**最后更新**: 2025-12-24  
**文档版本**: v1.0.2  

