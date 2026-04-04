# PATCH_NOTES_v7_3.md

v7.3 修正重點：

1. 修正 `modal/__init__.py` 仍引用不存在的 `modal_two_point.py` / `modal_three_point.py`
2. 新增 `modal/modal_two_point.py`、`modal/modal_three_point.py` 相容 shim
3. 修正 `smart_align_pro_modular.py`：
   - settings 重複註冊保護
   - unregister_classes 在 import chain 壞掉時不再整包崩
   - bbox handler 改用實際存在的 `remove_bbox_handler()`
   - 納入 `view_oriented_operators`
4. 修正 `utils/bbox_utils.py`：
   - 補 `remove_bbox_overlay_handler()` 舊名相容
   - 補 `SMARTALIGNPRO_OT_toggle_bbox_point_overlay` 類名相容
5. 修正 `core/topology_alignment.py`：
   - 新增 `SnapType`
   - `TopologySnapPoint` 相容 `position=` / `object=`
   - 移除 world matrix 雙重套用
   - 補 `bm.free()`
6. 修正 ZIP 根目錄名稱為合法 Python package：`smart_align_pro_v7_3`

建議你 Blender 端先把舊的同名資料夾刪掉，再安裝這版 ZIP。
