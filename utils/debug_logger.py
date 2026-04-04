"""
Smart Align Pro - 詳細偵錯日誌工具
每次操作都記錄成 JSONL，方便回放對齊前後狀態。
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime
from typing import Any

from mathutils import Matrix, Vector


def _addon_root() -> str:
    return os.path.dirname(os.path.dirname(__file__))


def _log_path() -> str:
    return os.path.join(_addon_root(), 'smart_align_pro_debug_log.jsonl')


def _safe_float(v: Any) -> Any:
    try:
        if isinstance(v, float):
            if math.isfinite(v):
                return round(v, 6)
            return str(v)
        return float(v)
    except Exception:
        return v


def _convert(value: Any) -> Any:
    if isinstance(value, Vector):
        return [_safe_float(x) for x in value]
    if isinstance(value, Matrix):
        return [[_safe_float(x) for x in row] for row in value]
    if isinstance(value, dict):
        return {str(k): _convert(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_convert(v) for v in value]
    if hasattr(value, 'name') and not isinstance(value, (str, bytes)):
        return getattr(value, 'name', repr(value))
    if isinstance(value, (int, str, bool)) or value is None:
        return value
    if isinstance(value, float):
        return _safe_float(value)
    return repr(value)


def _bbox_center_world(obj) -> Vector | None:
    try:
        return sum((obj.matrix_world @ Vector(corner) for corner in obj.bound_box), Vector()) / 8.0
    except Exception:
        return None


def snapshot_object(obj) -> dict[str, Any] | None:
    if obj is None:
        return None
    try:
        loc, rot, scale = obj.matrix_world.decompose()
        rot_euler = rot.to_euler('XYZ')
        return {
            'name': obj.name,
            'type': getattr(obj, 'type', None),
            'location': _convert(loc),
            'rotation_euler_deg': [round(math.degrees(a), 6) for a in rot_euler],
            'rotation_quaternion': _convert(rot),
            'scale': _convert(scale),
            'dimensions': _convert(getattr(obj, 'dimensions', None)),
            'bbox_center_world': _convert(_bbox_center_world(obj)),
            'matrix_world': _convert(obj.matrix_world.copy()),
        }
    except Exception as e:
        return {'name': getattr(obj, 'name', '<unknown>'), 'snapshot_error': str(e)}


def log_event(action: str, **payload: Any) -> None:
    record = {
        'ts': datetime.now().isoformat(timespec='milliseconds'),
        'action': action,
        **{k: _convert(v) for k, v in payload.items()},
    }
    line = json.dumps(record, ensure_ascii=False)
    try:
        with open(_log_path(), 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception as e:
        print(f'[SmartAlignPro][DEBUG_LOG][WRITE_FAIL] {e}')
    print(f'[SmartAlignPro][DEBUG_LOG] {line}')


def log_operator_start(operator_name: str, context, **extra: Any) -> None:
    selected = [obj.name for obj in getattr(context, 'selected_objects', [])]
    active = getattr(getattr(context, 'active_object', None), 'name', None)
    log_event(
        'operator_start',
        operator=operator_name,
        active_object=active,
        selected_objects=selected,
        extra=extra,
    )


def log_operator_end(operator_name: str, status: str, **extra: Any) -> None:
    log_event('operator_end', operator=operator_name, status=status, extra=extra)


def log_object_pair(operator_name: str, source_obj, target_obj, label: str, **extra: Any) -> None:
    log_event(
        'object_pair_state',
        operator=operator_name,
        label=label,
        source=snapshot_object(source_obj),
        target=snapshot_object(target_obj),
        extra=extra,
    )


def log_pick_point(operator_name: str, stage: str, obj, location, **extra: Any) -> None:
    log_event(
        'pick_point',
        operator=operator_name,
        stage=stage,
        object_snapshot=snapshot_object(obj),
        location=location,
        extra=extra,
    )


def log_single_object_state(operator_name: str, label: str, obj, **extra: Any) -> None:
    log_event(
        'single_object_state',
        operator=operator_name,
        label=label,
        object_snapshot=snapshot_object(obj),
        extra=extra,
    )


def _vector_delta(a: Any, b: Any):
    try:
        return _convert(Vector(b) - Vector(a))
    except Exception:
        return None


def log_transform_delta(operator_name: str, source_before, source_after, target_before=None, target_after=None, **extra: Any) -> None:
    delta = {
        'source_location_delta': _vector_delta(source_before.get('location') if source_before else None, source_after.get('location') if source_after else None),
        'source_scale_delta': _vector_delta(source_before.get('scale') if source_before else None, source_after.get('scale') if source_after else None),
        'source_dimensions_delta': _vector_delta(source_before.get('dimensions') if source_before else None, source_after.get('dimensions') if source_after else None),
        'source_bbox_center_delta': _vector_delta(source_before.get('bbox_center_world') if source_before else None, source_after.get('bbox_center_world') if source_after else None),
    }
    if source_before and source_after:
        try:
            delta['source_rotation_delta_deg'] = [round(b - a, 6) for a, b in zip(source_before.get('rotation_euler_deg', []), source_after.get('rotation_euler_deg', []))]
        except Exception:
            pass
    log_event(
        'transform_delta',
        operator=operator_name,
        source_before=source_before,
        source_after=source_after,
        target_before=target_before,
        target_after=target_after,
        delta=delta,
        extra=extra,
    )


# Backward-compatible aliases for older operator imports
def debug_log(action: str, **payload: Any) -> None:
    log_event(action, **payload)


def log_object_pair_state(operator_name: str, label: str, source_obj, target_obj, extra: Any | None = None, **kwargs: Any) -> None:
    merged = {}
    if isinstance(extra, dict):
        merged.update(extra)
    merged.update(kwargs)
    log_object_pair(operator_name, source_obj, target_obj, label, **merged)


def debug_print(*args, **kwargs) -> None:
    """調試列印 - 僅在 debug_mode 啟用時輸出
    
    用法:
        debug_print("message")  # 簡單訊息
        debug_print("value:", value)  # 多參數
        debug_print("condition:", condition, prefix="INFO")  # 自訂前綴
    """
    try:
        settings = bpy.context.scene.smartalignpro_settings
        if not getattr(settings, 'debug_mode', False):
            return
    except Exception:
        return
    
    prefix = kwargs.pop('prefix', 'DEBUG')
    messages = ' '.join(str(arg) for arg in args)
    print(f'[SmartAlignPro][{prefix}] {messages}')


# v7.5 新增：高風險區塊 fallback 記錄函數
def log_fallback_behavior(module: str, original_error: str, fallback_action: str):
    """記錄 fallback 行為 - 取代 pass 的高風險區塊"""
    print(f'[SmartAlignPro][FALLBACK][{module}] {fallback_action} (original: {original_error})')


def log_preview_cleanup_failure(handler_name: str, details: dict = None):
    """記錄預覽清理失敗"""
    detail_str = f" | {details}" if details else ""
    print(f'[SmartAlignPro][WARNING][PREVIEW] 預覽清理失敗: {handler_name}{detail_str}')


def log_snap_candidate_failure(mode: str, obj_count: int, mouse_pos: tuple, error: str):
    """記錄吸附候選失敗"""
    print(f'[SmartAlignPro][WARNING][SNAP] 候選失敗: mode={mode}, objects={obj_count}, mouse={mouse_pos}, error={error}')


def log_constraint_failure(axis_lock: str, current_state: str, error: str):
    """記錄約束失敗"""
    print(f'[SmartAlignPro][WARNING][CONSTRAINT] 約束失敗: axis={axis_lock}, state={current_state}, error={error}')
