"""
Smart Align Pro - 回歸測試場景
用於驗證核心對齊功能的穩定性

使用方式：
1. 在 Blender 中開啟 Python Console
2. 執行：exec(open("/path/to/REGRESSION_TEST_SCENE.py").read())
3. 或在 Text Editor 中開啟並執行
"""

import bpy
import math
from mathutils import Vector


def clear_scene():
    """清除所有物件"""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # 清除所有 mesh (如果有的話)
    for item in bpy.data.meshes:
        bpy.data.meshes.remove(item)
    for item in bpy.data.materials:
        bpy.data.materials.remove(item)


def create_test_scene():
    """建立回歸測試場景"""
    clear_scene()
    
    # 建立來源物件 (Source Cube)
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    source = bpy.context.active_object
    source.name = "Test_Source_Cube"
    source.scale = (1, 2, 0.5)  # 非均勻縮放
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # 建立目標物件 (Target Cube)
    bpy.ops.mesh.primitive_cube_add(size=2, location=(5, 3, 2))
    target = bpy.context.active_object
    target.name = "Test_Target_Cube"
    target.rotation_euler = (0, math.radians(45), math.radians(30))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # 建立傾斜目標平面 (用於表面法線測試)
    bpy.ops.mesh.primitive_plane_add(size=4, location=(5, -3, 1))
    angled_target = bpy.context.active_object
    angled_target.name = "Test_Angled_Plane"
    angled_target.rotation_euler = (math.radians(60), 0, math.radians(15))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # 建立地面 (用於貼地測試)
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, -2))
    ground = bpy.context.active_object
    ground.name = "Test_Ground"
    
    # 選取設定
    target.select_set(True)
    source.select_set(True)
    bpy.context.view_layer.objects.active = target
    
    print("[SmartAlignPro][TEST] 回歸測試場景已建立")
    print(f"[SmartAlignPro][TEST] 來源物件: {source.name}")
    print(f"[SmartAlignPro][TEST] 目標物件: {target.name}")
    print(f"[SmartAlignPro][TEST] 傾斜目標: {angled_target.name}")
    print(f"[SmartAlignPro][TEST] 地面: {ground.name}")
    
    return {
        'source': source,
        'target': target,
        'angled_target': angled_target,
        'ground': ground
    }


def verify_bbox_center():
    """驗證邊界框中心計算"""
    from utils.bbox_utils import get_bbox_center_world
    
    source = bpy.data.objects.get("Test_Source_Cube")
    if not source:
        print("[SmartAlignPro][TEST][FAIL] 找不到 Test_Source_Cube")
        return False
    
    # 計算邊界框中心
    bbox_center = get_bbox_center_world(source)
    
    # 驗證結果
    expected_center = source.matrix_world @ Vector((0, 0, 0))  # 原點在局部空間
    
    if abs((bbox_center - expected_center).length) < 0.001:
        print(f"[SmartAlignPro][TEST][PASS] 邊界框中心計算正確: {bbox_center}")
        return True
    else:
        print(f"[SmartAlignPro][TEST][FAIL] 邊界框中心計算錯誤")
        print(f"  計算值: {bbox_center}")
        print(f"  預期值: {expected_center}")
        return False


def verify_settings_integration():
    """驗證設定系統整合"""
    try:
        settings = bpy.context.scene.smartalignpro_settings
        
        # 檢查必要屬性是否存在
        required_attrs = [
            'two_point_source_a', 'two_point_source_b',
            'two_point_target_a', 'two_point_target_b',
            'ui_show_cad_tools', 'debug_mode',
            'snap_tolerance', 'sticky_radius',  # 從 utils/settings 合併過來的
            'workflow_mode', 'alignment_strategy',
            'normal_align_axis', 'normal_align_move_to_hit',
        ]
        
        missing = []
        for attr in required_attrs:
            if not hasattr(settings, attr):
                missing.append(attr)
        
        if missing:
            print(f"[SmartAlignPro][TEST][FAIL] 設定屬性缺失: {missing}")
            return False
        
        print(f"[SmartAlignPro][TEST][PASS] 設定系統整合正確")
        return True
        
    except Exception as e:
        print(f"[SmartAlignPro][TEST][FAIL] 設定系統錯誤: {e}")
        return False


def run_regression_tests():
    """執行回歸測試"""
    print("[SmartAlignPro][TEST] === 開始回歸測試 ===")
    
    # 建立測試場景
    objects = create_test_scene()
    
    # 執行驗證
    results = []
    
    print("\n[SmartAlignPro][TEST] --- 測試 1: 邊界框中心計算 ---")
    results.append(("bbox_center", verify_bbox_center()))
    
    print("\n[SmartAlignPro][TEST] --- 測試 2: 設定系統整合 ---")
    results.append(("settings_integration", verify_settings_integration()))
    
    # 總結
    print("\n[SmartAlignPro][TEST] === 回歸測試結果 ===")
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"[SmartAlignPro][TEST] 通過: {passed}/{total}")
    
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")
    
    return passed == total


if __name__ == "__main__":
    run_regression_tests()
