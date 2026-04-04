"""
Smart Align Pro - 設置模組
包含所有插件的設置屬性
"""

import bpy
from bpy.props import (
    BoolProperty,
    FloatProperty,
    PointerProperty,
    EnumProperty,
    StringProperty,
    IntProperty,
)

# 工作流程模式選項
WORKFLOW_MODE_ITEMS = [
    ("BEGINNER", "初學者", "簡化界面，專注基本功能"),
    ("ARCHITECTURAL", "建築", "建築工作流程優化"),
    ("MECHANICAL", "機械", "機械工程工作流程優化"),
    ("PROFESSIONAL", "專業", "完整功能，專業用戶"),
]

# 物件類型選項
OBJECT_TYPE_ITEMS = [
    ("AUTO", "自動", "自動檢測物件類型"),
    ("BUILDING", "建築", "建築物件"),
    ("MECHANICAL", "機械", "機械零件"),
    ("GAME", "遊戲", "遊戲物件"),
    ("PROP", "道具", "一般道具"),
]

# 對齊策略選項
ALIGNMENT_STRATEGY_ITEMS = [
    ("AUTO", "自動", "自動選擇最佳策略"),
    ("TWO_POINT", "兩點對齊", "使用兩點對齊"),
    ("THREE_POINT", "三點對齊", "使用三點對齊"),
    ("SURFACE_NORMAL", "表面法線", "使用表面法線對齊"),
    ("AUTO_CONTACT", "接觸對齊", "使用智慧接觸對齊"),
]

# 對齊軸選項
ALIGN_AXIS_ITEMS = [
    ("POS_X", "+X（物件右方向外）", "將物件 +X 對齊表面法線"),
    ("NEG_X", "-X（物件左方向外）", "將物件 -X 對齊表面法線"),
    ("POS_Y", "+Y（物件前方向外）", "將物件 +Y 對齊表面法線"),
    ("NEG_Y", "-Y（物件後方向外）", "將物件 -Y 對齊表面法線"),
    ("POS_Z", "+Z（物件上方向外）", "將物件 +Z 對齊表面法線"),
    ("NEG_Z", "-Z（物件下方向外）", "將物件 -Z 對齊表面法線"),
]

# 邊界框點位選項
BBOX_POINT_ITEMS = [
    ("0", "點 0 (MIN)", "邊界框最小角點"),
    ("1", "點 1", "邊界框左下前"),
    ("2", "點 2", "邊界框左下後"),
    ("3", "點 3", "邊界框左上前"),
    ("4", "點 4", "邊界框右下前"),
    ("5", "點 5", "邊界框右下後"),
    ("6", "點 6", "邊界框右上後"),
    ("7", "點 7 (MAX)", "邊界框最大角點"),
]


