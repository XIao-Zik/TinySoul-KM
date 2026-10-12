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

#[derive(serde::Serialize, Clone, Debug)]
pub struct KmDocHit {
    pub id: String,
    pub title: String,
    pub path: String,
    pub source: String,
}

#[derive(serde::Serialize, Clone, Debug)]
pub struct KmCardSource {
    pub id: String,
    pub title: String,
    pub path: String,
    pub source: String,
}

#[derive(serde::Serialize, Clone, Debug)]
pub struct KmCardEntry {
    pub day: String,
    pub question: String,
    pub answer: String,
    pub tags: Vec<String>,
    pub confidence: String,
    pub sources: Vec<KmCardSource>,
}

#[derive(serde::Serialize, Clone, Debug)]
pub struct KmDocument {
    pub id: String,
    pub title: String,
    pub path: String,
    pub source: String,
    pub markdown: String,
}

/// One knowledge document's full Markdown, addressed by stable km id.
#[tauri::command]
fn km_document(project_root: String, km_id: String) -> Result<KmDocument, String> {
    let entries = km_live_entries(&project_root)?;
    let (path, entry) = entries
        .iter()
        .find(|(_, e)| e.km_id == km_id)
        .ok_or_else(|| format!("Knowledge document not found: {km_id}"))?;
    let base = match entry.source.as_str() {
        "chat" => "chats",
        "card" => "cards",
        _ => "notes",
    };
    let full = km_root(&project_root)?.join(base).join(path);
    let markdown = fs::read_to_string(&full)
        .map_err(|e| format!("Cannot read {}: {e}", full.display()))?;
    Ok(KmDocument {
        id: entry.km_id.clone(),
        title: km_doc_hit(path, entry).title,
        path: path.clone(),
        source: entry.source.clone(),
        markdown,
    })
}

// -- KM vault file browser (user-configured external directory) -------------
//
// The KM "files" view browses a user-configured directory (typically the
// Obsidian vault) directly. Paths are always resolved as base + relative
// with `..` rejected, so commands cannot escape the configured root.

fn km_fs_path(base: &str, rel: &str) -> Result<PathBuf, String> {
    let base_path = Path::new(base);
    if !base_path.is_dir() {
        return Err(format!("KM 数据源目录不存在: {base}"));
    }
    let relative = Path::new(rel);
    if relative.is_absolute()
        || relative
            .components()
            .any(|c| matches!(c, std::path::Component::ParentDir))
    {
        return Err(format!("非法路径: {rel}"));
    }
    Ok(base_path.join(relative))
}

#[derive(serde::Serialize, Clone, Debug)]
pub struct KmFsEntry {
    pub name: String,
    pub rel: String,
    pub is_dir: bool,
    pub size: u64,
}

#[tauri::command]
fn km_fs_list(base: String, rel: String) -> Result<Vec<KmFsEntry>, String> {
    let dir = km_fs_path(&base, &rel)?;
    if !dir.is_dir() {
        return Err(format!("不是目录: {rel}"));
    }
    let mut entries: Vec<KmFsEntry> = Vec::new();
    for entry in fs::read_dir(&dir)
        .map_err(|e| format!("无法读取目录: {e}"))?
        .flatten()
    {
        let name = entry.file_name().to_string_lossy().to_string();
        if name.starts_with('.') {
            continue;
        }
        let is_dir = entry.file_type().map(|t| t.is_dir()).unwrap_or(false);
        let size = entry.metadata().map(|m| m.len()).unwrap_or(0);
        let rel_child = if rel.is_empty() {
            name.clone()
        } else {
            format!("{rel}/{name}")
        };
        entries.push(KmFsEntry {
            name,
            rel: rel_child,
            is_dir,
            size,
        });
    }
    entries.sort_by(|a, b| {
        b.is_dir
            .cmp(&a.is_dir)
            .then_with(|| a.name.to_lowercase().cmp(&b.name.to_lowercase()))
    });
    Ok(entries)
}

