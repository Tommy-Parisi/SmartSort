use tauri::{AppHandle, Emitter};
use tauri_plugin_dialog::DialogExt;
use log::{info, error};
use std::process::Command;
use serde_json::Value;
use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize)]
pub struct SortOptions {
    dry_run: Option<bool>,
    cluster_sensitivity: Option<String>,
    folder_naming_style: Option<String>,
    include_subfolders: Option<bool>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct PipelineProgress {
    status: String,
    message: String,
    progress: u32,
    stages_completed: u32,
    total_stages: u32,
    files_processed: u32,
    clusters_found: u32,
    errors: Vec<String>,
}

fn get_python_executable() -> String {
    let project_root = std::env::current_dir()
        .unwrap()
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .join("backend")
        .join("fileSortVenv");

    let python_path = if cfg!(target_os = "windows") {
        project_root.join("Scripts").join("python.exe")
    } else {
        project_root.join("bin").join("python")
    };

    python_path.to_string_lossy().to_string()
}

fn get_backend_dir() -> String {
    let backend_dir = std::env::current_dir()
        .unwrap()
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .join("backend");

    backend_dir.to_string_lossy().to_string()
}

// ── New event-streaming pipeline command ────────────────────────────────────

#[tauri::command]
pub async fn start_sort(
    app_handle: AppHandle,
    folder_path: String,
    watch_mode: bool,
    preview_mode: bool,
) -> Result<(), String> {
    info!("start_sort called: folder={} watch={} preview={}", folder_path, watch_mode, preview_mode);

    let python_exe = get_python_executable();
    let backend_dir = get_backend_dir();

    // Spawn in a background thread so this command returns immediately.
    // The thread streams NDJSON events from Python stdout and re-emits them as Tauri events.
    std::thread::spawn(move || {
        let mut cmd = Command::new(&python_exe);
        cmd.arg("pipeline/tauri_pipeline.py")
            .arg("--stream-events")
            .arg(&folder_path)
            .current_dir(&backend_dir)
            .env("SMARTSORT_DEV", "1")
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped());

        if preview_mode {
            cmd.arg("--dry-run");
        }

        let mut child = match cmd.spawn() {
            Ok(c) => c,
            Err(e) => {
                error!("Failed to spawn python: {}", e);
                let _ = app_handle.emit("sort-error", serde_json::json!({
                    "code": "spawn_error",
                    "message": e.to_string()
                }));
                return;
            }
        };

        // Drain stderr in a background thread so the pipe buffer never fills and blocks Python.
        if let Some(stderr) = child.stderr.take() {
            std::thread::spawn(move || {
                use std::io::Read;
                let mut reader = std::io::BufReader::new(stderr);
                let mut buf = Vec::new();
                let _ = reader.read_to_end(&mut buf);
            });
        }

        if let Some(stdout) = child.stdout.take() {
            use std::io::BufRead;
            let reader = std::io::BufReader::new(stdout);
            for line in reader.lines() {
                match line {
                    Ok(line) if !line.trim().is_empty() => {
                        match serde_json::from_str::<Value>(&line) {
                            Ok(obj) => {
                                let event_name = obj["event"].as_str().unwrap_or("unknown").to_string();
                                let payload = obj["payload"].clone();
                                info!("Emitting event: {}", event_name);
                                let _ = app_handle.emit(&event_name, payload);
                            }
                            Err(e) => {
                                // Not JSON — log it but don't crash
                                info!("Non-JSON stdout line: {} ({})", line, e);
                            }
                        }
                    }
                    Ok(_) => {}
                    Err(e) => {
                        error!("stdout read error: {}", e);
                        break;
                    }
                }
            }
        }

        match child.wait() {
            Ok(status) if !status.success() => {
                error!("Python pipeline exited with status: {}", status);
                let _ = app_handle.emit("sort-error", format!("Pipeline exited with status {}", status));
            }
            Err(e) => error!("Failed to wait for python: {}", e),
            _ => {}
        }
    });

    Ok(())
}

