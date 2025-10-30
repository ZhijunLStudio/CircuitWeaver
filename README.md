# CircuitWeaver 🤖🔌 - 一个能自我进化、支持并发的电路设计AI代理系统

CircuitWeaver 是一个先进的、自主化的AI代理系统，其核心任务是从高级概念出发，生成使用 `schemdraw` 库的Python脚本，以绘制专业的电子电路图。它实现了一套健壮的、能够从错误和成功中持续学习的自动化工作流。

本系统采用并发的“工厂”模式运行，能够并行处理多个独立的电路设计任务。当代理（Agent）生成的代码出错时，系统会触发一个“集体反思”机制，由一个AI模型团队协同寻找解决方案，并将成功的修复经验存入持久化的知识库。更进一步，系统还会将所有最终成功的代码收录到一个“成功案例库”中，用于在未来生成新电路时提供高质量的上下文参考。

---

## ✨ 核心特性

*   **🧠 端到端自动化**: 从电路构思到最终生成可运行的 `schemdraw` 脚本和高质量SVG图纸，整个流程完全自主。
*   **🚀 并发代理工厂**: 支持并行运行多个电路设计任务，最大化提升产出效率，并能以服务模式持续运行。
*   **🤝 集体问题解决**: 采用“模型竞速”机制，让多个AI模型并行提出修复方案。即使所有模型都失败，系统也能聚合所有失败经验，形成“集体记忆”以指导下一轮尝试。
*   **📚 双循环学习系统 (Dual-Loop Learning)**:
    *   **修复经验库 (Corrective Learning)**: 能够从连续的失败链中进行“多步归纳学习”。成功的修复方案会被AI“方案矿工”异步提炼，并存入持久化的SQLite知识库。
    *   **成功代码库 (Creative Learning)**: 所有最终成功的电路代码都会被自动收录。在生成新电路时，系统会通过RAG动态检索最相关的成功案例作为高质量的上下文示例。
*   **🔍 混合知识检索**: 创造性地结合了**三种知识来源**——官方文档（静态RAG）、修复经验（动态KB）和成功案例（动态RAG），为AI提供最全面的决策依据。
*   **📦 轻量级安全沙箱**: 使用基于Python `multiprocessing` 的安全本地沙箱，在**隔离的临时目录**中执行和验证每一段代码，根除了并发冲突。
*   **💾 极致透明的日志**: 每一次代码执行（无论是验证还是修复尝试）的所有产物（代码、错误、输出、图片）都被清晰地、原子化地保存在其专属的目录中，提供了无与伦比的可追溯性。

## 🏛️ 系统架构

系统由一个多阶段、迭代式的循环进行编排：

1.  **构思 (Ideation)**: AI规划师提出电路概念。
2.  **动态上下文生成 (Dynamic Context Generation)**: 系统使用电路概念，从“成功代码库”中检索（RAG）出N个最相关的、已完成的完整代码，并结合固定的“风格指南”示例，共同构成高质量的上下文。
3.  **初始代码生成 (Initial Code Generation)**: AI程序员基于电路概念和丰富的上下文，生成第一版 `schemdraw` 脚本。
4.  **验证与调试循环 (Validation & Debug Loop)**:
    *   **验证**: 代码在一个隔离的沙箱目录中执行。若成功，则流程结束；若失败，则启动集体调试循环，并将失败记录到“失败链”中。
    *   **集体调试**:
        *   **混合检索**: 从“文档库”和“修复经验库”中检索线索。
        *   **模型竞速**: 多个AI模型并行提出修复方案。
        *   **独立验证**: 每个方案在各自的隔离目录中验证。
        *   **决策与学习**: 若有模型成功，则采纳其方案并触发对“失败链”的归纳学习；若全部失败，则生成“集体失败报告”并继续下一轮调试。
5.  **最终产出 (Finalization)**: 成功的脚本被保存并再次运行以生成最终SVG图纸。该成功脚本及其电路概念被自动添加到“成功代码库”中。