#[tauri::command]
fn km_fs_read(base: String, rel: String) -> Result<String, String> {
    let path = km_fs_path(&base, &rel)?;
    let metadata = path
        .metadata()
        .map_err(|e| format!("无法读取文件信息: {e}"))?;
    if metadata.len() > 2_000_000 {
        return Err("文件超过 2MB，暂不支持在界面中打开".to_string());
    }
    fs::read_to_string(&path).map_err(|e| format!("无法读取文件: {e}"))
}

#[tauri::command]
fn km_fs_write(base: String, rel: String, contents: String) -> Result<(), String> {
    let path = km_fs_path(&base, &rel)?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("无法创建目录: {e}"))?;
    }
    fs::write(&path, contents).map_err(|e| format!("无法写入文件: {e}"))
}

#[tauri::command]
fn km_fs_mkdir(base: String, rel: String) -> Result<(), String> {
    let path = km_fs_path(&base, &rel)?;
    fs::create_dir_all(&path).map_err(|e| format!("无法创建目录: {e}"))
}

fn km_live_entries(project_root: &str) -> Result<Vec<(String, KmIndexEntry)>, String> {
    let index_path = km_root(project_root)?
        .join(".tinysoul_knowledge")
        .join("index.json");
    let text = fs::read_to_string(&index_path)
        .map_err(|e| format!("Cannot read knowledge index: {e}"))?;
    let index: KmIndex =
        serde_json::from_str(&text).map_err(|e| format!("Knowledge index is invalid: {e}"))?;
    Ok(index
        .entries
        .into_iter()
        .filter(|(_, e)| !e.tombstoned && !e.km_id.is_empty())
        .collect())
}

fn km_doc_hit(path: &str, entry: &KmIndexEntry) -> KmDocHit {
    let stem = Path::new(path)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or(path)
        .to_string();
    KmDocHit {
        id: entry.km_id.clone(),
        title: if entry.title.is_empty() { stem } else { entry.title.clone() },
        path: path.to_string(),
        source: entry.source.clone(),
    }
}

/// Candidate documents for the neighborhood explorer: title prefix, then
/// title/path substring; an empty query returns the most recently imported.
#[tauri::command]
fn km_find_docs(
    project_root: String,
    query: String,
    limit: Option<usize>,
) -> Result<Vec<KmDocHit>, String> {
    let entries = km_live_entries(&project_root)?;
    let q = query.trim().to_lowercase();
    let mut hits: Vec<(i64, KmDocHit)> = Vec::new();
    for (path, entry) in &entries {
        let hit = km_doc_hit(path, entry);
        let score = if q.is_empty() {
            -(entry.mtime as i64)
        } else {
            let title = hit.title.to_lowercase();
            let stem = Path::new(path)
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or(path)
                .to_lowercase();
            if title.starts_with(&q) {
                0
            } else if title.contains(&q) {
                1
            } else if stem.contains(&q) || path.to_lowercase().contains(&q) {
                2
            } else {
                continue;
            }
        };
        hits.push((score, hit));
    }
    hits.sort_by(|a, b| {
        a.0.cmp(&b.0).then_with(|| {
            a.1.title.to_lowercase().cmp(&b.1.title.to_lowercase())
        })
    });
    hits.truncate(limit.unwrap_or(20).min(50));
    Ok(hits.into_iter().map(|(_, hit)| hit).collect())
}

#[derive(serde::Serialize, Clone, Debug)]
pub struct KmNeighbor {
    pub id: String,
    pub title: String,
    pub path: String,
    pub source: String,
    /// Relative to the center document: "out", "in", or "both".
    pub direction: String,
}

#[derive(serde::Serialize, Clone, Debug)]
pub struct KmNeighborhood {
    pub center: KmDocHit,
    pub neighbors: Vec<KmNeighbor>,
}

