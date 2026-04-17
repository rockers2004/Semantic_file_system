use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};

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

fn find_project_root(start: &Path) -> Option<PathBuf> {
    let candidates = [
        start.to_path_buf(),
        start.parent()?.to_path_buf(),
        start.parent()?.parent()?.to_path_buf(),
    ];

    candidates
        .into_iter()
        .find(|candidate| candidate.join("backend_api").join("app").join("main.py").exists())
}

fn start_python_backend() -> Result<Child, String> {
    let cwd = std::env::current_dir().map_err(|e| format!("Failed to read cwd: {}", e))?;
    let project_root = find_project_root(&cwd).ok_or_else(|| {
        "Unable to locate project root containing backend_api/app/main.py".to_string()
    })?;

    let backend_script = project_root.join("backend_api").join("app").join("main.py");
    if !backend_script.exists() {
        return Err(format!("Backend script not found: {}", backend_script.display()));
    }

    let venv_python = project_root.join("myenv").join("Scripts").join("python.exe");
    let python_cmd = if venv_python.exists() {
        venv_python
    } else {
        PathBuf::from("python")
    };

    Command::new(python_cmd)
        .arg(backend_script)
        .current_dir(project_root)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("Failed to start Python backend: {}", e))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend_child: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
    let backend_for_setup = Arc::clone(&backend_child);
    let backend_for_exit = Arc::clone(&backend_child);

    tauri::Builder::default()
        .setup(move |_app| {
            let mut guard = backend_for_setup
                .lock()
                .map_err(|_| "Failed to acquire backend process lock".to_string())?;

            if guard.is_none() {
                *guard = Some(start_python_backend()?);
            }

            Ok(())
        })
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![greet, open_with_dialog])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(move |_app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                if let Ok(mut guard) = backend_for_exit.lock() {
                    if let Some(mut child) = guard.take() {
                        let _ = child.kill();
                        let _ = child.wait();
                    }
                }
            }
        });
}
