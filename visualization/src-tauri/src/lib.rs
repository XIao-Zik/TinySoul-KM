use std::env;
use std::fs;
use std::path::{Path, PathBuf};

use serde::Deserialize;
use sha2::{Digest, Sha256};

#[derive(serde::Serialize, Clone, Debug)]
pub struct BackendConnection {
    pub host: String,
    pub port: u16,
    pub token: String,
    pub protocol_version: i64,
    pub instance_id: String,
    pub project_identity: String,
    pub project_root: String,
}

#[derive(Deserialize, Debug)]
struct InstanceRecord {
    schema_version: i64,
    instance_id: String,
    project_root: String,
    project_identity: String,
    host: String,
    port: u16,
    token: String,
    protocol_version: i64,
}

#[tauri::command]
fn discover_backend(project_root: String) -> Result<Option<BackendConnection>, String> {
    let root = fs::canonicalize(Path::new(&project_root))
        .map_err(|error| format!("Project root cannot be resolved: {error}"))?;
    let identity = project_identity(&root);
    let record_path = instance_directory()?.join(format!("{identity}.json"));
    let text = match fs::read_to_string(&record_path) {
        Ok(value) => value,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => {
            return Err(format!(
                "TinySoul connection record cannot be read: {error}"
            ))
        }
    };
    let record: InstanceRecord = serde_json::from_str(&text)
        .map_err(|error| format!("TinySoul connection record is invalid: {error}"))?;
    if record.schema_version != 1
        || record.project_identity != identity
        || record.host != "127.0.0.1"
        || record.port == 0
        || record.token.len() < 32
        || record.instance_id.is_empty()
    {
        return Ok(None);
    }
    Ok(Some(BackendConnection {
        host: record.host,
        port: record.port,
        token: record.token,
        protocol_version: record.protocol_version,
        instance_id: record.instance_id,
        project_identity: record.project_identity,
        project_root: record.project_root,
    }))
}

fn project_identity(root: &Path) -> String {
    let mut value = root.to_string_lossy().to_string();
    if cfg!(windows) {
        value = value
            .strip_prefix(r"\\?\")
            .unwrap_or(&value)
            .replace('/', "\\")
            .to_lowercase();
    }
    format!("{:x}", Sha256::digest(value.as_bytes()))
}

fn instance_directory() -> Result<PathBuf, String> {
    if let Some(value) = env::var_os("TINYSOUL_INSTANCE_DIR") {
        return Ok(PathBuf::from(value));
    }
    if cfg!(windows) {
        if let Some(value) = env::var_os("LOCALAPPDATA") {
            return Ok(PathBuf::from(value).join("TinySoul").join("instances"));
        }
    }
    if let Some(value) = env::var_os("XDG_RUNTIME_DIR") {
        return Ok(PathBuf::from(value).join("tinysoul").join("instances"));
    }
    let home = env::var_os("HOME")
        .map(PathBuf::from)
        .ok_or_else(|| "Current user home directory is unavailable".to_string())?;
    if cfg!(target_os = "macos") {
        return Ok(home
            .join("Library")
            .join("Application Support")
            .join("TinySoul")
            .join("instances"));
    }
    Ok(home
        .join(".local")
        .join("state")
        .join("tinysoul")
        .join("instances"))
}

#[derive(Deserialize, Debug)]
struct ExportFileInput {
    path: String,
    contents: String,
}

/// Write the turn trace export bundle under a user-picked directory.
/// Every path must stay relative to `base_dir`; returns the export root.
#[tauri::command]
fn write_export_files(base_dir: String, files: Vec<ExportFileInput>) -> Result<String, String> {
    let base = Path::new(&base_dir);
    if !base.is_dir() {
        return Err("The chosen export directory does not exist".to_string());
    }
    for file in &files {
        let relative = Path::new(&file.path);
        if relative.is_absolute()
            || relative
                .components()
                .any(|c| matches!(c, std::path::Component::ParentDir))
        {
            return Err(format!("Invalid export path: {}", file.path));
        }
        let target = base.join(relative);
        if let Some(parent) = target.parent() {
            fs::create_dir_all(parent)
                .map_err(|e| format!("Cannot create export directory: {e}"))?;
        }
        fs::write(&target, &file.contents)
            .map_err(|e| format!("Cannot write {}: {e}", target.display()))?;
    }
    // The bundle root is the first path component shared by all files.
    let root = files
        .first()
        .and_then(|f| Path::new(&f.path).components().next())
        .map(|c| base.join(c.as_os_str()))
        .unwrap_or_else(|| base.to_path_buf());
    Ok(root.to_string_lossy().to_string())
}

// -- Knowledge (km) read-only helpers ---------------------------------------
//
// These commands read the local knowledge store directly (Markdown documents
// and the derived index) so the KM views work without new endpoint protocol
// surface. They are read-only except for km_ingest, which shells out to the
// `tinysoul km-ingest` CLI (configurable binary, never a shell string).

#[derive(serde::Serialize, Clone, Debug)]
pub struct KmCard {
    pub day: String,
    pub path: String,
    pub markdown: String,
}

#[derive(serde::Serialize, Clone, Debug)]
pub struct KmNode {
    pub id: String,
    pub title: String,
    pub path: String,
    pub source: String,
    pub tags: Vec<String>,
}

#[derive(serde::Serialize, Clone, Debug)]
pub struct KmEdge {
    pub from: String,
    pub to: String,
}

#[derive(serde::Serialize, Clone, Debug)]
pub struct KmGraph {
    pub nodes: Vec<KmNode>,
    pub edges: Vec<KmEdge>,
    pub truncated: bool,
}

fn km_root(project_root: &str) -> Result<PathBuf, String> {
    let root = Path::new(project_root).join("knowledge");
    if !root.is_dir() {
        return Err("This project has no knowledge store yet — import a vault first.".to_string());
    }
    Ok(root)
}

#[tauri::command]
fn km_cards(project_root: String) -> Result<Vec<KmCard>, String> {
    let cards_dir = km_root(&project_root)?.join("cards");
    let mut cards = Vec::new();
    let entries = fs::read_dir(&cards_dir)
        .map_err(|e| format!("Cannot read cards directory: {e}"))?;
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("md") {
            continue;
        }
        let day = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("unknown")
            .to_string();
        let markdown = fs::read_to_string(&path)
            .map_err(|e| format!("Cannot read {}: {e}", path.display()))?;
        cards.push(KmCard {
            day,
            path: path.to_string_lossy().to_string(),
            markdown,
        });
    }
    cards.sort_by(|a, b| b.day.cmp(&a.day));
    Ok(cards)
}