## 🛠️ 安装与设置

### 1. 环境要求
*   Python 3.10+
*   一个兼容OpenAI的API Key和API服务地址（Endpoint URL）。
*   (可选但强烈推荐) 一块支持CUDA的NVIDIA GPU，用于加速嵌入模型的计算。

### 2. 克隆仓库
```bash
git clone https://github.com/ZhijunLStudio/CircuitWeaver.git
cd CircuitWeaver
```

### 3. 设置环境变量
在项目根目录创建一个 `.env` 文件（此文件已在 `.gitignore` 中被忽略），或直接在终端中导出以下环境变量：
```bash
# .env 文件内容
OPENAI_API_KEY="你的API Key"
OPENAI_BASE_URL="你的API服务地址"
```
或者
```bash
export OPENAI_API_KEY="你的API Key"
export OPENAI_BASE_URL="你的API服务地址"
```

### 4. 配置模型

**重要**: `configs/models.py` 文件包含模型名称和路径等敏感信息，**不应**上传到公共代码库。您需要根据自己的环境手动创建或修改此文件。

下面是一个配置示例 `configs/models.py`:
```python
import os

# API凭证将从环境变量中读取
API_KEY = os.getenv("OPENAI_API_KEY", "your_default_key_if_any")
BASE_URL = os.getenv("OPENAI_BASE_URL", "your_default_url_if_any")

# --- 模型选择 ---

# 用于创意构思阶段的模型
MODEL_FOR_CREATION = os.getenv("MODEL_FOR_CREATION", "gemini-2.5-pro")

# 用于代码生成和修复的模型列表
# 强烈建议在此处配置多个模型（即使是重复相同的模型名称）
# 这可以激发多样性，是系统“集体问题解决”能力的关键。
MODELS_FOR_FIXING = [
    "gemini-2.5-pro", 
    "claude-3-sonnet", # 示例
    "qwen-max"         # 示例
]

# --- RAG嵌入模型 ---

# 指定您本地存放的Sentence-Transformer模型的路径
# 示例: "/path/to/your/models/bge-large-en-v1.5"
EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-4B"
```

### 5. 安装依赖库

我们强烈建议您先单独安装PyTorch，以确保其版本与您的系统和CUDA环境兼容。

