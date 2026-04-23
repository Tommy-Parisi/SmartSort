mod commands;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            // New streaming pipeline
            commands::start_sort,
            commands::confirm_sort,
            commands::reassign_files,
            commands::undo_sort,
            // Daemon
            commands::get_daemon_status,
            commands::start_daemon,
            commands::stop_daemon,
            // License
            commands::activate_license,
            commands::get_license_status,
            // Legacy
            commands::select_files,
            commands::select_folder,
            commands::preview_sort,
            commands::get_file_preview,
            commands::run_sort,
        ])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
