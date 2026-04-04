"""
Smart Align Pro - 工具操作器模組
包含各種輔助工具操作器
"""

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, StringProperty, FloatProperty, IntProperty
from ..core.detection import analyze_scene_objects, detect_object_type
from ..utils.bbox_utils import get_bbox_point_info, analyze_bbox_relationship, get_bbox_center_world


class SMARTALIGNPRO_OT_analyze_scene(Operator):
    """場景分析操作器"""
    bl_idname = "smartalignpro.analyze_scene"
    bl_label = "分析場景"
    bl_description = "分析場景中的物件並提供建議"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            analysis = analyze_scene_objects(context)
            
            # 生成分析報告
            report_lines = [
                f"場景分析完成",
                f"總物件數: {analysis['total_objects']}",
                f"",
                "物件類型分布:",
            ]
            
            for obj_type, count in analysis['object_types'].items():
                report_lines.append(f"  {obj_type}: {count} 個")
            
            report_lines.extend([
                f"",
                "建議策略分布:",
            ])
            
            for strategy, count in analysis['suggested_strategies'].items():
                report_lines.append(f"  {strategy}: {count} 個")
            
            # 顯示詳細分析結果
            if context.scene.smartalignpro_settings.show_analysis_info:
                report_lines.extend([
                    f"",
                    "詳細分析:",
                ])
                
                for detail in analysis['detection_details']:
                    report_lines.append(
                        f"  {detail['object']}: {detail['type']} "
                        f"(信心度: {detail['confidence']:.2f})"
                    )
            
            # 在控制台輸出完整報告
            print("[SmartAlignPro] 場景分析報告:")
            for line in report_lines:
                print(line)
            
            # 顯示簡要信息
            self.report({"INFO"}, f"分析完成：{analysis['total_objects']} 個物件")
            
            # 將結果存儲到場景屬性中供UI使用
            context.scene.smartalignpro_analysis = analysis
            
            return {"FINISHED"}
            
        except Exception as e:
            self.report({"ERROR"}, f"場景分析失敗: {str(e)}")
            return {"CANCELLED"}


class SMARTALIGNPRO_OT_measure_distance(Operator):
    """測量距離操作器"""
    bl_idname = "smartalignpro.measure_distance"
    bl_label = "測量距離"
    bl_description = "測量兩個物件之間的距離"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        
        if len(selected) != 2:
            self.report({"WARNING"}, "請選取剛好兩個 Mesh 物件")
            return {"CANCELLED"}
        
        obj1, obj2 = selected
        
        # 計算中心點距離
        center1 = get_bbox_center_world(obj1)
        center2 = get_bbox_center_world(obj2)
        distance = (center2 - center1).length
        
        # 分析邊界框關係
        bbox_analysis = analyze_bbox_relationship(obj1, obj2)
        
        # 生成測量報告
        settings = context.scene.smartalignpro_settings
        precision = settings.measurement_precision
        
        report_lines = [
            f"距離測量結果:",
            f"物件1: {obj1.name}",
            f"物件2: {obj2.name}",
            f"",
            f"中心點距離: {distance:.{precision}f}",
            f"相對位置: {bbox_analysis['relative_position']}",
            f"",
            f"邊界框重疊:",
            f"  X軸: {bbox_analysis['overlap']['x']:.{precision}f}",
            f"  Y軸: {bbox_analysis['overlap']['y']:.{precision}f}",
            f"  Z軸: {bbox_analysis['overlap']['z']:.{precision}f}",
            f"  重疊體積: {bbox_analysis['overlap']['volume']:.{precision}f}",
            f"  是否重疊: {'是' if bbox_analysis['is_overlapping'] else '否'}",
        ]
        
        # 輸出到控制台
        print("[SmartAlignPro] 距離測量報告:")
        for line in report_lines:
            print(line)
        
        # 顯示主要信息
        self.report({"INFO"}, f"距離: {distance:.{precision}f} | 重疊: {'是' if bbox_analysis['is_overlapping'] else '否'}")
        
        return {"FINISHED"}