**步骤 5.1: 安装PyTorch**
请访问 [PyTorch官方网站](https://pytorch.org/) 获取适合您系统的安装命令。例如，对于Linux和CUDA 11.8环境：
```bash
pip3 install torch torchvision torudio --index-url https://download.pytorch.org/whl/cu118
```

**步骤 5.2: 安装其余依赖**
```bash
pip install -r requirements.txt
```

### 6. 准备知识库

**步骤 6.1: 放置语料库**
将你的 `schemdraw` 文档文件（`.md` 格式）放入 `corpus/cleaned_markdown_corpus/` 目录下。

**步骤 6.2: 构建向量数据库**
运行此脚本来处理语料库并创建FAISS向量索引。此操作只需执行一次，或者在您更新语料库后再次执行。
```bash
python scripts/build_vector_db.py
```

## 🚀 运行代理工厂

您可以通过命令行参数来控制工厂的运行模式。

**以2个并发代理生成总计10个电路:**
```bash
python main.py --num-jobs 10 --workers 2
```

**以3个并发代理持续运行:**
*(工厂会不断生成电路，直到您使用 Ctrl+C 停止它)*
```bash
python main.py --num-jobs 0 --workers 3
```

**命令行选项:**
*   `-n, --num-jobs`: 要生成的电路总数。`0` 代表无限生成。(默认: 10)
*   `-w, --workers`: 并发运行的代理数量。(默认: 2)

## ⚙️ 系统配置

核心配置项位于 `configs/` 目录下：

*   **`configs/models.py`**: (见上文“配置模型”部分)
*   **`configs/settings.py`**:
    *   `MAX_DEBUG_ATTEMPTS`: 单个代理在一个任务中最大调试轮次。
    *   `SUCCESS_CODE_RAG_K`: 在生成新代码时，从成功代码库中检索的示例数量。
    *   `SANDBOX_TIMEOUT`: 代码执行沙箱的超时时间（秒）。
    *   以及语料库、运行结果和知识库等文件的路径配置。

## 📂 项目结构

```
.
├── configs/              # 模型与应用配置
├── corpus/               # 静态文档语料库与向量数据库
├── knowledge_base/       # 动态修复经验数据库 (SQLite) 与日志
├── successful_circuits/  # 动态成功案例代码库
├── prompts/              # 所有AI代理的提示语
├── results/              # 所有运行的输出目录和产物
├── scripts/              # 辅助脚本 (例如, 构建向量数据库)
├── src/                  # 主要源代码
│   ├── core/             # 编排器, 方案矿工, 成功代码管理器
│   ├── db/               # 知识库管理器
│   ├── sandbox/          # 本地代码执行沙箱
│   ├── tools/            # RAG工具
│   └── utils/            # 辅助工具函数
└── main.py               # 运行工厂的主入口
```


# 版本升级日志

## [3.0.0] - 系统功能完善与动态学习

### 新增特性 (Features)

*   **新增“成功代码库”**:
    *   创建 `successful_circuits/` 目录，用于持久化存储所有最终成功的电路代码 (`.py` 文件) 和对应的元数据 (`metadata.jsonl`)。
    *   实现 `SuccessCodeManager`，负责管理此代码库，包括添加新代码和通过RAG进行检索。
*   **实现动态Few-Shot学习**: 在初始代码生成阶段，系统会从“成功代码库”中检索与当前任务最相关的 `k` 个完整代码示例，并将其注入Prompt，以提高初始代码的质量和相关性。
*   **实现“多步归纳学习”**:
    *   升级 `SolutionMiner`，使其能够分析从上一次成功到当前成功之间的完整“失败链”。
    *   Agent现在可以从一次成功的修复中，同时提炼出多个不同错误的解决方案，提高了学习效率。

### 优化与重构 (Refactoring)

*   **移除自动标注模块**: 简化了Agent的核心任务，使其专注于生成可运行的绘图脚本，增强了系统的健壮性和模块化。
*   **优化最终产出流程**: 成功的任务现在会额外生成一份带清晰命名的 `final_successful_diagram.svg`。

## [2.0.0] - 并发安全与调试逻辑强化

### 新增特性 (Features)

*   **实现“集体反思”机制**: 当一轮模型竞速全部失败时，系统会聚合所有模型的失败代码和错误，形成一份详细的“集体失败报告”，并添加到对话历史中，以指导下一轮修复。
*   **实现“前进式”状态更新**: 修复了Agent在调试循环中卡在旧错误状态的bug，确保了调试过程的线性推进。

### 优化与重构 (Refactoring)

*   **实现隔离的执行环境**:
    *   重构 `LocalCodeSandbox` 和 `Orchestrator`，为每一次代码验证创建唯一的、隔离的子目录。
    *   解决了并发写入同一个图片文件导致的竞争条件问题。
*   **统一并增强日志系统**: 实现了全新的、高度透明的目录和文件命名规范，增强了系统的可追溯性。
*   **更新文件夹命名格式**: 采用了 `日期_时间_Job_UUID` 的格式。

## [1.0.0] - 基础框架与并发模型

### 新增特性 (Features)

*   建立并发代理“工厂”模型，支持并行运行多个电路设计任务。
*   实现“模型竞速”机制，让多个模型并行修复错误，并采纳首个成功者的方案。
*   引入“修复经验库”，通过 `SolutionMiner` 实现从单步修复中学习并持久化到SQLite。
*   引入“混合知识检索”，结合静态文档RAG和动态经验库。
*   建立基于 `multiprocessing` 的轻量级本地沙箱。
*   实现绝对串行的资源预初始化流程，解决了并发死锁问题。