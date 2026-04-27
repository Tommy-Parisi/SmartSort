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

fn home_dir() -> Option<std::path::PathBuf> {
    #[cfg(target_os = "windows")]
    { std::env::var("USERPROFILE").ok().map(std::path::PathBuf::from) }
    #[cfg(not(target_os = "windows"))]
    { std::env::var("HOME").ok().map(std::path::PathBuf::from) }
}

fn python_in_venv(venv: &std::path::Path) -> std::path::PathBuf {
    if cfg!(target_os = "windows") {
        venv.join("Scripts").join("python.exe")
    } else {
        venv.join("bin").join("python")
    }
}

// Returns the exe path, resolving symlinks so we get the real binary location.
fn real_exe() -> Option<std::path::PathBuf> {
    std::env::current_exe().ok().and_then(|p| std::fs::canonicalize(p).ok())
}

fn get_python_executable() -> String {
    // 1. Explicit override — useful for testing or non-standard setups.
    if let Ok(p) = std::env::var("SMARTSORT_PYTHON") {
        if std::path::Path::new(&p).exists() {
            return p;
        }
    }

    // 2. User-level venv created by the installer (~/.smartsort/venv).
    //    This is the expected location in a packaged app.
    if let Some(home) = home_dir() {
        let p = python_in_venv(&home.join(".smartsort").join("venv"));
        if p.exists() {
            return p.to_string_lossy().to_string();
        }
    }

    // 3. Dev venv: resolve from the real exe path.
    //    In dev the binary is at <project>/frontend/src-tauri/target/{debug|release}/<name>
    //    Going up 4 parents reaches the project root, then into backend/fileSortVenv.
    if let Some(exe) = real_exe() {
        if let Some(venv) = exe.parent()       // {debug|release}/
            .and_then(|p| p.parent())          // target/
            .and_then(|p| p.parent())          // src-tauri/
            .and_then(|p| p.parent())          // frontend/
            .and_then(|p| p.parent())          // project root
            .map(|root| root.join("backend").join("fileSortVenv"))
        {
            let p = python_in_venv(&venv);
            if p.exists() {
                return p.to_string_lossy().to_string();
            }
        }
    }

    // 4. Last resort — system python3.
    "python3".to_string()
}

