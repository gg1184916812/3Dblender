# Smart Align Pro v7.1 Patch Notes

本次補丁重點：

- 修正 `operators/cad_operators.py` 缺少 `log_hotkey_done`、`update_two_point_preview`、`apply_preview`、`cancel_preview` 匯入，避免 CAD modal 執行時直接報錯。
- 修正 CAD modal 完成或失敗後未確實清理 HUD / overlay / preview 的問題。
- 修正 `operators/quick_align_operators.py` 缺少 `view3d_utils`、`log_hotkey_cancel` 匯入。
- 修正快速對齊面板引用不存在的 `context.scene.smartalignpro_settings.offset_distance` 屬性，並補回該設定欄位。
- 修正 `operators/view_oriented_operators.py` 缺少 `log_hotkey_cancel` 匯入。
- 修正視圖導向 AUTO 模式回傳錯誤向量，避免自動對齊方向計算失真。

注意：

- 這一版是針對靜態可見問題與明顯執行期阻塞點做補丁。
- 我沒有在 Blender 4.5 實機跑完整互動測試，所以不能誠實宣稱已經全部功能完美。
