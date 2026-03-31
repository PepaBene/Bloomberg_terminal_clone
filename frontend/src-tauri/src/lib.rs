use tauri::WebviewWindowBuilder;

#[tauri::command]
fn detach_panel(app: tauri::AppHandle, panel_id: String) -> Result<(), String> {
    let label = format!("detached-{}", panel_id);

    // Check if window already exists
    if app.get_webview_window(&label).is_some() {
        // Focus existing window
        if let Some(win) = app.get_webview_window(&label) {
            win.set_focus().map_err(|e| e.to_string())?;
        }
        return Ok(());
    }

    let url = format!("index.html#detached/{}", panel_id);
    WebviewWindowBuilder::new(&app, &label, tauri::WebviewUrl::App(url.into()))
        .title(format!("Terminal — {}", panel_id))
        .inner_size(1200.0, 800.0)
        .decorations(true)
        .build()
        .map_err(|e| e.to_string())?;

    Ok(())
}

#[tauri::command]
fn get_window_label(window: tauri::Window) -> String {
    window.label().to_string()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![detach_panel, get_window_label])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