class SMARTALIGNPRO_OT_measure_angle(Operator):
    """測量角度操作器"""
    bl_idname = "smartalignpro.measure_angle"
    bl_label = "測量角度"
    bl_description = "測量三個物件之間的角度"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        
        if len(selected) != 3:
            self.report({"WARNING"}, "請選取剛好三個 Mesh 物件")
            return {"CANCELLED"}
        
        # 獲取三個點位
        points = []
        for obj in selected:
            center = get_bbox_center_world(obj)
            points.append(center)
        
        p1, p2, p3 = points
        
        # 計算角度
        import math
        from mathutils import Vector
        
        v1 = (p1 - p2).normalized()
        v2 = (p3 - p2).normalized()
        
        # 計算夾角
        cos_angle = v1.dot(v2)
        cos_angle = max(-1.0, min(1.0, cos_angle))  # 限制在有效範圍
        angle_rad = math.acos(cos_angle)
        angle_deg = math.degrees(angle_rad)
        
        # 計算三角形面積
        area = 0.5 * (p1 - p2).cross(p3 - p2).length
        
        settings = context.scene.smartalignpro_settings
        precision = settings.measurement_precision
        
        # 生成測量報告
        report_lines = [
            f"角度測量結果:",
            f"頂點1: {selected[0].name}",
            f"頂點2: {selected[1].name} (角度頂點)",
            f"頂點3: {selected[2].name}",
            f"",
            f"夾角: {angle_deg:.{precision}f}°",
            f"弧度: {angle_rad:.{precision}f}",
            f"三角形面積: {area:.{precision}f}",
        ]
        
        # 輸出到控制台
        print("[SmartAlignPro] 角度測量報告:")
        for line in report_lines:
            print(line)
        
        # 顯示主要信息
        self.report({"INFO"}, f"角度: {angle_deg:.{precision}f}°")
        
        return {"FINISHED"}


class SMARTALIGNPRO_OT_measure_properties(Operator):
    """測量屬性操作器"""
    bl_idname = "smartalignpro.measure_properties"
    bl_label = "測量屬性"
    bl_description = "測量選取物件的各種屬性"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        
        if not selected:
            self.report({"WARNING"}, "請選取至少一個 Mesh 物件")
            return {"CANCELLED"}
        
        settings = context.scene.smartalignpro_settings
        precision = settings.measurement_precision
        
        report_lines = ["物件屬性測量結果:"]
        
        for obj in selected:
            # 基本屬性
            report_lines.extend([
                f"",
                f"物件: {obj.name}",
                f"類型: {obj.type}",
                f"位置: {obj.location}",
                f"旋轉: {obj.rotation_euler}",
                f"縮放: {obj.scale}",
                f"",
                f"邊界框尺寸: {obj.dimensions}",
                f"體積: {obj.data.volume:.{precision}f}",
                f"表面積: {obj.data.area:.{precision}f}",
                f"",
                f"幾何信息:",
                f"  頂點數: {len(obj.data.vertices)}",
                f"  邊數: {len(obj.data.edges)}",
                f"  面數: {len(obj.data.polygons)}",
                f"  材質數: {len(obj.data.materials)}",
                f"  修改器數: {len(obj.modifiers)}",
            ])
            
            # 智能檢測
            try:
                detection = detect_object_type(obj)
                report_lines.extend([
                    f"",
                    f"智能檢測:",
                    f"  類型: {detection.object_type}",
                    f"  信心度: {detection.confidence:.2f}",
                    f"  建議策略: {detection.suggested_strategy}",
                    f"  檢測原因: {', '.join(detection.reasons[:2])}",  # 只顯示前兩個原因
                ])
            except:
                pass
        
        # 輸出到控制台
        print("[SmartAlignPro] 屬性測量報告:")
        for line in report_lines:
            print(line)
        
        # 顯示摘要信息
        self.report({"INFO"}, f"測量完成：{len(selected)} 個物件")
        
        return {"FINISHED"}


