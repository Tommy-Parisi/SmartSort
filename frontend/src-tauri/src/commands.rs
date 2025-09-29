use tauri::AppHandle;
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

// Helper function to get the correct Python executable path for the platform
fn get_python_executable() -> String {
    // Get the project root directory (assuming we're running from frontend/src-tauri)
    let project_root = std::env::current_dir()
        .unwrap()
        .parent() // go up from src-tauri
        .unwrap()
        .parent() // go up from frontend  
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

// Helper function to get the backend directory path
fn get_backend_dir() -> String {
    let backend_dir = std::env::current_dir()
        .unwrap()
        .parent() // go up from src-tauri
        .unwrap()
        .parent() // go up from frontend
        .unwrap()
        .join("backend");
    
    backend_dir.to_string_lossy().to_string()
}

#[tauri::command]
pub async fn select_files(app_handle: AppHandle) -> Result<Vec<String>, String> {
    info!("select_files command called");
    let (tx, rx) = tokio::sync::oneshot::channel();
    
    app_handle.dialog().file().pick_files(move |file_paths| {
        info!("Dialog callback received: {:?}", file_paths);
        let paths = file_paths.map(|paths| paths.into_iter().map(|p| p.to_string()).collect());
        let _ = tx.send(paths);
    });
    
    match rx.await {
        Ok(Some(paths)) => {
            info!("Files selected successfully: {:?}", paths);
            Ok(paths)
        }
        Ok(None) => {
            info!("No files selected (user cancelled)");
            Err("No files selected".to_string())
        }
        Err(_) => {
            error!("Failed to receive file selection response");
            Err("Failed to receive file selection".to_string())
        }
    }
}

#[tauri::command]
pub async fn preview_sort(folder_path: String, _options: Option<SortOptions>) -> Result<Value, String> {
    info!("preview_sort command called for folder: {}", folder_path);
    
    let python_exe = get_python_executable();
    let backend_dir = get_backend_dir();
    info!("Using Python executable: {}", python_exe);
    info!("Using backend directory: {}", backend_dir);
    
    let mut command = Command::new(&python_exe);
    command.arg("pipeline/tauri_pipeline.py")
        .arg("--preview")
        .arg(&folder_path)
        .current_dir(&backend_dir);
    
    let output = command.output()
        .map_err(|e| format!("Failed to run python: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let stdout = String::from_utf8_lossy(&output.stdout);
        error!("Python stderr: {}", stderr);
        error!("Python stdout: {}", stdout);
        return Err(format!("Pipeline error: {}\nStdout: {}", stderr, stdout));
    }

    let full_output = String::from_utf8_lossy(&output.stdout);
    info!("Preview output: {}", full_output);
    
    // Parse JSON response from the pipeline
    serde_json::from_str(&full_output)
        .map_err(|e| format!("Failed to parse preview response: {} - output: {}", e, full_output))
}

#[tauri::command]
pub async fn run_sort(folder_path: String, options: Option<SortOptions>) -> Result<Value, String> {
    info!("run_sort command called for folder: {} with options: {:?}", folder_path, options);
    
    let python_exe = get_python_executable();
    let backend_dir = get_backend_dir();
    info!("Using Python executable: {}", python_exe);
    info!("Using backend directory: {}", backend_dir);
    
    let mut command = Command::new(&python_exe);
    command.arg("pipeline/tauri_pipeline.py")
        .arg(&folder_path)
        .current_dir(&backend_dir);
    
    // Add dry-run option if specified
    if let Some(opts) = &options {
        if opts.dry_run.unwrap_or(false) {
            command.arg("--dry-run");
        }
    }
    
    let output = command.output()
        .map_err(|e| format!("Failed to run python: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let stdout = String::from_utf8_lossy(&output.stdout);
        error!("Pipeline stderr: {}", stderr);
        error!("Pipeline stdout: {}", stdout);
        return Err(format!("Pipeline error: {}\nStdout: {}", stderr, stdout));
    }

    let full_output = String::from_utf8_lossy(&output.stdout);
    info!("Pipeline output: {}", full_output);
    
    // Parse the JSON response from the pipeline
    serde_json::from_str(&full_output)
        .map_err(|e| format!("Failed to parse pipeline response: {} - output: {}", e, full_output))
}

#[tauri::command]
pub async fn run_sort_with_progress(folder_path: String, options: Option<SortOptions>) -> Result<Value, String> {
    info!("run_sort_with_progress command called for folder: {} with options: {:?}", folder_path, options);
    
    let python_exe = get_python_executable();
    let backend_dir = get_backend_dir();
    info!("Using Python executable: {}", python_exe);
    info!("Using backend directory: {}", backend_dir);
    
    let mut command = Command::new(&python_exe);
    command.arg("pipeline/tauri_pipeline.py")
        .arg(&folder_path)
        .current_dir(&backend_dir);
    
    // Add dry-run option if specified
    if let Some(opts) = &options {
        if opts.dry_run.unwrap_or(false) {
            command.arg("--dry-run");
        }
    }
    
    let output = command.output()
        .map_err(|e| format!("Failed to run python: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let stdout = String::from_utf8_lossy(&output.stdout);
        error!("Pipeline stderr: {}", stderr);
        error!("Pipeline stdout: {}", stdout);
        return Err(format!("Pipeline error: {}\nStdout: {}", stderr, stdout));
    }

    let full_output = String::from_utf8_lossy(&output.stdout);
    info!("Pipeline output: {}", full_output);
    
    // Parse the JSON response from the pipeline
    serde_json::from_str(&full_output)
        .map_err(|e| format!("Failed to parse pipeline response: {} - output: {}", e, full_output))
}
#[tauri::command]
pub async fn select_folder(app_handle: AppHandle) -> Result<String, String> {
    info!("select_folder command called");
    let (tx, rx) = tokio::sync::oneshot::channel();
    
    app_handle.dialog().file().pick_folder(move |folder_path| {
        info!("Folder dialog callback received: {:?}", folder_path);
        let path = folder_path.map(|p| p.to_string());
        let _ = tx.send(path);
    });
    
    match rx.await {
        Ok(Some(path)) => {
            info!("Folder selected successfully: {:?}", path);
            Ok(path)
        }
        Ok(None) => {
            info!("No folder selected (user cancelled)");
            Err("No folder selected".to_string())
        }
        Err(_) => {
            error!("Failed to receive folder selection response");
            Err("Failed to receive folder selection".to_string())
        }
    }
}