#[derive(Deserialize, Debug)]
struct KmIndexEntry {
    #[serde(default)]
    km_id: String,
    #[serde(default)]
    title: String,
    #[serde(default)]
    source: String,
    #[serde(default)]
    links: Vec<String>,
    #[serde(default)]
    tags: Vec<String>,
    #[serde(default)]
    tombstoned: bool,
}

#[derive(Deserialize, Debug)]
struct KmIndex {
    #[serde(default)]
    entries: std::collections::HashMap<String, KmIndexEntry>,
}

#[tauri::command]
fn km_graph(project_root: String, limit: Option<usize>) -> Result<KmGraph, String> {
    let index_path = km_root(&project_root)?.join(".tinysoul_knowledge").join("index.json");
    let text = fs::read_to_string(&index_path)
        .map_err(|e| format!("Cannot read knowledge index: {e}"))?;
    let index: KmIndex =
        serde_json::from_str(&text).map_err(|e| format!("Knowledge index is invalid: {e}"))?;
    let max = limit.unwrap_or(400).min(2000);

    // Path stem -> km_id for resolving wiki-link targets to nodes.
    let mut by_stem: std::collections::HashMap<String, String> = Default::default();
    let mut nodes: Vec<KmNode> = Vec::new();
    for (path, entry) in index.entries.iter() {
        if entry.tombstoned || entry.km_id.is_empty() {
            continue;
        }
        if nodes.len() >= max {
            break;
        }
        let stem = Path::new(path)
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or(path)
            .to_string();
        by_stem.insert(stem.to_lowercase(), entry.km_id.clone());
        nodes.push(KmNode {
            id: entry.km_id.clone(),
            title: if entry.title.is_empty() { stem } else { entry.title.clone() },
            path: path.clone(),
            source: entry.source.clone(),
            tags: entry.tags.iter().take(6).cloned().collect(),
        });
    }
    let known: std::collections::HashSet<String> =
        nodes.iter().map(|n| n.id.clone()).collect();
    let mut edges: Vec<KmEdge> = Vec::new();
    'outer: for (_path, entry) in index.entries.iter() {
        if entry.tombstoned || entry.km_id.is_empty() || !known.contains(&entry.km_id) {
            continue;
        }
        for link in &entry.links {
            let stem = Path::new(link)
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or(link.as_str())
                .to_lowercase();
            if let Some(target) = by_stem.get(&stem) {
                if target != &entry.km_id {
                    edges.push(KmEdge {
                        from: entry.km_id.clone(),
                        to: target.clone(),
                    });
                }
            }
            if edges.len() >= max * 4 {
                break 'outer;
            }
        }
    }
    Ok(KmGraph {
        truncated: nodes.len() >= max,
        nodes,
        edges,
    })
}

#[derive(serde::Serialize, Clone, Debug)]
pub struct KmIngestOutcome {
    pub code: i32,
    pub output: String,
}

/// Run `tinysoul km-ingest` through a direct process (no shell interpolation).
#[tauri::command]
fn km_ingest(
    project_root: String,
    obsidian: Option<String>,
    chat: Option<String>,
    platform: Option<String>,
    dry_run: bool,
    cli: Option<String>,
) -> Result<KmIngestOutcome, String> {
    let binary = cli.unwrap_or_else(|| "tinysoul".to_string());
    let mut command = std::process::Command::new(binary);
    command.arg("km-ingest").arg("--root").arg(&project_root);
    if let Some(vault) = obsidian {
        command.arg("--obsidian").arg(vault);
    }
    if let Some(chat) = chat {
        command.arg("--chat").arg(chat);
    }
    if let Some(platform) = platform {
        command.arg("--platform").arg(platform);
    }
    if dry_run {
        command.arg("--dry-run");
    }
    let output = command
        .output()
        .map_err(|e| format!("Cannot run the tinysoul CLI: {e}"))?;
    let mut text = String::from_utf8_lossy(&output.stdout).to_string();
    if !output.stderr.is_empty() {
        text.push_str(&String::from_utf8_lossy(&output.stderr));
    }
    Ok(KmIngestOutcome {
        code: output.status.code().unwrap_or(-1),
        output: text,
    })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            discover_backend,
            write_export_files,
            km_cards,
            km_graph,
            km_ingest
        ])
        .run(tauri::generate_context!())
        .expect("error while running TinySoul visualization");
}