class SMARTALIGNPRO_OT_clear_measurements(Operator):
    """清除測量操作器"""
    bl_idname = "smartalignpro.clear_measurements"
    bl_label = "清除測量"
    bl_description = "清除所有測量結果和顯示"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # 清除場景中的測量數據
        if hasattr(context.scene, 'smartalignpro_analysis'):
            delattr(context.scene, 'smartalignpro_analysis')
        
        # 清除 3D 視圖中的測量顯示
        # 這裡可以添加清除測量線、文字等的代碼
        
        self.report({"INFO"}, "測量結果已清除")
        return {"FINISHED"}


class SMARTALIGNPRO_OT_smart_snap(Operator):
    """智能吸附操作器"""
    bl_idname = "smartalignpro.smart_snap"
    bl_label = "智能吸附"
    bl_description = "智能吸附到最近的面或邊"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        active = context.active_object
        
        if not active or active.type != "MESH":
            self.report({"WARNING"}, "請選取一個 Mesh 物件")
            return {"CANCELLED"}
        
        try:
            # 獲取物件中心
            from ..utils.bbox_utils import get_bbox_center_world
            obj_center = get_bbox_center_world(active)
            
            # 向下射線檢測
            from ..core.math_utils import ray_cast_to_surface
            
            ray_start = obj_center + Vector((0, 0, 10))
            ray_direction = Vector((0, 0, -1))
            
            result = ray_cast_to_surface(context, ray_start, ray_direction)
            
            if result:
                # 移動到檢測到的表面
                active.location = result['location']
                
                # 可選：對齊法線
                if getattr(context.scene.smartalignpro_settings, 'normal_align_axis', None):
                    from ..core.math_utils import rotation_between_vectors

                    axis_map = {
                        "POS_X": Vector((1, 0, 0)),
                        "NEG_X": Vector((-1, 0, 0)),
                        "POS_Y": Vector((0, 1, 0)),
                        "NEG_Y": Vector((0, -1, 0)),
                        "POS_Z": Vector((0, 0, 1)),
                        "NEG_Z": Vector((0, 0, -1)),
                    }

                    settings = context.scene.smartalignpro_settings
                    target_axis = axis_map.get(getattr(settings, "normal_align_axis", "POS_Z"), Vector((0, 0, 1)))
                    rotation = rotation_between_vectors(target_axis, result['normal'])

                    current_quat = active.rotation_euler.to_quaternion()
                    new_quat = rotation @ current_quat
                    active.rotation_euler = new_quat.to_euler(active.rotation_mode)
                
                self.report({"INFO"}, f"智能吸附完成：{result['object'].name}")
                return {"FINISHED"}
            else:
                self.report({"WARNING"}, "未找到可吸附的表面")
                return {"CANCELLED"}
                
        except Exception as e:
            self.report({"ERROR"}, f"智能吸附失敗: {str(e)}")
            return {"CANCELLED"}


class SMARTALIGNPRO_OT_constraint_align(Operator):
    """約束對齊操作器"""
    bl_idname = "smartalignpro.constraint_align"
    bl_label = "約束對齊"
    bl_description = "使用 Blender 約束系統進行對齊"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        active = context.active_object
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        
        if not active or active.type != "MESH":
            self.report({"WARNING"}, "請選取一個目標 Mesh 物件作為 Active Object")
            return {"CANCELLED"}
        
        if len(selected) < 2:
            self.report({"WARNING"}, "請至少選取兩個 Mesh 物件")
            return {"CANCELLED"}
        
        sources = [obj for obj in selected if obj != active]
        if not sources:
            self.report({"WARNING"}, "找不到來源物件")
            return {"CANCELLED"}
        
        try:
            for source in sources:
                # 創建 COPY_LOCATION 約束
                constraint = source.constraints.new(type='COPY_LOCATION')
                constraint.name = "SmartAlign_Location"
                constraint.target = active
                
                # 創建 COPY_ROTATION 約束
                constraint = source.constraints.new(type='COPY_ROTATION')
                constraint.name = "SmartAlign_Rotation"
                constraint.target = active
                
                print(f"[SmartAlignPro] 約束對齊: {source.name} → {active.name}")
            
            self.report({"INFO"}, f"約束對齊完成：{len(sources)} 個物件")
            return {"FINISHED"}
            
        except Exception as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}