// ── Preview / confirm / undo ─────────────────────────────────────────────────

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct FileAssignment {
    pub filename: String,
    pub cluster_id: i32,
    pub folder_name: String,
}

#[tauri::command]
pub async fn confirm_sort(preview_folders: Vec<Value>) -> Result<(), String> {
    info!("confirm_sort called with {} folders", preview_folders.len());
    // TODO: apply preview_folders to disk via Python
    Ok(())
}

#[tauri::command]
pub async fn reassign_files(
    filenames: Vec<String>,
    exclude_cluster_id: i32,
) -> Result<Vec<FileAssignment>, String> {
    info!("reassign_files called: {} files, excluding cluster {}", filenames.len(), exclude_cluster_id);
    let python_exe = get_python_executable();
    let backend_dir = get_backend_dir();

    let files_json = serde_json::to_string(&filenames)
        .map_err(|e| e.to_string())?;

    let output = Command::new(&python_exe)
        .args(["-m", "backend.daemon.reassign_cli"])
        .arg("--files-json")
        .arg(&files_json)
        .arg("--exclude")
        .arg(exclude_cluster_id.to_string())
        .current_dir(&backend_dir)
        .output()
        .map_err(|e| format!("Failed to run reassign_cli: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Reassign failed: {}", stderr));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str::<Vec<FileAssignment>>(&stdout)
        .map_err(|e| format!("Failed to parse reassign result: {}", e))
}

#[tauri::command]
pub async fn undo_sort() -> Result<(), String> {
    info!("undo_sort called");
    let python_exe = get_python_executable();
    let backend_dir = get_backend_dir();

    let output = Command::new(&python_exe)
        .arg("pipeline/tauri_pipeline.py")
        .arg("--undo")
        .current_dir(&backend_dir)
        .output()
        .map_err(|e| format!("Failed to run python: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Undo failed: {}", stderr));
    }

    Ok(())
}

// ── Daemon ───────────────────────────────────────────────────────────────────

#[tauri::command]
pub async fn get_daemon_status() -> Result<Value, String> {
    info!("get_daemon_status called");
    let python_exe = get_python_executable();
    let backend_dir = get_backend_dir();

    let output = Command::new(&python_exe)
        .arg("pipeline/tauri_pipeline.py")
        .arg("--daemon-status")
        .current_dir(&backend_dir)
        .output()
        .map_err(|e| format!("Failed to run python: {}", e))?;

    if !output.status.success() {
        // Return a safe default if the daemon isn't running yet
        return Ok(serde_json::json!({
            "running": false,
            "watchedFolders": [],
            "recentActivity": []
        }));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&stdout)
        .map_err(|e| format!("Failed to parse daemon status: {}", e))
}

#[tauri::command]
pub async fn start_daemon(folders: Vec<String>) -> Result<(), String> {
    info!("start_daemon called with {} folders", folders.len());
    let python_exe = get_python_executable();
    let backend_dir = get_backend_dir();

    let folders_json = serde_json::to_string(&folders)
        .map_err(|e| e.to_string())?;

    Command::new(&python_exe)
        .arg("pipeline/tauri_pipeline.py")
        .arg("--start-daemon")
        .arg(&folders_json)
        .current_dir(&backend_dir)
        .spawn()
        .map_err(|e| format!("Failed to start daemon: {}", e))?;

    Ok(())
}

#[tauri::command]
pub async fn stop_daemon() -> Result<(), String> {
    info!("stop_daemon called");
    let python_exe = get_python_executable();
    let backend_dir = get_backend_dir();

    Command::new(&python_exe)
        .arg("pipeline/tauri_pipeline.py")
        .arg("--stop-daemon")
        .current_dir(&backend_dir)
        .output()
        .map_err(|e| format!("Failed to stop daemon: {}", e))?;

    Ok(())
}

// ── License ──────────────────────────────────────────────────────────────────

