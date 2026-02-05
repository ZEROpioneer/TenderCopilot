# Prototype 测试代码

此目录包含爬虫功能开发和验证过程中的测试脚本。这些代码已经过充分测试并成功合并到主项目中。

## 📁 文件说明

### 核心工具
- **`common_utils.py`**: 经过验证的通用工具函数
  - `wait_and_load_page()`: 稳健的页面加载函数（含重试机制）
  - `find_announcement_items()`: 查找公告列表项
  - `parse_list_item_v2()`: 解析列表项（地域、日期提取）

### 测试脚本（按开发顺序）

1. **`test_01_basic.py`**: 基础爬取测试
   - 验证页面加载
   - 验证列表项解析
   - 测试数据库保存

2. **`test_02_pagination.py`**: 翻页功能测试
   - 验证分页元素识别
   - 测试翻页操作
   - 检查多页数据获取

3. **`test_03_time_filter.py`**: 时间过滤测试
   - 验证时间窗口过滤
   - 测试增量爬取逻辑

4. **`test_04_keyword_filter.py`**: 关键词匹配测试
   - 验证关键词匹配逻辑
   - 测试业务方向识别
   - 检查地域限制

5. **`test_05_dedup.py`**: 去重功能测试
   - 验证数据库去重
   - 测试内部去重逻辑
   - 检查重复数据处理

6. **`test_06_e2e.py`**: 端到端流程测试
   - 完整流程验证
   - 集成所有功能模块

7. **`test_full_workflow.py`**: 最终完整流程测试
   - 多页爬取（3页）
   - 智能停止机制
   - 完整的问题检查

### 调试脚本

- **`debug_pagination.py`**: 翻页调试工具
  - 用于排查翻页问题
  - 分析分页元素结构
  - 测试不同的选择器策略

## 🎯 关键发现

### 1. AJAX内容加载
**问题**: 页面内容为空，公告列表未加载

**解决方案**:
```python
# 显式等待AJAX内容
page.wait.ele_displayed('css:ul.noticeShowList li a', timeout=20)

# 滚动触发延迟加载
page.scroll.to_bottom()
time.sleep(0.5)
```

### 2. 翻页元素识别
**问题**: 无法找到"下一页"按钮

**解决方案**:
```python
# 错误：查找 <a> 标签
next_btn = page.ele('xpath://div[@id="pagination"]//a[text()=">"]')

# 正确：查找 <li> 标签
next_btn = page.ele('xpath://div[@id="pagination"]//li[text()=">"]')
```

### 3. 内容刷新检测
**问题**: 翻页后内容未刷新，出现重复数据

**解决方案**:
```python
# 记录当前第一条公告标题
first_title = items[0].ele('tag:a').text

# 点击下一页
next_btn.click()

# 等待内容变化
for _ in range(10):
    new_items = page.eles('css:ul.noticeShowList li')
    if new_items:
        new_first_title = new_items[0].ele('tag:a').text
        if new_first_title != first_title:
            break  # 内容已刷新
    time.sleep(1)
```

### 4. 地域信息提取
**问题**: 地域信息提取错误或为空

**解决方案**:
```html
<!-- HTML 结构 -->
<li>
  <a>标题</a>
  <span>类型</span>
  <span>地域</span>  <!-- spans[1] -->
  <span>日期</span>  <!-- spans[2] -->
</li>
```

```python
# 正确提取
location = spans[1].text.strip() if len(spans) >= 3 else "未知"
pub_date = spans[2].text.strip() if len(spans) >= 3 else None
```

## 📊 测试结果

| 测试项 | 状态 | 说明 |
|--------|------|------|
| 基础爬取 | ✅ | 单页爬取正常 |
| 翻页功能 | ✅ | 可正确识别和翻页 |
| 时间过滤 | ✅ | 增量爬取正确 |
| 关键词匹配 | ✅ | 业务方向识别准确 |
| 去重功能 | ✅ | 无重复数据 |
| 端到端 | ✅ | 完整流程运行正常 |
| 多页爬取 | ✅ | 3-5页爬取稳定 |

## 🔄 已合并到主项目

以下功能已成功合并到 `src/spider/plap_spider.py` 和 `main.py`：

- ✅ 页面加载重试机制
- ✅ AJAX内容显式等待
- ✅ 智能翻页和内容检测
- ✅ 地域信息正确提取
- ✅ 多页爬取支持
- ✅ 实时数据库去重
- ✅ 智能增量停止

## 💡 使用建议

1. **参考学习**: 这些脚本展示了如何逐步解决实际问题
2. **问题复现**: 如果主项目出现问题，可使用这些脚本快速定位
3. **功能验证**: 修改爬虫逻辑后，可先在此测试再应用
4. **保留备份**: 建议保留此目录作为开发历史记录

## ⚠️ 注意

- 这些脚本仅用于开发和测试
- 不应在生产环境中直接运行
- 部分脚本可能需要调整配置路径
- 建议在隔离环境中运行测试
