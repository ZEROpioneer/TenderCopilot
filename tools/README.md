# 工具目录

本目录包含用于调试和维护 TenderCopilot 系统的辅助工具。

## 工具列表

### 1. find_api_endpoint.py
**用途**: 手动查找军队采购网的真实 API 端点

**使用方法**:
```bash
python tools/find_api_endpoint.py
```

**功能**:
- 自动打开浏览器访问军队采购网
- 引导你使用开发者工具查找 API
- 提供详细的操作步骤和提示

**适用场景**:
- API 端点失效需要更新时
- 想要优化爬取性能时

---

### 2. test_api_endpoints.py
**用途**: 测试多个可能的 API 端点

**使用方法**:
```bash
python tools/test_api_endpoints.py
```

**功能**:
- 自动测试预设的多个 API 端点
- 报告哪些端点可用
- 显示响应数据结构

**适用场景**:
- 快速验证 API 端点是否可用
- 找到新的 API 地址后测试

**自定义端点**:
编辑脚本中的 `possible_endpoints` 列表来添加新的端点。

---

### 3. verify_codes.py
**用途**: 验证地区代码和公告类型代码映射

**使用方法**:
```bash
python tools/verify_codes.py
```

**功能**:
- 显示当前配置的地区代码
- 显示当前配置的公告类型代码
- 检查配置完整性
- 提供验证指南

**适用场景**:
- 检查配置是否正确
- 理解当前的筛选配置

---

## 工作流程示例

### 场景 1: API 端点失效，需要更新

1. **查找新的 API 端点**
   ```bash
   python tools/find_api_endpoint.py
   ```
   按照提示操作，找到正确的 API URL 和参数格式

2. **测试新端点**
   编辑 `test_api_endpoints.py`，将新端点添加到 `possible_endpoints` 列表
   ```bash
   python tools/test_api_endpoints.py
   ```

3. **更新配置**
   编辑 `config/filter_settings.yaml`：
   ```yaml
   api:
     endpoint: "/你找到的新端点"
   ```

4. **验证**
   ```bash
   python main.py --mode once
   ```

### 场景 2: 筛选结果不准确

1. **验证代码映射**
   ```bash
   python tools/verify_codes.py
   ```

2. **使用浏览器验证**
   ```bash
   python tools/find_api_endpoint.py
   ```
   在开发者工具中查看实际的地区代码和类型代码

3. **更新配置**
   编辑 `config/filter_settings.yaml` 中的映射表

### 场景 3: 调试爬虫问题

1. **运行调试脚本**（项目根目录）
   ```bash
   python analyze_cggg_page.py
   ```
   或
   ```bash
   python debug_spider.py
   ```

2. **查看调试输出**
   检查 `data/debug/` 目录下的截图和 HTML 文件

3. **根据结果调整爬虫选择器**

---

## 注意事项

1. **编码问题**: Windows 控制台可能无法正确显示 emoji，这是正常的，不影响功能

2. **浏览器要求**: 这些工具使用 DrissionPage，需要 Chrome/Edge 浏览器

3. **网络要求**: 需要能够访问 https://www.plap.mil.cn/

4. **配置备份**: 修改配置前建议备份 `config/` 目录

---

## 获取帮助

如果工具运行出错：
1. 检查 Python 版本（需要 3.8+）
2. 确认已安装所有依赖：`pip install -r requirements.txt`
3. 查看错误日志了解详情

---

*最后更新: 2026-02-04*