#[tauri::command]
pub async fn activate_license(key: String) -> Result<(), String> {
    info!("activate_license called");
    let python_exe = get_python_executable();
    let backend_dir = get_backend_dir();

    let output = Command::new(&python_exe)
        .arg("pipeline/tauri_pipeline.py")
        .arg("--activate")
        .arg(&key)
        .current_dir(&backend_dir)
        .output()
        .map_err(|e| format!("Failed to run python: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let result: Value = serde_json::from_str(&stdout)
        .map_err(|e| format!("Failed to parse response: {}", e))?;

    if result["status"].as_str() == Some("activated") {
        Ok(())
    } else {
        Err(result["message"].as_str().unwrap_or("Activation failed").to_string())
    }
}

#[tauri::command]
pub async fn get_license_status() -> Result<Value, String> {
    info!("get_license_status called");
    let python_exe = get_python_executable();
    let backend_dir = get_backend_dir();

    let output = Command::new(&python_exe)
        .arg("pipeline/tauri_pipeline.py")
        .arg("--license-status")
        .current_dir(&backend_dir)
        .output()
        .map_err(|e| format!("Failed to run python: {}", e))?;

    if !output.status.success() {
        return Ok(serde_json::json!({ "valid": true, "trial": false }));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&stdout)
        .map_err(|e| format!("Failed to parse license status: {}", e))
}

// ── Legacy synchronous commands (kept for compatibility) ─────────────────────

#[tauri::command]
pub async fn select_files(app_handle: AppHandle) -> Result<Vec<String>, String> {
    info!("select_files command called");
    let (tx, rx) = tokio::sync::oneshot::channel();

    app_handle.dialog().file().pick_files(move |file_paths| {
        let paths = file_paths.map(|paths| paths.into_iter().map(|p| p.to_string()).collect());
        let _ = tx.send(paths);
    });

    match rx.await {
        Ok(Some(paths)) => Ok(paths),
        Ok(None) => Err("No files selected".to_string()),
        Err(_) => Err("Failed to receive file selection".to_string()),
    }
}

#[tauri::command]
pub async fn select_folder(app_handle: AppHandle) -> Result<String, String> {
    info!("select_folder command called");
    let (tx, rx) = tokio::sync::oneshot::channel();

    app_handle.dialog().file().pick_folder(move |folder_path| {
        let path = folder_path.map(|p| p.to_string());
        let _ = tx.send(path);
    });

    match rx.await {
        Ok(Some(path)) => Ok(path),
        Ok(None) => Err("No folder selected".to_string()),
        Err(_) => Err("Failed to receive folder selection".to_string()),
    }
}

#[tauri::command]
pub async fn preview_sort(folder_path: String, _options: Option<SortOptions>) -> Result<Value, String> {
    info!("preview_sort called: {}", folder_path);
    let python_exe = get_python_executable();
    let backend_dir = get_backend_dir();

    let output = Command::new(&python_exe)
        .arg("pipeline/tauri_pipeline.py")
        .arg("--preview")
        .arg(&folder_path)
        .current_dir(&backend_dir)
        .output()
        .map_err(|e| format!("Failed to run python: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Pipeline error: {}", stderr));
    }

    serde_json::from_str(&String::from_utf8_lossy(&output.stdout))
        .map_err(|e| format!("Failed to parse response: {}", e))
}

#[tauri::command]
pub async fn run_sort(folder_path: String, options: Option<SortOptions>) -> Result<Value, String> {
    info!("run_sort called: {}", folder_path);
    let python_exe = get_python_executable();
    let backend_dir = get_backend_dir();

    let mut command = Command::new(&python_exe);
    command.arg("pipeline/tauri_pipeline.py")
        .arg(&folder_path)
        .current_dir(&backend_dir);

    if let Some(opts) = &options {
        if opts.dry_run.unwrap_or(false) {
            command.arg("--dry-run");
        }
    }

    let output = command.output()
        .map_err(|e| format!("Failed to run python: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Pipeline error: {}", stderr));
    }

    serde_json::from_str(&String::from_utf8_lossy(&output.stdout))
        .map_err(|e| format!("Failed to parse response: {}", e))
}