/// One-hop link neighborhood of one document: resolved out-links plus real
/// in-links (backlinks) inverted from the whole index.
#[derive(Clone, Copy, PartialEq)]
enum Dir {
    Out,
    In,
    Both,
}

fn record_neighbor<'a>(
    neighbors: &mut std::collections::HashMap<String, (Dir, String, &'a KmIndexEntry)>,
    id: String,
    dir: Dir,
    path: &str,
    entry: &'a KmIndexEntry,
) {
    match neighbors.get_mut(&id) {
        Some((existing, _, _)) => {
            if *existing != dir {
                *existing = Dir::Both;
            }
        }
        None => {
            neighbors.insert(id, (dir, path.to_string(), entry));
        }
    }
}

#[tauri::command]
fn km_neighborhood(
    project_root: String,
    km_id: String,
) -> Result<KmNeighborhood, String> {
    let entries = km_live_entries(&project_root)?;
    let center = entries
        .iter()
        .find(|(_, e)| e.km_id == km_id)
        .ok_or_else(|| format!("Knowledge document not found: {km_id}"))?;

    let mut by_stem: std::collections::HashMap<String, String> = Default::default();
    let mut by_title: std::collections::HashMap<String, String> = Default::default();
    for (path, entry) in &entries {
        let stem = Path::new(path)
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or(path)
            .to_lowercase();
        by_stem.insert(stem, entry.km_id.clone());
        if !entry.title.is_empty() {
            by_title.insert(entry.title.to_lowercase(), entry.km_id.clone());
        }
    }
    let resolve = |link: &String| -> Option<String> {
        let key = Path::new(link)
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or(link.as_str())
            .to_lowercase();
        by_stem.get(&key).or_else(|| by_title.get(&key)).cloned()
    };

    let mut neighbors: std::collections::HashMap<String, (Dir, String, &KmIndexEntry)> =
        Default::default();

    // Out-links of the center.
    for link in &center.1.links {
        if let Some(target) = resolve(link) {
            if target != km_id {
                    {
        // Out-links of the center.
        for link in &center.1.links {
            if let Some(target) = resolve(link) {
                if target != km_id {
                    record_neighbor(&mut neighbors, target, Dir::Out, &center.0, &center.1);
                }
            }
        }
    }
            }
        }
    }
    // In-links: every document whose links resolve to the center.
    for (path, entry) in &entries {
        if entry.km_id == km_id {
            continue;
        }
        for link in &entry.links {
            if resolve(link).as_deref() == Some(km_id.as_str()) {
                record_neighbor(&mut neighbors, entry.km_id.clone(), Dir::In, path, entry);
                break;
            }
        }
        let _ = path;
    }

    let mut rows: Vec<(String, Dir, String, &KmIndexEntry)> = neighbors
        .into_iter()
        .map(|(id, (dir, path, entry))| (id, dir, path, entry))
        .collect();
    rows.sort_by(|a, b| {
        let title = |e: &KmIndexEntry, fallback: &String| -> String {
            if e.title.is_empty() {
                fallback.clone()
            } else {
                e.title.clone()
            }
        };
        title(a.3, &a.2).to_lowercase().cmp(&title(b.3, &b.2).to_lowercase())
    });
    rows.truncate(48);
    let neighbors = rows
        .into_iter()
        .map(|(id, dir, path, entry)| {
            let direction = match dir {
                Dir::Out => "out",
                Dir::In => "in",
                Dir::Both => "both",
            };
            KmNeighbor {
                id,
                title: if entry.title.is_empty() {
                    path.strip_suffix(".md").unwrap_or(&path).to_string()
                } else {
                    entry.title.clone()
                },
                path,
                source: entry.source.clone(),
                direction: direction.to_string(),
            }
        })
        .collect();
    Ok(KmNeighborhood {
        center: km_doc_hit(&center.0, &center.1),
        neighbors,
    })
}

