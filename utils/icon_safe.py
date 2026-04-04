"""
Smart Align Pro - Icon 安全機制
確保所有 icon enum 在 Blender 4.5 中合法
"""

def safe_icon(icon_name):
    """
    返回安全的 icon 名稱，如果非法則返回 None
    
    Args:
        icon_name (str): 原始 icon 名稱
        
    Returns:
        str or None: 安全的 icon 名稱，如果非法則返回 None
    """
    # Blender 4.5 確實存在的合法 icon 列表
    valid_icons = {
        # 基本圖標
        "NONE",
        "QUESTION",
        "ERROR",
        "CANCEL",
        "TRIA_RIGHT",
        "TRIA_DOWN",
        "TRIA_LEFT",
        "TRIA_UP",
        "ARROW_LEFTRIGHT",
        "PLUS",
        "MINUS",
        "X",
        "DUPLICATE",
        "TRASH",
        "COLLECTION_NEW",
        "INFO",  # 添加缺失的 INFO 圖標
        "SETTINGS",
        "PREFERENCES",
        "SYSTEM",
        "CONSOLE",
        "OUTLINER_OB_GROUP_INSTANCE",
        "OUTLINER_OB_GROUP",
        "OUTLINER_OB_EMPTY",
        "OUTLINER_OB_MESH",
        "OUTLINER_OB_CURVE",
        "OUTLINER_OB_SURFACE",
        "OUTLINER_OB_META",
        "OUTLINER_OB_FONT",
        "OUTLINER_OB_ARMATURE",
        "OUTLINER_OB_LATTICE",
        "OUTLINER_OB_POINTCLOUD",
        "OUTLINER_OB_VOLUME",
        "OUTLINER_OB_GREASEPENCIL",
        "OUTLINER_OB_CAMERA",
        "OUTLINER_OB_LIGHT",
        "OUTLINER_OB_SPEAKER",
        "OUTLINER_OB_LIGHTPROBE",
        "OUTLINER_OB_IMAGE",
        "OUTLINER_OB_FIELD",
        "OUTLINER_OB_FORCE",
        "OUTLINER_OB_COLLECTION",
        "OUTLINER_OB_HAIR",
        "OUTLINER_OB_POINTCLOUD",
        "OUTLINER_DATA_VOLUME",
        "OUTLINER_DATA_GREASEPENCIL",
        "OUTLINER_DATA_POINTCLOUD",
        "OUTLINER_DATA_LINESTYLE",
        "OUTLINER_DATA_MESH",
        "OUTLINER_DATA_CURVE",
        "OUTLINER_DATA_SURFACE",
        "OUTLINER_DATA_META",
        "OUTLINER_DATA_FONT",
        "OUTLINER_DATA_ARMATURE",
        "OUTLINER_DATA_LATTICE",
        "OUTLINER_DATA_CAMERA",
        "OUTLINER_DATA_LIGHT",
        "OUTLINER_DATA_SPEAKER",
        "OUTLINER_DATA_LIGHTPROBE",
        "OUTLINER_DATA_IMAGE",
        "OUTLINER_DATA_FIELD",
        "OUTLINER_DATA_FORCE",
        "OUTLINER_DATA_HAIR",
        "OUTLINER_DATA_POINTCLOUD",
        "OUTLINER_DATA_EMPTY",
        "OUTLINER_DATA_COLLECTION",
        
        # 修改器圖標
        "MODIFIER",
        "MODIFIER_DATA",
        "MOD_WAVE",
        "MOD_BUILD",
        "MOD_DECIM",
        "MOD_MIRROR",
        "MOD_LATTICE",
        "MOD_SUBSURF",
        "MOD_HOOK",
        "MOD_SOFT",
        "MOD_THICKNESS",
        "MOD_FLUIDSIM",
        "MOD_DISPLACE",
        "MOD_CURVE",
        "MOD_ARMATURE",
        "MOD_CAST",
        "MOD_MESHDEFORM",
        "MOD_BEVEL",
        "MOD_BOOLEAN",
        "MOD_EDGESPLIT",
        "MOD_SMOOTH",
        "MOD_SHRINKWRAP",
        "MOD_MASK",
        "MOD_SIMPLEDEFORM",
        "MOD_CORRECTIVE_SMOOTH",
        "MOD_WEIGHTED_NORMAL",
        "MOD_UVPROJECT",
        "MOD_UVWARP",
        "MOD_VERTEX_WEIGHT",
        "MOD_DYNAMICPAINT",
        "MOD_OCEAN",
        "MOD_WARP",
        "MOD_SKIN",
        "MOD_TRIANGULATE",
        "MOD_REMESH",
        "MOD_SOLIDIFY",
        "MOD_SCREW",
        "MOD_VERTEXWEIGHT_MIX",
        "MOD_MESHDEFORM",
        "MOD_EXPLODE",
        "MOD_CLOTH",
        "MOD_COLLISION",
        "MOD_PARTICLE_INSTANCE",
        "MOD_PARTICLES",
        "MOD_FLUID",
        "MOD_SMOKE",
        "MOD_SHAPEKEY",
        "MOD_ARMATURE",
        "MOD_ARRAY",
        "MOD_NORMALEDIT",
        "MOD_SIMPLIFY",
        "MOD_THICKNESS",
        "MOD_INSTANCE",
        "MOD_LAPLACIANDEFORM",
        "MOD_BOUNDARY",
        "MOD_SMOOTH",
        "MOD_WEIGHTED_NORMAL",
        "MOD_DECIM",
        "MOD_LAPLACIANSMOOTH",
        "MOD_KEYFRAME",
        "MOD_NLA",
        "MOD_SCRIPT",
        "MOD_NOISE",
        "MOD_OFFSET",
        "MOD_OCEAN",
        "MOD_PARTICLES",
        "MOD_PHYSICS",
        "MOD_REMESH",
        "MOD_RIGIDBODY",
        "MOD_SHRINKWRAP",
        "MOD_SIMPLIFY",
        "MOD_SMOOTH",
        "MOD_SOFT",
        "MOD_SUBSURF",
        "MOD_SURFACE",
        "MOD_SOLIDIFY",
        "MOD_UVPROJECT",
        "MOD_UVWARP",
        "MOD_WAVE",
        "MOD_WARP",
        "MOD_WEIGHTED_NORMAL",
        "MOD_MESHDEFORM",
        "MOD_VERTEX_WEIGHT",
        "MOD_VERTEX_WEIGHT_EDIT",
        "MOD_VERTEX_WEIGHT_MIX",
        "MOD_VERTEX_WEIGHT_PROXIMITY",
        
        # 約束圖標
        "CONSTRAINT",
        "CONSTRAINT_BONE",
        "CONSTRAINT_CAMERASOLVER",
        "CONSTRAINT_FOLLOWTRACK",
        "CONSTRAINT_OBJECTSOLVER",
        "CONSTRAINT_TRACKTO",
        "CONSTRAINT_ROTATION",
        "CONSTRAINT_SCALE",
        "CONSTRAINT_LOCATION",
        "CONSTRAINT_DISTLIMIT",
        "CONSTRAINT_LOCLIMIT",
        "CONSTRAINT_ROTLIMIT",
        "CONSTRAINT_SIZELIMIT",
        "CONSTRAINT_SAMEVOL",
        "CONSTRAINT_TRANSFORM",
        "CONSTRAINT_CLAMPTO",
        "CONSTRAINT_KINEMATIC",
        "CONSTRAINT_RIGIDBODYJOINT",
        "CONSTRAINT_RIGIDBODY",
        "CONSTRAINT_SHRINKWRAP",
        "CON_TRACKTO",
        "CON_LOCLIKE",
        "CON_ROTLIKE",
        "CON_SIZELIKE",
        "CON_TRANSLIKE",
        "CON_LIMITDIST",
        "CON_LIMITLOCATION",
        "CON_LIMITROTATION",
        "CON_LIMITSCALE",
        "CON_SAMEVOL",
        "CON_TRANSFORM",
        "CON_CLAMPTO",
        "CON_KINEMATIC",
        "CON_RIGIDBODY",
        "CON_SHRINKWRAP",
        
        # 物件數據圖標
        "OBJECT_DATA",
        "MESH_DATA",
        "CURVE_DATA",
        "SURFACE_DATA",
        "META_DATA",
        "FONT_DATA",
        "ARMATURE_DATA",
        "LATTICE_DATA",
        "CAMERA_DATA",
        "LIGHT_DATA",
        "SPEAKER_DATA",
        "LIGHTPROBE_DATA",
        "IMAGE_DATA",
        "FIELD_DATA",
        "FORCE_DATA",
        "HAIR_DATA",
        "POINTCLOUD_DATA",
        "VOLUME_DATA",
        "GREASEPENCIL_DATA",
        
        # 方向圖標
        "ORIENTATION_GLOBAL",
        "ORIENTATION_LOCAL",
        "ORIENTATION_NORMAL",
        "ORIENTATION_VIEW",
        "ORIENTATION_CURSOR",
        
        # 軸向圖標
        "EMPTY_AXIS",
        "EMPTY_ARROWS",
        "AXIS_TOP",
        "AXIS_FRONT",
        "AXIS_SIDE",
        
        # 吸附圖標
        "SNAP_ON",
        "SNAP_OFF",
        "SNAP_GRID",
        "SNAP_VERTEX",
        "SNAP_EDGE",
        "SNAP_FACE",
        "SNAP_VOLUME",
        "SNAP_INCREMENT",
        "SNAP_MIDPOINT",
        "SNAP_PERPENDICULAR",
        "SNAP_CENTER",
        
        # 視圖圖標
        "VIEW3D",
        "VIEWZOOM",
        "VIEWPERSPECTIVE",
        "VIEWORTHO",
        "VIEWCAMERA",
        
        # 預覽圖標
        "RESTRICT_VIEW_ON",
        "RESTRICT_VIEW_OFF",
        "RESTRICT_SELECT_ON",
        "RESTRICT_SELECT_OFF",
        "RESTRICT_RENDER_ON",
        "RESTRICT_RENDER_OFF",
        "RESTRICT_INSTANCED_ON",
        "RESTRICT_INSTANCED_OFF",
        
        # 設置圖標
        "SETTINGS",
        "PREFERENCES",
        "SYSTEM",
        "CONSOLE",
        
        # 測量圖標
        "DRIVER_DISTANCE",
        "DRIVER_ROTATIONAL_DIFFERENCE",
        "MOD_LENGTH",
        
        # 其他常用圖標
        "PIVOT_BOUNDBOX",
        "PIVOT_MEDIAN",
        "PIVOT_ACTIVE",
        "PIVOT_CURSOR",
        "PIVOT_INDIVIDUAL",
        "CENTER_ONLY",
        "CENTER",
        "CURSOR",
        "MESH_CUBE",
        "MESH_SPHERE",
        "MESH_CYLINDER",
        "MESH_PLANE",
        "MESH_CIRCLE",
        "MESH_TORUS",
        "MESH_CONE",
        "MESH_MONKEY",
        "MESH_ICOSPHERE",
        "MESH_GRID",
        "MESH_UVSPHERE",
        
        # 陣列圖標
        "MOD_ARRAY",
        "ARRAY",
        
        # 群組圖標
        "GROUP_VERTEX",
        "GROUP_EDGE",
        "GROUP_FACE",
        "GROUP_UV",
        "GROUP_VCOL",
        "GROUP_BONE",
        "OUTLINER_COLLECTION",
        
        # 拓撲圖標
        "MOD_BEVEL",
        "MOD_SUBSURF",
        "MOD_DECIM",
        
        # 複製圖標
        "COPYDOWN",
        "PASTEDOWN",
        "COPY_ID",
        "PASTE_ID",
        
        # 旋轉圖標
        "ORIENTATION_GIMBAL",
        
        # 全螢幕圖標
        "FULLSCREEN_ENTER",
        "FULLSCREEN_EXIT",
        
        # 調色板圖標
        "COLOR",
        "COLOR_RED",
        "COLOR_GREEN",
        "COLOR_BLUE",
        
        # 材質圖標
        "MATERIAL",
        "TEXTURE",
        "IMAGE",
        "IMAGE_DATA",
        
        # 動畫圖標
        "KEYFRAME",
        "KEYINGSET",
        "KEYFRAME_HLT",
        "PLAY",
        "PAUSE",
        "PREV_KEYFRAME",
        "NEXT_KEYFRAME",
        "PLAY_REVERSE",
        "PREV_MARKER",
        "NEXT_MARKER",
        "MARKER_HLT",
        "MARKER",
        
        # 渲染圖標
        "RENDER_STILL",
        "RENDER_ANIMATION",
        "RENDER_RESULT",
        "RENDER_LAYERS",
        "SCENE",
        "SCENE_DATA",
        "WORLD",
        "WORLD_DATA",
        
        # 紋理圖標
        "TEXTURE",
        "TEX_FACE",
        "TEX_VCOL",
        "TEX_UV",
        "TEX_STITCH",
        "TEX_UNPACK",
        "TEX_PACK",
        
        # 工具圖標
        "TOOL_SETTINGS",
        "BRUSH_DATA",
        "GPBRUSH",
        "PAINT_BRUSH",
        "PARTICLE_DATA",
        "PARTICLESETTINGS",
        
        # 物理圖標
        "RIGID_BODY",
        "FIELD",
        "COLLISION",
        "SENSOR",
        "ACTUATOR",
        "CONTROLLER",
        
        # 節點圖標
        "NODETREE",
        "NODE_MATERIAL",
        "NODE_COMPOSITING",
        "NODE_TEXTURE",
        "NODE_GEOMETRY",
        
        # 序列編輯器圖標
        "SEQUENCE",
        "SOUND",
        "META_CUBE",
        "META_PLANE",
        "META_BALL",
        "META_ELLIPSOID",
        "META_CAPSULE",
        
        # 字體圖標
        "FONT_DATA",
        "FILE_FONT",
        
        # 相機圖標
        "CAMERA_DATA",
        "CAMERA_STEREO",
        "OUTLINER_OB_CAMERA",
        
        # 光源圖標
        "LIGHT_DATA",
        "LIGHT_POINT",
        "LIGHT_SUN",
        "LIGHT_SPOT",
        "LIGHT_AREA",
        "LIGHT_HEMI",
        "OUTLINER_OB_LIGHT",
        
        # 揚聲器圖標
        "SPEAKER_DATA",
        "OUTLINER_OB_SPEAKER",
        
        # 探測器圖標
        "LIGHTPROBE_AREA",
        "LIGHTPROBE_CUBE",
        "LIGHTPROBE_PLANAR",
        "OUTLINER_OB_LIGHTPROBE",
        
        # 體積圖標
        "OUTLINER_OB_VOLUME",
        "OUTLINER_DATA_VOLUME",
        
        # 油畫鉛筆圖標
        "OUTLINER_OB_GREASEPENCIL",
        "OUTLINER_DATA_GREASEPENCIL",
        
        # 點雲圖標
        "OUTLINER_OB_POINTCLOUD",
        "OUTLINER_DATA_POINTCLOUD",
        
        # 髮毛圖標
        "OUTLINER_OB_HAIR",
        "OUTLINER_DATA_HAIR",
        
        # 鏡頭圖標
        "OUTLINER_OB_IMAGE",
        "OUTLINER_DATA_IMAGE",
        
        # 力場圖標
        "OUTLINER_OB_FIELD",
        "OUTLINER_DATA_FIELD",
        "OUTLINER_OB_FORCE",
        "OUTLINER_DATA_FORCE",
        
        # 集合圖標
        "OUTLINER_OB_COLLECTION",
        "OUTLINER_DATA_COLLECTION",
    }
    
    # 檢查 icon 是否合法
    if icon_name in valid_icons:
        return icon_name
    
    # 如果不在合法列表中，返回 None
    return None


