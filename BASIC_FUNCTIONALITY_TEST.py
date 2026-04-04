"""
Smart Align Pro - 基礎功能測試
用於驗證核心功能是否正常工作
"""

import bpy
import math
from mathutils import Vector

def create_test_scene():
    """創建測試場景"""
    # 清除現有物件
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    
    # 創建測試物件
    # 目標物件 (較大的 Box)
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    target = bpy.context.active_object
    target.name = "Target_Box"
    
    # 來源物件1 (較小的 Box)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(3, 3, 2))
    source1 = bpy.context.active_object
    source1.name = "Source_Box_1"
    
    # 來源物件2 (不同位置的 Box)
    bpy.ops.mesh.primitive_cube_add(size=0.8, location=(-2, 4, 1))
    source2 = bpy.context.active_object
    source2.name = "Source_Box_2"
    
    # 清除選擇
    bpy.ops.object.select_all(action='DESELECT')
    
    return target, source1, source2

def test_basic_functionality():
    """測試基礎功能"""
    print("=" * 50)
    print("Smart Align Pro 基礎功能測試")
    print("=" * 50)
    
    # 創建測試場景
    target, source1, source2 = create_test_scene()
    
    # 設置測試參數
    settings = bpy.context.scene.smartalignpro_settings
    
    # 測試 1: 兩點對齊
    print("\n🧪 測試 1: 兩點對齊")
    try:
        # 選擇物件
        bpy.context.view_layer.objects.active = target
        target.select_set(True)
        source1.select_set(True)
        
        # 設置點位
        settings.two_point_source_a = "0"
        settings.two_point_source_b = "1"
        settings.two_point_target_a = "0"
        settings.two_point_target_b = "1"
        
        # 執行兩點對齊
        bpy.ops.smartalignpro.two_point_align()
        
        # 檢查結果
        source1_pos = source1.location
        target_pos = target.location
        distance = (source1_pos - target_pos).length
        
        print(f"✅ 兩點對齊成功: {source1.name} 位置 {source1_pos}")
        print(f"   與目標距離: {distance:.3f}")
        
    except Exception as e:
        print(f"❌ 兩點對齊失敗: {str(e)}")
    
    # 重置場景
    bpy.ops.object.select_all(action='DESELECT')
    target, source1, source2 = create_test_scene()
    
    # 測試 2: 三點對齊
    print("\n🧪 測試 2: 三點對齊")
    try:
        # 選擇物件
        bpy.context.view_layer.objects.active = target
        target.select_set(True)
        source2.select_set(True)
        
        # 設置點位
        settings.three_point_source_a = "0"
        settings.three_point_source_b = "1"
        settings.three_point_source_c = "3"
        settings.three_point_target_a = "0"
        settings.three_point_target_b = "1"
        settings.three_point_target_c = "3"
        
        # 設置三點對齊選項
        settings.three_point_flip_target_normal = False
        settings.three_point_apply_offset = True
        settings.collision_safe_mode = True
        settings.small_offset = 0.01
        
        # 執行三點對齊
        bpy.ops.smartalignpro.three_point_align()
        
        # 檢查結果
        source2_pos = source2.location
        target_pos = target.location
        distance = (source2_pos - target_pos).length
        
        print(f"✅ 三點對齊成功: {source2.name} 位置 {source2_pos}")
        print(f"   與目標距離: {distance:.3f}")
        
    except Exception as e:
        print(f"❌ 三點對齊失敗: {str(e)}")
    
    # 重置場景
    bpy.ops.object.select_all(action='DESELECT')
    target, source1, source2 = create_test_scene()
    
    # 測試 3: 表面法線對齊
    print("\n🧪 測試 3: 表面法線對齊")
    try:
        # 選擇物件
        bpy.context.view_layer.objects.active = target
        target.select_set(True)
        source1.select_set(True)
        
        # 設置對齊軸向
        settings.normal_align_axis = "POS_Z"
        
        # 執行表面法線對齊
        bpy.ops.smartalignpro.surface_normal_align()
        
        # 檢查結果
        source1_pos = source1.location
        target_pos = target.location
        distance = (source1_pos - target_pos).length
        
        print(f"✅ 表面法線對齊成功: {source1.name} 位置 {source1_pos}")
        print(f"   與目標距離: {distance:.3f}")
        
    except Exception as e:
        print(f"❌ 表面法線對齊失敗: {str(e)}")
    
    # 重置場景
    bpy.ops.object.select_all(action='DESELECT')
    target, source1, source2 = create_test_scene()
    
    # 測試 4: 接觸對齊
    print("\n🧪 測試 4: 接觸對齊")
    try:
        # 選擇物件
        bpy.context.view_layer.objects.active = target
        target.select_set(True)
        source2.select_set(True)
        
        # 執行接觸對齊
        bpy.ops.smartalignpro.auto_contact_align()
        
        # 檢查結果
        source2_pos = source2.location
        target_pos = target.location
        distance = (source2_pos - target_pos).length
        
        print(f"✅ 接觸對齊成功: {source2.name} 位置 {source2_pos}")
        print(f"   與目標距離: {distance:.3f}")
        
    except Exception as e:
        print(f"❌ 接觸對齊失敗: {str(e)}")
    
    # 測試 5: 預覽系統
    print("\n🧪 測試 5: 預覽系統")
    try:
        # 選擇物件
        bpy.context.view_layer.objects.active = target
        target.select_set(True)
        source1.select_set(True)
        
        # 創建預覽
        bpy.ops.smartalignpro.preview_align()
        
        # 檢查預覽物件
        preview_objects = [obj for obj in bpy.context.scene.objects if "Preview" in obj.name]
        
        if preview_objects:
            print(f"✅ 預覽創建成功: 找到 {len(preview_objects)} 個預覽物件")
            
            # 應用預覽
            bpy.ops.smartalignpro.apply_preview()
            print("✅ 預覽應用成功")
            
            # 清除預覽
            bpy.ops.smartalignpro.clear_preview()
            print("✅ 預覽清除成功")
        else:
            print("❌ 預覽創建失敗: 未找到預覽物件")
        
    except Exception as e:
        print(f"❌ 預覽系統失敗: {str(e)}")
    
    print("\n" + "=" * 50)
    print("基礎功能測試完成")
    print("=" * 50)