fn km_root(project_root: &str) -> Result<PathBuf, String> {
    let root = Path::new(project_root).join("knowledge");
    if !root.is_dir() {
        return Err("This project has no knowledge store yet — import a vault first.".to_string());
    }
    Ok(root)
}

#[tauri::command]
fn km_cards(project_root: String) -> Result<Vec<KmCardEntry>, String> {
    let cards_dir = km_root(&project_root)?.join("cards");
    let entries = km_live_entries(&project_root)?;
    let by_id: std::collections::HashMap<&str, (&String, &KmIndexEntry)> = entries
        .iter()
        .map(|(path, e)| (e.km_id.as_str(), (path, e)))
        .collect();

    let mut cards: Vec<KmCardEntry> = Vec::new();
    let files = fs::read_dir(&cards_dir)
        .map_err(|e| format!("Cannot read cards directory: {e}"))?;
    let mut paths: Vec<std::path::PathBuf> = files
        .flatten()
        .map(|entry| entry.path())
        .filter(|path| path.extension().and_then(|e| e.to_str()) == Some("md"))
        .collect();
    paths.sort_by(|a, b| b.cmp(a));
    for path in paths {
        let day = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("unknown")
            .to_string();
        let markdown = fs::read_to_string(&path)
            .map_err(|e| format!("Cannot read {}: {e}", path.display()))?;
        for section in markdown.split("## 卡片").skip(1) {
            let mut question = String::new();
            let mut tags: Vec<String> = Vec::new();
            let mut sources: Vec<KmCardSource> = Vec::new();
            let mut confidence = String::new();
            let mut answer_lines: Vec<&str> = Vec::new();
            let mut in_answer = false;
            for line in section.lines() {
                let trimmed = line.trim();
                if let Some(rest) = trimmed.strip_prefix("**Q:") {
                    question = rest.trim().trim_end_matches("**").to_string();
                    in_answer = true;
                } else if let Some(rest) = trimmed.strip_prefix("- 标签:") {
                    in_answer = false;
                    tags = rest
                        .split(',')
                        .map(|item| item.trim().to_string())
                        .filter(|item| !item.is_empty())
                        .collect();
                } else if let Some(rest) = trimmed.strip_prefix("- 来源:") {
                    in_answer = false;
                    for reference in rest.split(',') {
                        let id = reference.trim().trim_start_matches("km:").to_string();
                        if id.is_empty() {
                            continue;
                        }
                        match by_id.get(id.as_str()) {
                            Some((path, entry)) => sources.push(KmCardSource {
                                id: id.clone(),
                                title: km_doc_hit(path, entry).title,
                                path: (*path).clone(),
                                source: entry.source.clone(),
                            }),
                            None => sources.push(KmCardSource {
                                id: id.clone(),
                                title: id.clone(),
                                path: String::new(),
                                source: String::new(),
                            }),
                        }
                    }
                } else if let Some(rest) = trimmed.strip_prefix("- 置信度:") {
                    in_answer = false;
                    confidence = rest.trim().to_string();
                } else if in_answer && !trimmed.is_empty() {
                    answer_lines.push(trimmed);
                }
            }
            if question.is_empty() && answer_lines.is_empty() && sources.is_empty() {
                continue;
            }
            cards.push(KmCardEntry {
                day: day.clone(),
                question: if question.is_empty() {
                    "(未解析的问题)".to_string()
                } else {
                    question
                },
                answer: answer_lines.join("
"),
                tags,
                confidence: if confidence.is_empty() {
                    "medium".to_string()
                } else {
                    confidence
                },
                sources,
            });
        }
    }
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
    #[serde(default)]
    mtime: f64,
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
    let max = limit.unwrap_or(100).min(2000);

    // Collect every live node, then resolve links by path stem OR title so
    // `[[Note 49]]` matches a note stored at `notes/d00/note-00049.md`.
    let mut by_stem: std::collections::HashMap<String, String> = Default::default();
    let mut by_title: std::collections::HashMap<String, String> = Default::default();
    let mut live: Vec<(String, &KmIndexEntry)> = Vec::new();
    for (path, entry) in index.entries.iter() {
        if entry.tombstoned || entry.km_id.is_empty() {
            continue;
        }
        let stem = Path::new(path)
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or(path)
            .to_lowercase();
        by_stem.insert(stem.clone(), entry.km_id.clone());
        if !entry.title.is_empty() {
            by_title.insert(entry.title.to_lowercase(), entry.km_id.clone());
        }
        live.push((path.clone(), entry));
    }

    // Resolve every real link edge first (deduplicated), counting degrees so
    // the displayed subgraph keeps the most-connected documents.
    let mut edge_set: std::collections::HashSet<(String, String)> = Default::default();
    let mut degree: std::collections::HashMap<String, usize> = Default::default();
    for (path, entry) in &live {
        for link in &entry.links {
            let stem = Path::new(link)
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or(link.as_str())
                .to_lowercase();
            let target = by_stem
                .get(&stem)
                .or_else(|| by_title.get(&stem))
                .cloned();
            if let Some(target) = target {
                if target != entry.km_id
                    && edge_set.insert((entry.km_id.clone(), target.clone()))
                {
                    *degree.entry(entry.km_id.clone()).or_insert(0) += 1;
                    *degree.entry(target).or_insert(0) += 1;
                }
            }
            let _ = path;
        }
    }

    // Keep the `max` highest-degree nodes (ties broken by path), rebuild the
    // edge list among them.
    let total_live = live.len();
    let mut kept: Vec<(usize, String, &KmIndexEntry)> = live
        .into_iter()
        .map(|(path, entry)| {
            let d = degree.get(&entry.km_id).copied().unwrap_or(0);
            (d, path, entry)
        })
        .collect();
    kept.sort_by(|a, b| b.0.cmp(&a.0).then_with(|| a.1.cmp(&b.1)));
    kept.truncate(max);
    // Cards and chat entries are the interesting recent nodes; keep them even
    // when their degree is too low for the top-N cut.
    let kept_ids: std::collections::HashSet<String> =
        kept.iter().map(|(_, _, e)| e.km_id.clone()).collect();
    let specials: Vec<(usize, String, &KmIndexEntry)> = index
        .entries
        .iter()
        .filter(|(path, e)| {
            let is_special_source =
                e.source == "card" || path.to_lowercase().starts_with("chats/");
            is_special_source && !e.tombstoned && !e.km_id.is_empty()
                && !kept_ids.contains(&e.km_id)
        })
        .map(|(path, e)| (0, path.clone(), e))
        .take(64)
        .collect();
    kept.extend(specials);
    let known: std::collections::HashSet<String> =
        kept.iter().map(|(_, _, e)| e.km_id.clone()).collect();
    let mut nodes: Vec<KmNode> = kept
        .into_iter()
        .map(|(_, path, entry)| KmNode {
            id: entry.km_id.clone(),
            title: if entry.title.is_empty() {
                path.strip_suffix(".md").unwrap_or(&path).to_string()
            } else {
                entry.title.clone()
            },
            path,
            source: entry.source.clone(),
            tags: entry.tags.iter().take(6).cloned().collect(),
        })
        .collect();
    nodes.sort_by(|a, b| a.path.cmp(&b.path));
    let edges: Vec<KmEdge> = edge_set
        .into_iter()
        .filter(|(from, to)| known.contains(from) && known.contains(to))
        .map(|(from, to)| KmEdge { from, to })
        .collect();
    Ok(KmGraph {
        truncated: total_live > max,
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
            km_find_docs,
            km_neighborhood,
            km_document,
            km_fs_list,
            km_fs_read,
            km_fs_write,
            km_fs_mkdir,
            km_ingest
        ])
        .run(tauri::generate_context!())
        .expect("error while running TinySoul visualization");
}
