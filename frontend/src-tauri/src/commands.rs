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
pub async fn preview_sort(folder_path: String, options: serde_json::Value) -> Result<u32, String> {
    info!("preview_sort command called for folder: {}", folder_path);
    
    // For now, return a mock cluster count
    // In the future, this could integrate with the Python backend
    let cluster_count = 5;
    info!("Preview returning {} clusters", cluster_count);
    
    Ok(cluster_count)
} 