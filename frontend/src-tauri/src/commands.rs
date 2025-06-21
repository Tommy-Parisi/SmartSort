use tauri::AppHandle;
use tauri_plugin_dialog::DialogExt;
use log::{info, error};

#[tauri::command]
pub async fn select_folder(app_handle: AppHandle) -> Result<String, String> {
    info!("select_folder command called");
    let (tx, rx) = tokio::sync::oneshot::channel();
    
    app_handle.dialog().file().pick_folder(move |folder_path| {
        info!("Dialog callback received: {:?}", folder_path);
        let _ = tx.send(folder_path.map(|p| p.to_string()));
    });
    
    match rx.await {
        Ok(Some(path)) => {
            info!("Folder selected successfully: {}", path);
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
pub async fn preview_sort(folder_path: String, _options: serde_json::Value) -> Result<u32, String> {
    info!("preview_sort command called for folder: {}", folder_path);
    
    // For now, return a mock cluster count
    // In the future, this could integrate with the Python backend
    let cluster_count = 5;
    info!("Preview returning {} clusters", cluster_count);
    
    Ok(cluster_count)
} 