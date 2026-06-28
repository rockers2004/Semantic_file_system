use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};

// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
fn open_in_default_app(path: String) -> Result<(), String> {
    let resolved_path = PathBuf::from(&path);
    if !resolved_path.exists() {
        return Err(format!("File does not exist: {}", path));
    }

    let normalized = resolved_path
        .canonicalize()
        .unwrap_or(resolved_path)
        .to_string_lossy()
        .to_string();

    #[cfg(target_os = "windows")]
    {
        Command::new("cmd")
            .arg("/C")
            .arg("start")
            .arg("")
            .arg(&normalized)
            .spawn()
            .map_err(|e| format!("Failed to open file in the default Windows app: {}", e))?;

        Ok(())
    }

    #[cfg(target_os = "macos")]
    {
        Command::new("open")
            .arg(&normalized)
            .spawn()
            .map_err(|e| format!("Failed to open file in the default macOS app: {}", e))?;

        Ok(())
    }

    #[cfg(all(unix, not(target_os = "macos")))]
    {
        Command::new("xdg-open")
            .arg(&normalized)
            .spawn()
            .map_err(|e| format!("Failed to open file in the default app: {}", e))?;

        Ok(())
    }
}

#[tauri::command]
fn show_in_folder(path: String) -> Result<(), String> {
    let resolved_path = PathBuf::from(&path);
    if !resolved_path.exists() {
        return Err(format!("File does not exist: {}", path));
    }

    let normalized = resolved_path
        .canonicalize()
        .unwrap_or(resolved_path)
        .to_string_lossy()
        .to_string();

    #[cfg(target_os = "windows")]
    {
        Command::new("explorer")
            .arg("/select,")
            .arg(&normalized)
            .spawn()
            .map_err(|e| format!("Failed to open folder in Explorer: {}", e))?;
        Ok(())
    }

    #[cfg(target_os = "macos")]
    {
        Command::new("open")
            .arg("-R")
            .arg(&normalized)
            .spawn()
            .map_err(|e| format!("Failed to reveal file in Finder: {}", e))?;
        Ok(())
    }

    #[cfg(all(unix, not(target_os = "macos")))]
    {
        let parent = Path::new(&normalized)
            .parent()
            .ok_or_else(|| "Cannot determine parent directory".to_string())?;
        Command::new("xdg-open")
            .arg(parent.to_string_lossy().to_string())
            .spawn()
            .map_err(|e| format!("Failed to open folder: {}", e))?;
        Ok(())
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

    // Prefer platform-specific virtualenv paths first, then try system python3 then python.
    let venv_python_win = project_root.join("myenv").join("Scripts").join("python.exe");
    let venv_python_unix = project_root.join("myenv").join("bin").join("python3");

    let candidates: Vec<PathBuf> = if venv_python_win.exists() {
        vec![venv_python_win]
    } else if venv_python_unix.exists() {
        vec![venv_python_unix]
    } else {
        vec![PathBuf::from("python3"), PathBuf::from("python")]
    };

    // Try each candidate until one successfully spawns. If a non-NotFound error
    // occurs, return it immediately.
    for cmd in candidates {
        match Command::new(&cmd)
            .arg(&backend_script)
            .current_dir(&project_root)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
        {
            Ok(child) => return Ok(child),
            Err(e) => {
                if e.kind() == std::io::ErrorKind::NotFound {
                    // Try next candidate
                    continue;
                }
                return Err(format!("Failed to start Python backend: {}", e));
            }
        }
    }

    Err("Failed to start Python backend: no python executable found in PATH".to_string())
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
        .invoke_handler(tauri::generate_handler![greet, open_in_default_app, show_in_folder])
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