class SMARTALIGNPRO_OT_array_align(Operator):
    """陣列對齊操作器"""
    bl_idname = "smartalignpro.array_align"
    bl_label = "陣列對齊"
    bl_description = "將物件對齊到陣列模式"
    bl_options = {"REGISTER", "UNDO"}

    count: IntProperty(
        name="數量",
        description="陣列數量",
        default=3,
        min=2,
        max=100
    )
    
    offset: FloatProperty(
        name="偏移",
        description="陣列偏移距離",
        default=1.0,
        min=0.1
    )

    def execute(self, context):
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        
        if not selected:
            self.report({"WARNING"}, "請選取至少一個 Mesh 物件")
            return {"CANCELLED"}
        
        try:
            aligned_count = 0
            
            for obj in selected:
                # 創建 ARRAY 修改器
                modifier = obj.modifiers.new(name="SmartAlign_Array", type='ARRAY')
                modifier.count = self.count
                
                # 設置偏移
                if hasattr(modifier, 'relative_offset_displace'):
                    modifier.relative_offset_displace = (self.offset, 0, 0)
                
                aligned_count += 1
                print(f"[SmartAlignPro] 陣列對齊: {obj.name} ({self.count}個)")
            
            self.report({"INFO"}, f"陣列對齊完成：{aligned_count} 個物件")
            return {"FINISHED"}
            
        except Exception as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}


class SMARTALIGNPRO_OT_batch_ground(Operator):
    """批量貼地操作器"""
    bl_idname = "smartalignpro.batch_ground"
    bl_label = "批量貼地"
    bl_description = "將多個物件批量貼地對齊"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        
        if not selected:
            self.report({"WARNING"}, "請選取至少一個 Mesh 物件")
            return {"CANCELLED"}
        
        try:
            from ..core.alignment import align_to_ground
            
            results = align_to_ground(selected, context.scene.smartalignpro_settings)
            
            if results:
                self.report({"INFO"}, f"批量貼地完成：{len(results)} 個物件")
            else:
                self.report({"WARNING"}, "沒有找到地面，無法貼地")
            
            return {"FINISHED"}
            
        except Exception as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}


class SMARTALIGNPRO_OT_smart_group(Operator):
    """智能分組操作器"""
    bl_idname = "smartalignpro.smart_group"
    bl_label = "智能分組"
    bl_description = "根據物件類型智能分組"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        
        if not selected:
            self.report({"WARNING"}, "請選取至少一個 Mesh 物件")
            return {"CANCELLED"}
        
        try:
            # 分析物件類型
            groups = {}
            
            for obj in selected:
                detection = detect_object_type(obj)
                obj_type = detection.object_type
                
                if obj_type not in groups:
                    groups[obj_type] = []
                groups[obj_type].append(obj)
            
            # 創建集合並分組
            created_groups = 0
            
            for obj_type, objects in groups.items():
                # 創建新集合
                collection_name = f"SmartAlign_{obj_type}"
                collection = bpy.data.collections.new(collection_name)
                context.scene.collection.children.link(collection)
                
                # 移動物件到集合
                for obj in objects:
                    collection.objects.link(obj)
                    # 從原集合中移除（如果不在場景集合中）
                    for col in obj.users_collection:
                        if col != context.scene.collection:
                            col.objects.unlink(obj)
                
                created_groups += 1
                print(f"[SmartAlignPro] 智能分組: {obj_type} ({len(objects)}個物件)")
            
            self.report({"INFO"}, f"智能分組完成：{created_groups} 個組")
            return {"FINISHED"}
            
        except Exception as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