def test_cad_functionality():
    """測試 CAD 功能"""
    print("\n🧪 測試 6: CAD 吸附模式")
    try:
        # 創建測試場景
        target, source1, source2 = create_test_scene()
        
        # 選擇物件
        bpy.context.view_layer.objects.active = target
        target.select_set(True)
        source1.select_set(True)
        
        # 設置 CAD 參數
        settings = bpy.context.scene.smartalignpro_settings
        settings.cad_snap_tolerance = 0.1
        settings.cad_constraint_axis = "NONE"
        settings.cad_alignment_type = "TWO_POINT"
        
        print("✅ CAD 模式參數設置成功")
        print(f"   吸附容差: {settings.cad_snap_tolerance}")
        print(f"   約束軸: {settings.cad_constraint_axis}")
        print(f"   對齊類型: {settings.cad_alignment_type}")
        
        # 注意: CAD modal 模式需要手動測試
        print("📝 CAD modal 模式需要手動測試")
        print("   請在 Blender 中手動測試 CAD 吸附模式")
        
    except Exception as e:
        print(f"❌ CAD 功能測試失敗: {str(e)}")

def run_all_tests():
    """運行所有測試"""
    try:
        test_basic_functionality()
        test_cad_functionality()
        
        print("\n🎯 測試總結:")
        print("✅ 基礎功能測試完成")
        print("✅ CAD 功能參數測試完成")
        print("📝 請在 Blender 中手動測試 CAD modal 模式")
        
    except Exception as e:
        print(f"❌ 測試運行失敗: {str(e)}")

# 測試入口
if __name__ == "__main__":
    run_all_tests()
