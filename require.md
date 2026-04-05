# 项目环境安装清单（Windows 64 位）

本文档适用于 `Windows 10 64 位` + `PowerShell` 环境。

目标是帮助你从 0 开始按顺序安装本项目需要的开发工具，并用最直接的命令检查是否安装成功。

说明：
- 本项目代码仍然是在你本地电脑上编写。
- `Docker Desktop` 主要用于运行数据库、缓存等配套环境。
- 根据 [tasks.md](D:/graduation-project/tasks.md) 的规划，`PostgreSQL` 和 `Redis` 后续优先通过 Docker 启动，不建议现在单独安装到 Windows 里。

## 一、建议安装顺序

建议按下面顺序安装：

1. `Git`
2. `Node.js 20 LTS (x64)`
3. `Python 3.11 (x64)`
4. `Docker Desktop for Windows (x64)`
5. `VS Code`（推荐安装，不是运行项目的硬性前提）
6. 后面做到算法模块时，再安装：
   - `Visual Studio Build Tools 2022`
   - `CMake (x64)`

## 二、现在先安装

### 1. Git

- 是否现在安装：是
- 作用：代码版本管理，后续提交、回退、同步代码都会用到
- 检查命令：

```powershell
git --version
```

- Windows 注意事项：
  - 安装时保持默认选项通常就可以
  - 安装完成后重新打开 PowerShell 再检查

### 2. Node.js 20 LTS (x64)

- 是否现在安装：是
- 作用：运行前端 `Vue3 + TypeScript`
- 检查命令：

```powershell
node -v
npm -v
```

- Windows 注意事项：
  - 建议下载 `LTS` 版本，不要选过新的实验版本
  - 建议安装 `x64` 版本

### 3. Python 3.11 (x64)

- 是否现在安装：是
- 作用：运行后端 `FastAPI`、数据处理脚本、后续工具脚本
- 检查命令：

```powershell
python --version
pip --version
py --version
```

- Windows 注意事项：
  - 安装时勾选 `Add Python to PATH`
  - 如果 `python --version` 不正常，但 `py --version` 正常，也说明 Python 基本已安装成功
  - 建议安装 `3.11.x` 的 `x64` 版本

### 4. Docker Desktop for Windows (x64)

- 是否现在安装：是
- 作用：后续用 `docker compose` 统一启动 `PostgreSQL`、`Redis` 等环境
- 检查命令：

```powershell
wsl --status
docker --version
docker compose version
```

- Windows 注意事项：
  - 在 `Windows 10` 上，`Docker Desktop` 通常依赖 `WSL 2`
  - 电脑需要开启虚拟化支持；如果 Docker 无法启动，先检查 BIOS/任务管理器里的虚拟化状态
  - 如果 `wsl --status` 提示未安装或未启用，需要先完成 `WSL 2` 配置
  - 看到 `docker compose version` 正常输出，比只看到 `docker --version` 更关键

### 5. VS Code

- 是否现在安装：推荐安装
- 作用：写前端、后端和文档都很方便
- 检查命令：

```powershell
code --version
```

- Windows 注意事项：
  - 如果 `code --version` 无法识别，通常是安装时没有把 VS Code 加入 `PATH`
  - 即使 `code` 命令暂时不可用，VS Code 本体也可能已经装好了
  - 推荐后续安装扩展：`Python`、`C/C++`、`Docker`、`ESLint`

## 三、现在先不要单独安装

### 1. PostgreSQL

- 是否现在安装：否
- 原因：
  - 你的任务规划已经明确把 `PostgreSQL 15+` 作为主数据库
  - 同时也明确把 `Docker Compose` 作为本地开发与演示环境统一方案
  - 对新手来说，优先用 Docker 跑数据库，比直接装到 Windows 更省事、更不容易出环境问题

### 2. Redis

- 是否现在安装：否
- 原因：
  - 你的项目里 `Redis` 主要承担缓存和任务状态作用
  - 后续建议和 `PostgreSQL` 一起交给 Docker 统一启动

## 四、后面做到算法模块时再安装

### 1. Visual Studio Build Tools 2022

- 是否现在安装：暂时不用
- 作用：提供 Windows 下的 C++ 编译环境，后续给 `algo-engine` 使用
- 安装时建议选择：
  - `Desktop development with C++`
- 检查命令：

```powershell
cl
```

- Windows 注意事项：
  - `cl` 不一定能在普通 PowerShell 里直接使用
  - 请优先在 `x64 Native Tools Command Prompt for VS 2022` 或 `Developer PowerShell for VS 2022` 中检查
  - 只要在对应的 VS 开发者终端里能识别 `cl`，就说明基本正常

### 2. CMake (x64)

- 是否现在安装：暂时不用
- 作用：后续编译 C++ 算法模块时常用
- 检查命令：

```powershell
cmake --version
```

- Windows 注意事项：
  - 建议安装 `x64` 版本
  - 安装时注意把 CMake 加入 `PATH`

## 五、你完成第一阶段后，最少应能检查成功的命令

下面这些命令，表示你已经具备开始做这个项目的基础环境：

```powershell
git --version
node -v
npm -v
python --version
pip --version
py --version
wsl --status
docker --version
docker compose version
```

## 六、简短结论

对你现在这个阶段，先装下面 4 个最重要：

1. `Git`
2. `Node.js`
3. `Python`
4. `Docker Desktop`

`PostgreSQL` 和 `Redis` 先不要单独装。  
`C++` 编译环境等你做到算法模块时再装。  
这样最适合新手，也最符合你当前项目任务文件的规划。