fn get_backend_dir() -> String {
    // 1. Explicit override.
    if let Ok(p) = std::env::var("SMARTSORT_BACKEND") {
        if std::path::Path::new(&p).exists() {
            return p;
        }
    }

    if let Some(exe) = real_exe() {
        // 2. Bundled app resources: <app>.app/Contents/MacOS/<binary>
        //    Resources live at <app>.app/Contents/Resources/backend
        if let Some(bundle_backend) = exe.parent()   // MacOS/
            .and_then(|p| p.parent())                // Contents/
            .map(|p| p.join("Resources").join("backend"))
        {
            if bundle_backend.join("pipeline").exists() {
                return bundle_backend.to_string_lossy().to_string();
            }
        }

        // 3. Dev path: project root / backend
        if let Some(dev_backend) = exe.parent()    // {debug|release}/
            .and_then(|p| p.parent())              // target/
            .and_then(|p| p.parent())              // src-tauri/
            .and_then(|p| p.parent())              // frontend/
            .and_then(|p| p.parent())              // project root
            .map(|root| root.join("backend"))
        {
            if dev_backend.exists() {
                return dev_backend.to_string_lossy().to_string();
            }
        }
    }

    // 4. Original cwd-relative fallback (keeps old dev behaviour if above fails).
    std::env::current_dir()
        .ok()
        .and_then(|d| d.parent().and_then(|p| p.parent().map(|pp| pp.join("backend"))))
        .unwrap_or_else(|| std::path::PathBuf::from("backend"))
        .to_string_lossy()
        .to_string()
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
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped());

        #[cfg(debug_assertions)]
        cmd.env("SMARTSORT_DEV", "1");

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
pub async fn confirm_sort(
    base_folder: String,
    preview_folders: Vec<Value>,
    trashed_filenames: Vec<String>,
) -> Result<(), String> {
    info!("confirm_sort called: {} folders, {} trashed, base={}", preview_folders.len(), trashed_filenames.len(), base_folder);

    let python_exe = get_python_executable();
    let backend_dir = get_backend_dir();

    let preview_json = serde_json::to_string(&preview_folders)
        .map_err(|e| format!("Failed to serialize preview: {}", e))?;

    let trashed_json = serde_json::to_string(&trashed_filenames)
        .map_err(|e| format!("Failed to serialize trashed: {}", e))?;

    let output = Command::new(&python_exe)
        .args(["-m", "backend.pipeline.tauri_pipeline"])
        .arg("--apply-preview")
        .arg("--base-folder")
        .arg(&base_folder)
        .arg("--preview-json")
        .arg(&preview_json)
        .arg("--trashed-json")
        .arg(&trashed_json)
        .current_dir(&backend_dir)
        .output()
        .map_err(|e| format!("Failed to run apply_preview: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("apply_preview failed: {}", stderr.trim()));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let result: Value = serde_json::from_str(stdout.trim())
        .map_err(|e| format!("Failed to parse result: {}", e))?;

    if result.get("status").and_then(|s| s.as_str()) == Some("error") {
        let msg = result.get("message").and_then(|m| m.as_str()).unwrap_or("Unknown error");
        return Err(msg.to_string());
    }

    if let Some(errors) = result.get("errors").and_then(|e| e.as_array()) {
        if !errors.is_empty() {
            let moved = result.get("moved").and_then(|m| m.as_u64()).unwrap_or(0);
            if moved == 0 {
                return Err(format!("{} error(s), nothing moved", errors.len()));
            }
            error!("confirm_sort partial: {} error(s), {} moved", errors.len(), moved);
        }
    }

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

// ── History ───────────────────────────────────────────────────────────────────

#[derive(Debug, Serialize)]
pub struct SortSession {
    pub folder: String,
    pub date: String,
    pub files_sorted: usize,
    pub folders_created: usize,
    pub session_id: String,
}

fn days_to_date_str(days_since_epoch: i64) -> String {
    // Civil calendar algorithm (no external crates required)
    let z = days_since_epoch + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let _y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    let month_name = months[(m as usize).saturating_sub(1).min(11)];
    format!("{} {}", month_name, d)
}

#[tauri::command]
pub async fn get_history() -> Result<Vec<SortSession>, String> {
    let home = home_dir().ok_or_else(|| "Cannot find home directory".to_string())?;
    let log_path = home.join(".smartsort").join("move_log.jsonl");

    if !log_path.exists() {
        return Ok(vec![]);
    }

    use std::io::{BufRead, BufReader};
    let file = std::fs::File::open(&log_path).map_err(|e| e.to_string())?;
    let reader = BufReader::new(file);

    // (timestamp, source_path, dest_path)
    let mut entries: Vec<(f64, String, String)> = Vec::new();

    for line in reader.lines().flatten() {
        if line.trim().is_empty() { continue; }
        if let Ok(val) = serde_json::from_str::<Value>(&line) {
            let ts = val["timestamp"].as_f64()
                .or_else(|| val["ts"].as_f64())
                .unwrap_or(0.0);
            let source = val["source"].as_str()
                .or_else(|| val["src"].as_str())
                .or_else(|| val["from"].as_str())
                .unwrap_or("")
                .to_string();
            let dest = val["destination"].as_str()
                .or_else(|| val["dest"].as_str())
                .or_else(|| val["to"].as_str())
                .unwrap_or("")
                .to_string();
            if !source.is_empty() {
                entries.push((ts, source, dest));
            }
        }
    }

    if entries.is_empty() {
        return Ok(vec![]);
    }

    entries.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));

    let home_str = home.to_string_lossy().to_string();
    let mut sessions: Vec<SortSession> = Vec::new();
    let mut i = 0;
    let mut session_num: u64 = 0;

    while i < entries.len() {
        let session_start_ts = entries[i].0;
        let mut j = i;
        while j < entries.len() && entries[j].0 - session_start_ts <= 300.0 {
            j += 1;
        }
        let session_entries = &entries[i..j];

        // Derive the sorted folder from the first source path's parent
        let source_path = std::path::Path::new(&session_entries[0].1);
        let folder = source_path
            .parent()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_else(|| session_entries[0].1.clone())
            .replace(&home_str, "~");

        // Count unique destination folders
        let mut dest_folders = std::collections::HashSet::new();
        for (_, _, dest) in session_entries {
            if !dest.is_empty() {
                if let Some(parent) = std::path::Path::new(dest).parent() {
                    dest_folders.insert(parent.to_string_lossy().to_string());
                }
            }
        }

        let days = session_start_ts as i64 / 86400;
        let date = days_to_date_str(days);

        session_num += 1;
        sessions.push(SortSession {
            folder,
            date,
            files_sorted: session_entries.len(),
            folders_created: dest_folders.len(),
            session_id: format!("session_{}", session_num),
        });

        i = j;
    }

    sessions.reverse();
    sessions.truncate(10);
    Ok(sessions)
}

#[tauri::command]
pub async fn open_log_folder() -> Result<(), String> {
    let home = home_dir().ok_or_else(|| "Cannot find home directory".to_string())?;
    let log_dir = home.join(".smartsort");

    if !log_dir.exists() {
        std::fs::create_dir_all(&log_dir).map_err(|e| e.to_string())?;
    }

    #[cfg(target_os = "macos")]
    std::process::Command::new("open")
        .arg(log_dir.to_string_lossy().as_ref())
        .spawn()
        .map_err(|e| e.to_string())?;

    #[cfg(target_os = "windows")]
    std::process::Command::new("explorer")
        .arg(log_dir.to_string_lossy().as_ref())
        .spawn()
        .map_err(|e| e.to_string())?;

    #[cfg(target_os = "linux")]
    std::process::Command::new("xdg-open")
        .arg(log_dir.to_string_lossy().as_ref())
        .spawn()
        .map_err(|e| e.to_string())?;

    Ok(())
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

#[derive(Debug, Serialize, Deserialize)]
pub struct FilePreview {
    pub data: String,
    pub mime_type: String,
}

#[tauri::command]
pub async fn get_file_preview(file_path: String) -> Result<FilePreview, String> {
    info!("get_file_preview called for: {}", file_path);
    use std::io::Read;
    use base64::{Engine as _, engine::general_purpose};

    let path = std::path::Path::new(&file_path);
    let ext = path.extension()
        .and_then(|s| s.to_str())
        .unwrap_or("")
        .to_lowercase();

    let mut file = std::fs::File::open(&file_path)
        .map_err(|e| format!("Failed to open file: {}", e))?;

    let is_text = matches!(ext.as_str(),
        "txt" | "md" | "js" | "ts" | "py" | "json" | "rs" | "css" | "html"
        | "jsx" | "tsx" | "csv" | "sh" | "yaml" | "yml"
    );
    let mut buffer = Vec::new();
    if is_text {
        // Cap text previews at 200 KB — enough to show content without blowing memory.
        let _ = file.take(200_000).read_to_end(&mut buffer)
            .map_err(|e| format!("Failed to read file: {}", e))?;
    } else {
        // Images must be read in full — a truncated JPEG renders as a partial image.
        file.read_to_end(&mut buffer)
            .map_err(|e| format!("Failed to read file: {}", e))?;
    }

    let mime_type = match ext.as_str() {
        "jpg" | "jpeg" => "image/jpeg",
        "png" => "image/png",
        "gif" => "image/gif",
        "webp" => "image/webp",
        "pdf" => "application/pdf",
        "txt" | "md" | "js" | "ts" | "py" | "json" | "rs" | "css" | "html" | "jsx" | "tsx" | "csv" | "sh" | "yaml" | "yml" => "text/plain",
        _ => "application/octet-stream",
    };

    Ok(FilePreview {
        data: general_purpose::STANDARD.encode(&buffer),
        mime_type: mime_type.to_string(),
    })
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
