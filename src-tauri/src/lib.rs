use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;
use tauri::{
    menu::{MenuBuilder, MenuItemBuilder, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager, WindowEvent,
};

// ─── embedded tray icons (colored circles, 32x32 PNG) ───

const TRAY_GRAY: &[u8] = include_bytes!("../icons/tray-gray.png");
const TRAY_GREEN: &[u8] = include_bytes!("../icons/tray-green.png");
const TRAY_YELLOW: &[u8] = include_bytes!("../icons/tray-yellow.png");
const TRAY_RED: &[u8] = include_bytes!("../icons/tray-red.png");

fn tray_icon_bytes(color: &str) -> &'static [u8] {
    match color {
        "green" => TRAY_GREEN,
        "yellow" => TRAY_YELLOW,
        "red" => TRAY_RED,
        _ => TRAY_GRAY,
    }
}

// ─── sidecar management ───

struct SidecarProcess(Arc<Mutex<Option<std::process::Child>>>);

fn spawn_python_backend() -> Option<std::process::Child> {
    // candidate paths: release bundle, dev binaries, dist fallback
    let mut candidates: Vec<std::path::PathBuf> = Vec::new();

    // 1. next to the exe (release bundle)
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            candidates.push(dir.join("python-sidecar.exe"));
        }
    }

    // 2. src-tauri/binaries/ (dev mode, built by PyInstaller)
    if let Ok(manifest) = std::env::var("CARGO_MANIFEST_DIR") {
        candidates.push(
            std::path::PathBuf::from(&manifest).join("binaries").join("python-sidecar.exe"),
        );
    }

    // 3. project dist/ fallback
    if let Ok(manifest) = std::env::var("CARGO_MANIFEST_DIR") {
        candidates.push(
            std::path::PathBuf::from(&manifest)
                .parent()
                .map(|p| p.join("dist").join("python-sidecar.exe"))
                .unwrap_or_default(),
        );
    }

    let path = candidates.iter().find(|p| p.exists()).cloned();

    match path {
        Some(ref p) => println!("[tauri] starting Python sidecar: {:?}", p),
        None => {
            eprintln!("[tauri] Python sidecar not found (checked {:?})", candidates);
            return None;
        }
    }

    std::process::Command::new(path.unwrap())
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::inherit())
        .stderr(std::process::Stdio::inherit())
        .spawn()
        .ok()
}

fn kill_sidecar(state: &SidecarProcess) {
    if let Some(mut child) = state.0.lock().unwrap().take() {
        let _ = child.kill();
        let _ = child.wait();
        println!("[tauri] Python sidecar terminated");
    }
}

// ─── tray status polling ───

fn start_status_poller(app: AppHandle) {
    thread::spawn(move || {
        // give the Python sidecar time to start
        thread::sleep(Duration::from_secs(4));

        loop {
            thread::sleep(Duration::from_secs(10));

            // call Python API to check status
            let color = match ureq::get("http://127.0.0.1:8899/api/stats")
                .call()
                .ok()
                .and_then(|r| r.into_json::<serde_json::Value>().ok())
            {
                Some(stats) => {
                    let running = stats["running"].as_u64().unwrap_or(0);
                    let total = stats["total"].as_u64().unwrap_or(0);
                    if running > 0 {
                        "green"
                    } else if total > 0 {
                        "gray"
                    } else {
                        "gray"
                    }
                }
                None => "gray",
            };

            // update tray icon
            if let Some(tray) = app.tray_by_id("main-tray") {
                if let Ok(icon) = tauri::image::Image::from_bytes(tray_icon_bytes(color)) {
                    let _ = tray.set_icon(Some(icon));
                }
            }
        }
    });
}

// ─── application entry ───

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_process::init())
        .manage(SidecarProcess(Arc::new(Mutex::new(None))))
        .setup(|app| {
            // 1. spawn Python sidecar
            let child = spawn_python_backend();
            let state = app.state::<SidecarProcess>();
            *state.0.lock().unwrap() = child;

            // 2. build tray menu
            let show = MenuItemBuilder::with_id("show", "打开面板").build(app)?;
            let status_item = MenuItemBuilder::with_id("status", "状态摘要").build(app)?;
            let quit = MenuItemBuilder::with_id("quit", "退出 AutoDL Manager").build(app)?;

            let menu = MenuBuilder::new(app)
                .item(&show)
                .item(&status_item)
                .item(&PredefinedMenuItem::separator(app)?)
                .item(&quit)
                .build()?;

            let default_icon =
                tauri::image::Image::from_bytes(TRAY_GRAY).expect("tray icon");

            let _tray = TrayIconBuilder::with_id("main-tray")
                .icon(default_icon)
                .menu(&menu)
                .tooltip("AutoDL Manager")
                .on_menu_event(|app, event| match event.id().as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.unminimize();
                            let _ = window.set_focus();
                        }
                    }
                    "status" => {
                        // show a quick summary by opening the window
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.unminimize();
                            let _ = window.set_focus();
                        }
                    }
                    "quit" => {
                        let state = app.state::<SidecarProcess>();
                        kill_sidecar(&state);
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.unminimize();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(app)?;

            // 3. background: poll Python API for tray status
            start_status_poller(app.handle().clone());

            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("failed to launch AutoDL Manager");
}
