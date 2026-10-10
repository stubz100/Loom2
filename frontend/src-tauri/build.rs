// D36: bake the commit and the build time into the shell; spawn_backend hands them to the orchestrator (/version, About).
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

fn main() {
  let sha = Command::new("git")
    .args(["rev-parse", "--short", "HEAD"])
    .output()
    .ok()
    .filter(|o| o.status.success())
    .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
    .unwrap_or_default();
  let epoch = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0);
  println!("cargo:rustc-env=LOOM2_GIT_SHA={sha}");
  println!("cargo:rustc-env=LOOM2_BUILD_EPOCH={epoch}");
  // rebuild the metadata when the checkout moves to another commit
  println!("cargo:rerun-if-changed=../../.git/HEAD");
  println!("cargo:rerun-if-changed=../../.git/refs/heads");
  println!("cargo:rerun-if-env-changed=LOOM2_VARIANT");
  tauri_build::build()
}
