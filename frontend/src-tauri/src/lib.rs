//! loom2 shell (06 §1): supervises the orchestrator sidecar, performs the READY handshake, hands the per-launch
//! token to the webview through `backend_info`, shuts the orchestrator down gracefully on exit (which in turn
//! stops the engine), and keeps a single instance.

use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tauri::{AppHandle, Manager, State, WindowEvent};

#[derive(Default, Clone, Serialize)]
pub struct BackendInfo {
    pub ready: bool,
    pub port: u16,
    pub host: String,
    pub token: String,
    pub error: Option<String>,
    pub log_tail: Vec<String>,
}

#[derive(Deserialize)]
struct ReadyLine {
    port: u16,
    host: String,
    token: String,
}

#[derive(Default)]
pub struct Backend {
    info: Mutex<BackendInfo>,
    child: Mutex<Option<Child>>,
}

type Shared = Arc<Backend>;

fn repo_root() -> PathBuf {
    if let Ok(p) = std::env::var("LOOM2_REPO") {
        return PathBuf::from(p);
    }
    // <repo>/frontend/src-tauri at build time (dev builds on the author's machine); release builds set LOOM2_REPO
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().and_then(|p| p.parent()).map(|p| p.to_path_buf()).unwrap_or_default()
}

fn orchestrator_command(port: u16) -> (String, Vec<String>, PathBuf) {
    let root = repo_root();
    let orch_dir = root.join("orchestrator");
    if let Ok(cmd) = std::env::var("LOOM2_ORCH_CMD") {
        let mut parts = cmd.split_whitespace().map(String::from);
        let exe = parts.next().unwrap_or_default();
        let mut args: Vec<String> = parts.collect();
        args.extend(["--port".into(), port.to_string()]);
        return (exe, args, orch_dir);
    }
    let exe = orch_dir.join(".venv").join("Scripts").join("python.exe");
    (exe.to_string_lossy().into_owned(), vec!["-m".into(), "loom2.main".into(), "--port".into(), port.to_string()], orch_dir)
}

fn push_log(info: &Mutex<BackendInfo>, line: String) {
    let mut g = info.lock().unwrap();
    g.log_tail.push(line);
    let n = g.log_tail.len();
    if n > 200 {
        g.log_tail.drain(0..n - 200);
    }
}

fn spawn_backend(backend: Shared) {
    let port: u16 = std::env::var("LOOM2_PORT").ok().and_then(|p| p.parse().ok()).unwrap_or(8765);
    let (exe, args, cwd) = orchestrator_command(port);
    let mut cmd = Command::new(&exe);
    cmd.args(&args).current_dir(&cwd).env("PYTHONIOENCODING", "utf-8").env("PYTHONUNBUFFERED", "1").stdout(Stdio::piped()).stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    let mut child = match cmd.spawn() {
        Ok(c) => c,
        Err(e) => {
            backend.info.lock().unwrap().error = Some(format!("could not start the orchestrator `{exe}`: {e}"));
            return;
        }
    };
    assign_kill_on_close(&child);
    let stdout = child.stdout.take();
    let stderr = child.stderr.take();
    *backend.child.lock().unwrap() = Some(child);
    if let Some(err) = stderr {
        let b = backend.clone();
        std::thread::spawn(move || {
            for line in BufReader::new(err).lines().map_while(Result::ok) {
                push_log(&b.info, line);
            }
        });
    }
    if let Some(out) = stdout {
        let b = backend.clone();
        std::thread::spawn(move || {
            for line in BufReader::new(out).lines().map_while(Result::ok) {
                if let Some(json) = line.strip_prefix("LOOM2_READY ") {
                    match serde_json::from_str::<ReadyLine>(json) {
                        Ok(r) => {
                            let mut g = b.info.lock().unwrap();
                            g.ready = true;
                            g.port = r.port;
                            g.host = r.host;
                            g.token = r.token;
                            g.error = None;
                        }
                        Err(e) => b.info.lock().unwrap().error = Some(format!("bad READY line: {e}")),
                    }
                } else {
                    push_log(&b.info, line);
                }
            }
            // stdout closed: the orchestrator exited
            let mut g = b.info.lock().unwrap();
            if g.ready {
                g.ready = false;
                g.error = Some("the orchestrator exited".into());
            } else if g.error.is_none() {
                g.error = Some("the orchestrator exited before READY (see log_tail)".into());
            }
        });
    }
}

