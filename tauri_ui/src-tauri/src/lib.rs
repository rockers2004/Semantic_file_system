// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
fn open_with_dialog(path: String) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        use std::path::PathBuf;
        use std::process::Command;

        let resolved_path = PathBuf::from(&path);
        if !resolved_path.exists() {
            return Err(format!("File does not exist: {}", path));
        }

        let normalized = resolved_path
            .canonicalize()
            .unwrap_or(resolved_path)
            .to_string_lossy()
            .to_string();

        Command::new("rundll32.exe")
            .arg("shell32.dll,OpenAs_RunDLL")
            .arg(normalized)
            .spawn()
            .map_err(|e| format!("Failed to launch Open With dialog: {}", e))?;

        Ok(())
    }

    #[cfg(not(target_os = "windows"))]
    {
        let _ = path;
        Err("Open With dialog is only supported on Windows in this app".to_string())
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
    .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![greet, open_with_dialog])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
