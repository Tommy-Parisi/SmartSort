use tauri::AppHandle;
use tauri_plugin_dialog::DialogExt;
use log::{info, error};
use std::process::Command;
use serde_json::Value;
use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize)]
pub struct SortOptions {
    cluster_sensitivity: Option<String>,
    folder_naming_style: Option<String>,
    include_subfolders: Option<bool>,
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
pub async fn preview_sort(folder_path: String, options: Option<SortOptions>) -> Result<u32, String> {
    info!("preview_sort command called for folder: {} with options: {:?}", folder_path, options);
    
    let mut command = Command::new("/opt/homebrew/bin/python3");
    command.arg("sorter.py")
        .arg(&folder_path)
        .arg("--preview")
        .current_dir("../backend")
        .env("PYTHONPATH", "/Users/tommy/Desktop/FileSort/backend/fileSortVenv/lib/python3.11/site-packages");
    
    // Add options if provided
    if let Some(opts) = options {
        if let Some(sensitivity) = opts.cluster_sensitivity {
            command.arg("--sensitivity").arg(sensitivity);
        }
        if let Some(naming_style) = opts.folder_naming_style {
            command.arg("--naming-style").arg(naming_style);
        }
        if let Some(include_subfolders) = opts.include_subfolders {
            if include_subfolders {
                command.arg("--include-subfolders");
            } else {
                command.arg("--no-subfolders");
            }
        }
    }
    
    let output = command.output()
        .map_err(|e| format!("Failed to run python: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let stdout = String::from_utf8_lossy(&output.stdout);
        error!("Python stderr: {}", stderr);
        error!("Python stdout: {}", stdout);
        return Err(format!("Python error: {}\nStdout: {}", stderr, stdout));
    }

    let count_str = String::from_utf8_lossy(&output.stdout).trim().to_string();
    info!("Preview result: {}", count_str);
    count_str.parse::<u32>().map_err(|e| format!("Parse error: {}", e))
}

#[tauri::command]
pub async fn run_sort(folder_path: String, options: Option<SortOptions>) -> Result<Value, String> {
    info!("run_sort command called for folder: {} with options: {:?}", folder_path, options);
    
    let mut command = Command::new("/opt/homebrew/bin/python3");
    command.arg("sorter.py")
        .arg(&folder_path)
        .arg("--json")
        .current_dir("../backend")
        .env("PYTHONPATH", "/Users/tommy/Desktop/FileSort/backend/fileSortVenv/lib/python3.11/site-packages");
    
    // Add options if provided
    if let Some(opts) = options {
        if let Some(sensitivity) = opts.cluster_sensitivity {
            command.arg("--sensitivity").arg(sensitivity);
        }
        if let Some(naming_style) = opts.folder_naming_style {
            command.arg("--naming-style").arg(naming_style);
        }
        if let Some(include_subfolders) = opts.include_subfolders {
            if include_subfolders {
                command.arg("--include-subfolders");
            } else {
                command.arg("--no-subfolders");
            }
        }
    }
    
    let output = command.output()
        .map_err(|e| format!("Failed to run python: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let stdout = String::from_utf8_lossy(&output.stdout);
        error!("Python stderr: {}", stderr);
        error!("Python stdout: {}", stdout);
        return Err(format!("Python error: {}\nStdout: {}", stderr, stdout));
    }

    let json_str = String::from_utf8_lossy(&output.stdout);
    info!("Sort result JSON: {}", json_str);
    serde_json::from_str(&json_str).map_err(|e| format!("JSON parse error: {}", e))
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