class SMARTALIGNPRO_PG_settings(bpy.types.PropertyGroup):
    """Smart Align Pro 設置屬性組"""
    
    # 工作流程設置
    workflow_mode: EnumProperty(
        name="工作流程模式",
        description="選擇適合的工作流程模式",
        items=WORKFLOW_MODE_ITEMS,
        default="BEGINNER",
    )
    
    # 智能檢測設置
    smart_object_detection: BoolProperty(
        name="智能物件識別",
        description="自動識別物件類型並選擇最佳對齊策略",
        default=True,
    )
    
    object_type_filter: EnumProperty(
        name="物件類型篩選",
        description="只對特定類型的物件進行對齊",
        items=OBJECT_TYPE_ITEMS,
        default="AUTO",
    )
    
    alignment_strategy: EnumProperty(
        name="對齊策略",
        description="選擇對齊策略",
        items=ALIGNMENT_STRATEGY_ITEMS,
        default="AUTO",
    )
    
    # 兩點對齊設置
    two_point_source_a: EnumProperty(
        name="來源點 A",
        description="來源物件 Bounding Box 參考點 A",
        items=BBOX_POINT_ITEMS,
        default="0",
    )
    
    two_point_source_b: EnumProperty(
        name="來源點 B",
        description="來源物件 Bounding Box 參考點 B",
        items=BBOX_POINT_ITEMS,
        default="1",
    )
    
    two_point_target_a: EnumProperty(
        name="目標點 A",
        description="目標物件 Bounding Box 參考點 A",
        items=BBOX_POINT_ITEMS,
        default="0",
    )
    
    two_point_target_b: EnumProperty(
        name="目標點 B",
        description="目標物件 Bounding Box 參考點 B",
        items=BBOX_POINT_ITEMS,
        default="1",
    )
    
    # 三點對齊設置
    three_point_source_a: EnumProperty(
        name="來源點 A",
        description="來源物件 Bounding Box 參考點 A",
        items=BBOX_POINT_ITEMS,
        default="0",
    )
    
    three_point_source_b: EnumProperty(
        name="來源點 B",
        description="來源物件 Bounding Box 參考點 B",
        items=BBOX_POINT_ITEMS,
        default="1",
    )
    
    three_point_source_c: EnumProperty(
        name="來源點 C",
        description="來源物件 Bounding Box 參考點 C",
        items=BBOX_POINT_ITEMS,
        default="3",
    )
    
    three_point_target_a: EnumProperty(
        name="目標點 A",
        description="目標物件 Bounding Box 參考點 A",
        items=BBOX_POINT_ITEMS,
        default="0",
    )
    
    three_point_target_b: EnumProperty(
        name="目標點 B",
        description="目標物件 Bounding Box 參考點 B",
        items=BBOX_POINT_ITEMS,
        default="1",
    )
    
    three_point_target_c: EnumProperty(
        name="目標點 C",
        description="目標物件 Bounding Box 參考點 C",
        items=BBOX_POINT_ITEMS,
        default="3",
    )
    
    three_point_flip_target_normal: BoolProperty(
        name="三點對齊翻面",
        description="將目標平面法線反向，修正上下顛倒或背面朝外的情況",
        default=False,
    )
    
    three_point_apply_offset: BoolProperty(
        name="三點對齊套用微小間距",
        description="對齊完成後，沿目標平面法線推開一點，避免重疊與閃爍",
        default=True,
    )
    
    # 表面法線對齊設置
    normal_align_axis: EnumProperty(
        name="法線對齊軸",
        description="指定物件哪個局部軸要朝向表面法線",
        items=ALIGN_AXIS_ITEMS,
        default="POS_Z",
    )
    
    normal_align_move_to_hit: BoolProperty(
        name="移動到表面命中點",
        description="表面法線對齊後，將物件推到目標表面",
        default=True,
    )
    
    # 通用設置
    collision_safe_mode: BoolProperty(
        name="安全貼齊模式",
        description="保留微小偏移，降低穿模風險",
        default=True,
    )
    
    small_offset: FloatProperty(
        name="微小間距",
        description="避免重疊與閃爍",
        default=0.001,
        min=0.0,
        soft_max=0.1,
        precision=4,
    )
    
    keep_xy_position: BoolProperty(
        name="保持 XY 位置",
        description="貼地時只調整 Z 軸，不改變 XY",
        default=True,
    )
    
    center_on_target: BoolProperty(
        name="對齊目標中心",
        description="貼齊時將來源物件對齊到目標物件中心",
        default=False,
    )
    
    # 預覽系統設置
    preview_mode: BoolProperty(
        name="預覽模式",
        description="在執行前預覽對齊結果",
        default=True,
    )
    
    auto_update_preview: BoolProperty(
        name="自動更新預覽",
        description="參數變更時自動更新預覽",
        default=False,
    )
    
    # UI 設置
    ui_show_advanced: BoolProperty(
        name="顯示進階選項",
        description="顯示進階對齊選項",
        default=False,
    )
    
    ui_show_cad_tools: BoolProperty(
        name="顯示 CAD 工具",
        description="顯示 CAD / 吸附工具區塊",
        default=False,
    )
    
    ui_show_preview: BoolProperty(
        name="顯示預覽功能",
        description="顯示預覽與其他功能區塊",
        default=False,
    )
    
    ui_show_info: BoolProperty(
        name="顯示資訊",
        description="顯示快捷鍵與資訊區塊",
        default=False,
    )
    
    ui_show_tooltips: BoolProperty(
        name="顯示工具提示",
        description="在UI中顯示詳細的工具提示",
        default=True,
    )
    
    ui_compact_mode: BoolProperty(
        name="緊湊模式",
        description="使用更緊湊的UI佈局",
        default=False,
    )
    
    ui_auto_collapse: BoolProperty(
        name="自動折疊",
        description="自動折疊不常用的面板",
        default=False,
    )
    
    # 調試設置
    debug_mode: BoolProperty(
        name="調試模式",
        description="啟用調試輸出",
        default=False,
    )
    
    # 顯示設置
    show_bbox_point_overlay: BoolProperty(
        name="顯示 BBox 點編號",
        description="在 3D 視圖中顯示 Bounding Box 八個點的編號",
        default=False,
    )
    
    show_analysis_info: BoolProperty(
        name="顯示分析信息",
        description="在面板中顯示場景分析信息",
        default=True,
    )
    
    # 批量處理設置
    batch_mode: BoolProperty(
        name="批量模式",
        description="啟用批量處理模式",
        default=False,
    )
    
    auto_save_state: BoolProperty(
        name="自動保存狀態",
        description="對齊前自動保存物件狀態",
        default=True,
    )
    
    # 測量設置
    measurement_unit: EnumProperty(
        name="測量單位",
        description="選擇測量單位",
        items=[
            ("METRIC", "公制", "使用公制單位"),
            ("IMPERIAL", "英制", "使用英制單位"),
            ("BLENDER", "Blender", "使用 Blender 單位"),
        ],
        default="BLENDER",
    )
    
    measurement_precision: IntProperty(
        name="測量精度",
        description="測量值的小數位數",
        default=3,
        min=0,
        max=6,
    )
    
    # 動畫設置
    animation_keyframe: BoolProperty(
        name="插入關鍵幀",
        description="對齊時自動插入關鍵幀",
        default=False,
    )
    
    animation_interpolation: EnumProperty(
        name="插值模式",
        description="關鍵幀插值模式",
        items=[
            ("LINEAR", "線性", "線性插值"),
            ("BEZIER", "貝茲", "貝茲插值"),
            ("CONSTANT", "常數", "常數插值"),
        ],
        default="LINEAR",
    )
    
    # CAD 設置
    cad_snap_tolerance: FloatProperty(
        name="CAD 吸附容差",
        description="CAD 吸附檢測容差",
        default=0.1,
        min=0.01,
        max=1.0,
        precision=3,
    )
    
    cad_show_snap_preview: BoolProperty(
        name="顯示 CAD 吸附預覽",
        description="顯示 CAD 吸附點預覽",
        default=True,
    )
    
    cad_constraint_axis: EnumProperty(
        name="CAD 約束軸",
        description="CAD 吸附約束軸",
        items=[
            ("NONE", "無約束", "自由移動"),
            ("X", "X 軸", "約束到 X 軸"),
            ("Y", "Y 軸", "約束到 Y 軸"),
            ("Z", "Z 軸", "約束到 Z 軸"),
        ],
        default="NONE",
    )
    
    cad_alignment_type: EnumProperty(
        name="CAD 對齊類型",
        description="CAD 對齊方式",
        items=[
            ("TWO_POINT", "兩點對齊", "使用兩點對齊"),
            ("THREE_POINT", "三點對齊", "使用三點對齊"),
            ("SURFACE_NORMAL", "表面法線", "表面法線對齊"),
            ("PARALLEL", "平行對齊", "平行對齊"),
            ("PERPENDICULAR", "垂直對齊", "垂直對齊"),
        ],
        default="TWO_POINT",
    )
    
    cad_snap_modes: bpy.props.BoolVectorProperty(
        name="CAD 吸附模式",
        description="啟用的 CAD 吸附模式",
        size=8,
        default=(True, True, True, True, True, True, False, False),
        subtype="LAYER"
    )
    
    cad_show_helper_lines: BoolProperty(
        name="顯示輔助線",
        description="顯示 CAD 對齊輔助線",
        default=True,
    )
    
    cad_snap_strength: FloatProperty(
        name="吸附強度",
        description="吸附的強度（影響吸附範圍）",
        default=1.0,
        min=0.1,
        max=2.0,
        precision=2,
    )
    
    # 多物件對齊設置
    multi_object_alignment_mode: EnumProperty(
        name="多物件對齊模式",
        description="多物件對齊模式",
        items=[
            ("SINGLE_TO_TARGET", "單物件到目標", "每個物件單獨對齊到目標"),
            ("MULTIPLE_TO_TARGET", "多物件到目標", "所有物件整體對齊到目標"),
            ("GROUP_TO_TARGET", "群組到目標", "將群組整體對齊到目標"),
            ("CHAIN_ALIGNMENT", "鏈式對齊", "A→B→C→... 鏈式對齊"),
            ("CIRCULAR_ALIGNMENT", "圓形排列", "圍繞目標圓形排列"),
            ("ARRAY_ALIGNMENT", "線性陣列", "線性陣列排列"),
        ],
        default="MULTIPLE_TO_TARGET",
    )
    
    multi_object_alignment_strategy: EnumProperty(
        name="對齊策略",
        description="智慧對齊策略選擇",
        items=[
            ("PRECISION", "精確對齊", "使用精確的點位對齊，適合精密模型"),
            ("SURFACE", "表面對齊", "基於表面法線的對齊，適合建築模型"),
            ("QUICK", "快速對齊", "快速近似對齊，適合概念設計"),
            ("GROUND", "貼地對齊", "將物件對齊到地面，適合場景佈局"),
            ("AUTO", "自動判斷", "根據物件類型自動選擇最佳策略"),
        ],
        default="AUTO",
    )
    
    multi_object_alignment_type: EnumProperty(
        name="多物件對齊類型",
        description="多物件對齊方式",
        items=[
            ("TWO_POINT", "兩點對齊", "使用兩點對齊"),
            ("THREE_POINT", "三點對齊", "使用三點對齊"),
            ("SURFACE_NORMAL", "表面法線", "表面法線對齊"),
            ("CENTER", "中心對齊", "中心點對齊"),
        ],
        default="CENTER",
    )
    
    array_spacing: FloatProperty(
        name="陣列間距",
        description="陣列物件間的間距",
        default=2.0,
        min=0.1,
        max=10.0,
    )
    
    circular_radius: FloatProperty(
        name="圓形半徑",
        description="圓形排列的半徑",
        default=3.0,
        min=0.5,
        max=20.0,
    )
    
    # 支點對齊設置
    pivot_type: EnumProperty(
        name="支點類型",
        description="對齊支點類型",
        items=[
            ("VERTEX", "頂點支點", "使用頂點作為支點"),
            ("EDGE", "邊緣支點", "使用邊緣作為支點"),
            ("FACE", "面支點", "使用面作為支點"),
            ("CENTER", "中心支點", "使用物件中心作為支點"),
            ("CUSTOM", "自定義支點", "使用自定義位置作為支點"),
        ],
        default="CENTER",
    )
    
    pivot_index: IntProperty(
        name="支點索引",
        description="頂點/邊緣/面的索引",
        default=0,
        min=0,
    )
    
    custom_pivot: bpy.props.FloatVectorProperty(
        name="自定義支點",
        description="自定義支點位置",
        default=(0.0, 0.0, 0.0),
    )
    
    # 向量約束設置
    vector_constraint_type: EnumProperty(
        name="向量約束類型",
        description="向量約束類型",
        items=[
            ("AXIS", "軸向約束", "約束到指定軸向"),
            ("PLANE", "平面約束", "約束到指定平面"),
            ("VECTOR", "向量約束", "約束到自定義向量"),
            ("NORMAL", "法線約束", "約束到表面法線"),
            ("CAMERA", "相機約束", "約束到相機方向"),
        ],
        default="AXIS",
    )
    
    vector_constraint_axis: EnumProperty(
        name="約束軸",
        description="約束軸向",
        items=[
            ("X", "X 軸", "約束到 X 軸"),
            ("Y", "Y 軸", "約束到 Y 軸"),
            ("Z", "Z 軸", "約束到 Z 軸"),
            ("-X", "-X 軸", "約束到 -X 軸"),
            ("-Y", "-Y 軸", "約束到 -Y 軸"),
            ("-Z", "-Z 軸", "約束到 -Z 軸"),
        ],
        default="X",
    )
    
    custom_constraint_vector: bpy.props.FloatVectorProperty(
        name="自定義向量",
        description="自定義約束向量",
        default=(1.0, 0.0, 0.0),
    )
    
    # 拓撲對齊設置 - 超越 CAD Transform
    snap_user_preference: EnumProperty(
        name="吸附偏好",
        description="用戶吸附偏好設置",
        items=[
            ("BALANCED", "平衡", "平衡的吸附優先級"),
            ("VERTEX_FIRST", "頂點優先", "優先吸附到頂點"),
            ("EDGE_FIRST", "邊緣優先", "優先吸附到邊緣"),
            ("FACE_FIRST", "面優先", "優先吸附到面"),
            ("PRECISION", "精確模式", "高精度吸附模式"),
            ("SPEED", "速度模式", "快速吸附模式"),
        ],
        default="BALANCED",
    )
    
    topology_snap_tolerance: FloatProperty(
        name="拓撲吸附容差",
        description="拓撲吸附的容差距離",
        default=0.01,
        min=0.001,
        max=0.1,
        precision=4,
    )
    
    topology_show_priority_stack: BoolProperty(
        name="顯示優先級堆棧",
        description="顯示吸附點的優先級堆棧信息",
        default=True,
    )
    
    topology_enable_realtime_preview: BoolProperty(
        name="啟用即時預覽",
        description="啟用拓撲對齊的即時預覽",
        default=True,
    )
    
    # 交互式吸附設置 - CAD Transform 靈魂
    interactive_snap_tolerance: FloatProperty(
        name="交互式吸附容差",
        description="交互式吸附的容差距離",
        default=0.01,
        min=0.001,
        max=0.1,
        precision=4,
    )
    
    interactive_snap_show_ghost: BoolProperty(
        name="顯示 Ghost 預覽",
        description="顯示交互式吸附的 Ghost 預覽",
        default=True,
    )
    
    interactive_snap_constraint_feedback: BoolProperty(
        name="約束反饋",
        description="顯示約束系統的視覺反饋",
        default=True,
    )
    
    # 約束平面系統設置
    constraint_plane_system_enabled: BoolProperty(
        name="啟用約束平面系統",
        description="啟用 CAD Transform 級別的約束平面系統",
        default=True,
    )
    
    constraint_plane_show_visual: BoolProperty(
        name="顯示約束平面",
        description="顯示約束平面的視覺化",
        default=True,
    )
    
    constraint_reference_system: EnumProperty(
        name="約束參考系統",
        description="約束系統的參考坐標系",
        items=[
            ("WORLD", "世界坐標", "使用世界坐標系"),
            ("LOCAL", "本地坐標", "使用物件本地坐標系"),
            ("CUSTOM", "自定義坐標", "使用自定義坐標系"),
            ("VIEW", "視圖坐標", "使用視圖坐標系"),
        ],
        default="WORLD",
    )
    
    # 吸附系統設置（從 utils/settings.py 合併）
    snap_tolerance: FloatProperty(
        name="吸附容差",
        description="吸附點的螢幕距離容差（像素）",
        default=20.0,
        min=5.0,
        max=50.0,
        step=1.0
    )
    
    sticky_radius: FloatProperty(
        name="黏著半徑",
        description="滑鼠脫附的距離閾值（像素）",
        default=18.0,
        min=10.0,
        max=30.0,
        step=1.0
    )
    
    hysteresis_factor: FloatProperty(
        name="遲滯因子",
        description="新目標需要比當前目標好的百分比",
        default=1.15,
        min=1.0,
        max=1.5,
        step=0.05
    )
    
    release_threshold: FloatProperty(
        name="釋放閾值",
        description="累積移動距離達到此值時釋放（像素）",
        default=20.0,
        min=10.0,
        max=50.0,
        step=1.0
    )
    
    preview_opacity: FloatProperty(
        name="預覽透明度",
        description="預覽物件的透明度",
        default=0.7,
        min=0.3,
        max=1.0,
        step=0.1
    )
    
    show_preview: BoolProperty(
        name="顯示預覽",
        description="在選擇過程中顯示即時預覽",
        default=True
    )
    
    hud_position: EnumProperty(
        name="HUD 位置",
        description="HUD 在螢幕上的位置",
        items=[
            ("TOP_LEFT", "左上角", ""),
            ("TOP_RIGHT", "右上角", ""),
            ("BOTTOM_LEFT", "左下角", ""),
            ("BOTTOM_RIGHT", "右下角", ""),
        ],
        default="TOP_LEFT"
    )
    
    default_constraint: EnumProperty(
        name="預設約束",
        description="新對齊操作的預設約束模式",
        items=[
            ("NONE", "無約束", "自由對齊"),
            ("TRANSLATE_ONLY", "僅平移", "只進行平移"),
            ("ROTATE_ONLY", "僅旋轉", "只進行旋轉"),
            ("AXIS_LOCK_X", "鎖定 X 軸", "約束到 X 軸"),
            ("AXIS_LOCK_Y", "鎖定 Y 軸", "約束到 Y 軸"),
            ("AXIS_LOCK_Z", "鎖定 Z 軸", "約束到 Z 軸"),
        ],
        default="NONE"
    )
    
    enable_hysteresis: BoolProperty(
        name="啟用遲滯",
        description="啟用吸附點切換的遲滯效果",
        default=True
    )
    
    enable_sticky_release: BoolProperty(
        name="啟用黏著釋放",
        description="啟用滑鼠黏著釋放機制",
        default=True
    )
    
    outside_tolerance: FloatProperty(
        name="外部容忍",
        description="外部空區的容忍距離（毫米）",
        default=0.1,
        min=0.05,
        max=0.5,
        step=0.05
    )
    
    show_snap_candidates: BoolProperty(
        name="顯示候選點",
        description="顯示所有可能的吸附候選點",
        default=False
    )
    
    show_hud: BoolProperty(
        name="顯示 HUD",
        description="顯示操作提示和狀態信息",
        default=True
    )
    
    offset_distance: FloatProperty(
        name="表面偏移",
        description="表面對齊時沿法線保留的偏移距離",
        default=0.0,
        min=-1.0,
        max=1.0,
        step=0.01
    )


# 注意：此檔案只定義 SMARTALIGNPRO_PG_settings 類別
# 註冊和註銷由 smart_align_pro_modular.py 統一管理
