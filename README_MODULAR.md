# Smart Align Pro - 模組化架構

## 📁 檔案結構

```
smart_align_pro_ultimate_tw/
├── smart_align_pro_ultimate_tw.py     # 原始單檔版本
├── smart_align_pro_modular.py         # 新的模組化版本主入口
├── settings.py                        # 設置屬性模組
├── core/                              # 核心算法模組
│   ├── __init__.py
│   ├── alignment.py                   # 對齊算法
│   ├── math_utils.py                  # 數學工具
│   └── detection.py                   # 物件檢測
├── operators/                         # 操作器模組
│   ├── __init__.py
│   ├── alignment_operators.py         # 對齊操作器
│   ├── preview_operators.py           # 預覽操作器
│   └── utility_operators.py           # 工具操作器
├── ui/                               # UI 模組
│   ├── __init__.py
│   └── main_panel.py                  # 主面板
├── utils/                            # 工具模組
│   ├── __init__.py
│   ├── bbox_utils.py                  # 邊界框工具
│   ├── measurement_utils.py           # 測量工具
│   └── animation_utils.py             # 動畫工具
└── 使用說明.md                        # 使用說明
```

## 🏗️ 架構優勢

### 1. **模組化設計**
- **核心分離**: 對齊算法與UI分離
- **職責清晰**: 每個模組負責特定功能
- **易於維護**: 修改某功能不影響其他部分

### 2. **可擴展性**
- **插件式架構**: 新功能可獨立開發
- **標準化接口**: 統一的模組接口
- **版本兼容**: 向後兼容原有功能

### 3. **代碼質量**
- **減少耦合**: 模組間依賴最小化
- **提高復用**: 核心算法可被多處使用
- **便於測試**: 每個模組可獨立測試

## 📦 模組說明

### Core 模組 (`core/`)
- **alignment.py**: 核心對齊算法實現
- **math_utils.py**: 數學計算工具函數
- **detection.py**: 智能物件檢測系統

### Operators 模組 (`operators/`)
- **alignment_operators.py**: 兩點、三點、表面法線等對齊操作器
- **preview_operators.py**: 預覽系統操作器
- **utility_operators.py**: 測量、分析、批量處理等工具操作器

### UI 模組 (`ui/`)
- **main_panel.py**: 主界面面板、設置面板、信息面板

### Utils 模組 (`utils/`)
- **bbox_utils.py**: 邊界框相關工具
- **measurement_utils.py**: 測量和分析工具
- **animation_utils.py**: 動畫和時間軸工具

## 🚀 使用方式

### 開發者
```python
# 導入核心算法
from core.alignment import two_point_align, three_point_align
from core.detection import detect_object_type

# 導入操作器
from operators.alignment_operators import SMARTALIGNPRO_OT_two_point_align
from ui.main_panel import SMARTALIGNPRO_PT_main_panel
```

### 用戶
- 使用 `smart_align_pro_modular.py` 作為插件入口
- 所有原有功能保持不變
- 新增模組化架構的優勢

## 🔄 版本對應

| 功能 | 原版本 | 模組版本 |
|------|--------|----------|
| 兩點對齊 | ✅ | ✅ |
| 三點對齊 | ✅ | ✅ |
| 表面法線對齊 | ✅ | ✅ |
| 接觸對齊 | ✅ | ✅ |
| 預覽系統 | ✅ | ✅ |
| 智能檢測 | ✅ | ✅ |
| UI面板 | ✅ | ✅ |
| 快捷鍵 | ✅ | ✅ |

## 🛠️ 開發指南

### 添加新功能
1. **核心算法**: 在 `core/` 中添加
2. **操作器**: 在 `operators/` 中添加
3. **UI界面**: 在 `ui/` 中添加
4. **工具函數**: 在 `utils/` 中添加

### 修改現有功能
1. 找到對應模組
2. 修改相關文件
3. 更新測試（如有）
4. 更新文檔

### 測試
```python
# 測試核心算法
from core.alignment import two_point_align
# ... 測試代碼

# 測試操作器
bpy.ops.smartalignpro.two_point_align()
# ... 測試代碼
```

## 📈 性能優化

- **延遲導入**: 按需導入模組
- **快取機制**: 重複計算結果快取
- **內存管理**: 及時清理預覽數據

## 🔧 故障排除

### 常見問題
1. **導入錯誤**: 檢查模組路徑
2. **版本不兼容**: 確認 Blender 版本
3. **功能缺失**: 檢查模組是否正確註冊

### 調試技巧
```python
# 檢查模組導入
import core
print(dir(core))

# 檢查操作器註冊
print(bpy.ops.smartalignpro)

# 檢查設置屬性
print(bpy.context.scene.smartalignpro_settings)
```

## 🎯 未來計劃

- [ ] 完善單元測試
- [ ] 添加更多工具模組
- [ ] 優化性能和內存使用
- [ ] 支持插件生態系統

---

**注意**: 模組化版本與原版本功能完全兼容，可以安全切換使用。