/// Windows Job Object with KILL_ON_JOB_CLOSE: if the shell dies hard, the orchestrator dies with it (and the
/// engine with the orchestrator, which holds its own job object). The handle is leaked on purpose: it must
/// live as long as the process.
#[cfg(windows)]
fn assign_kill_on_close(child: &Child) {
    use std::os::windows::io::AsRawHandle;
    #[repr(C)]
    struct IoCounters { _c: [u64; 6] }
    #[repr(C)]
    struct BasicLimit { per_process_user_time: i64, per_job_user_time: i64, limit_flags: u32, min_ws: usize, max_ws: usize, active_process_limit: u32, affinity: usize, priority_class: u32, scheduling_class: u32 }
    #[repr(C)]
    struct ExtendedLimit { basic: BasicLimit, io: IoCounters, process_memory_limit: usize, job_memory_limit: usize, peak_process_memory: usize, peak_job_memory: usize }
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn CreateJobObjectW(attrs: *const std::ffi::c_void, name: *const u16) -> *mut std::ffi::c_void;
        fn SetInformationJobObject(job: *mut std::ffi::c_void, class: i32, info: *const std::ffi::c_void, len: u32) -> i32;
        fn AssignProcessToJobObject(job: *mut std::ffi::c_void, process: *mut std::ffi::c_void) -> i32;
    }
    const JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: u32 = 0x2000;
    const JOB_OBJECT_EXTENDED_LIMIT_INFORMATION: i32 = 9;
    unsafe {
        let job = CreateJobObjectW(std::ptr::null(), std::ptr::null());
        if job.is_null() {
            return;
        }
        let mut info: ExtendedLimit = std::mem::zeroed();
        info.basic.limit_flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        let ok = SetInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, &info as *const _ as *const _, std::mem::size_of::<ExtendedLimit>() as u32);
        if ok != 0 {
            AssignProcessToJobObject(job, child.as_raw_handle() as _);
        }
    }
}

#[cfg(not(windows))]
fn assign_kill_on_close(_child: &Child) {}

/// POST /shutdown, wait for the child to exit, kill it if it will not. Returns how it ended.
fn shutdown_backend(backend: &Backend, grace: Duration) -> String {
    let (ready, host, port, token) = {
        let g = backend.info.lock().unwrap();
        (g.ready, g.host.clone(), g.port, g.token.clone())
    };
    if ready {
        let url = format!("http://{host}:{port}/shutdown");
        let _ = ureq::post(&url).header("X-Loom-Token", &token).config().http_status_as_error(false).build().send_empty();
    }
    let t0 = Instant::now();
    let mut guard = backend.child.lock().unwrap();
    if let Some(child) = guard.as_mut() {
        loop {
            match child.try_wait() {
                Ok(Some(status)) => return format!("exited {status}"),
                Ok(None) if t0.elapsed() < grace => std::thread::sleep(Duration::from_millis(100)),
                _ => {
                    let _ = child.kill();
                    let _ = child.wait();
                    return "killed after grace".into();
                }
            }
        }
    }
    "no child".into()
}

#[tauri::command]
fn backend_info(backend: State<'_, Shared>) -> BackendInfo {
    backend.info.lock().unwrap().clone()
}

#[tauri::command]
fn request_exit(app: AppHandle, backend: State<'_, Shared>) {
    let b = backend.inner().clone();
    std::thread::spawn(move || {
        let how = shutdown_backend(&b, Duration::from_secs(20));
        log::info!("orchestrator {how}");
        app.exit(0);
    });
}

#[tauri::command]
fn reveal_path(path: String) -> Result<(), String> {
    #[cfg(windows)]
    {
        Command::new("explorer").arg(format!("/select,{}", path.replace('/', "\\"))).spawn().map_err(|e| e.to_string())?;
        Ok(())
    }
    #[cfg(not(windows))]
    {
        let _ = path;
        Err("reveal is Windows-only for now".into())
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend: Shared = Arc::new(Backend::default());
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.set_focus();
            }
        }))
        .manage(backend.clone())
        .invoke_handler(tauri::generate_handler![backend_info, request_exit, reveal_path])
        .setup(move |app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(tauri_plugin_log::Builder::default().level(log::LevelFilter::Info).build())?;
            }
            spawn_backend(backend.clone());
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let app = window.app_handle().clone();
                let b: Shared = app.state::<Shared>().inner().clone();
                std::thread::spawn(move || {
                    let how = shutdown_backend(&b, Duration::from_secs(20));
                    log::info!("orchestrator {how}");
                    app.exit(0);
                });
            }
        })
        .run(tauri::generate_context!())
        .expect("error while building tauri application");
}