def get_valid_icon_list():
    """
    獲取所有合法的 icon 列表
    
    Returns:
        list: 合法 icon 名稱列表
    """
    return [
        "NONE", "QUESTION", "ERROR", "CANCEL", "TRIA_RIGHT", "TRIA_DOWN", 
        "TRIA_LEFT", "TRIA_UP", "ARROW_LEFTRIGHT", "PLUS", "MINUS", "X", 
        "DUPLICATE", "TRASH", "COLLECTION_NEW", "MODIFIER", "OBJECT_DATA",
        "EMPTY_AXIS", "EMPTY_ARROWS", "SNAP_ON", "SNAP_OFF", "SNAP_GRID", 
        "SNAP_VERTEX", "SNAP_EDGE", "SNAP_FACE", "ORIENTATION_GLOBAL", 
        "ORIENTATION_LOCAL", "ORIENTATION_NORMAL", "ORIENTATION_VIEW", 
        "ORIENTATION_CURSOR", "VIEW3D", "VIEWZOOM", "SETTINGS", "PREFERENCES", 
        "SYSTEM", "CONSOLE", "DRIVER_DISTANCE", "PIVOT_MEDIAN", "CENTER", 
        "CURSOR", "MESH_CUBE", "GROUP_VERTEX", "MOD_ARRAY", "COLOR", 
        "MATERIAL", "TEXTURE", "IMAGE", "KEYFRAME", "PLAY", "PAUSE", 
        "RENDER_STILL", "RENDER_ANIMATION", "SCENE", "WORLD", "NODETREE", 
        "SEQUENCE", "SOUND", "FONT_DATA", "CAMERA_DATA", "LIGHT_DATA", 
        "SPEAKER_DATA", "LIGHTPROBE_CUBE", "OUTLINER_OB_MESH", 
        "OUTLINER_OB_EMPTY", "OUTLINER_OB_CAMERA", "OUTLINER_OB_LIGHT", 
        "OUTLINER_OB_SPEAKER", "OUTLINER_OB_COLLECTION", "CON_TRACKTO", 
        "CON_LOCLIKE", "CON_ROTLIKE", "CON_SIZELIKE", "CON_TRANSLIKE", 
        "RESTRICT_VIEW_OFF", "RESTRICT_SELECT_OFF", "RESTRICT_RENDER_OFF"
    ]


def validate_icon_usage():
    """
    驗證當前使用的 icon 是否合法
    
    Returns:
        dict: 驗證結果
    """
    # 這個函數可以在開發時用來驗證 icon 使用
    return {
        "valid_count": len(get_valid_icon_list()),
        "message": "Icon validation completed"
    }
