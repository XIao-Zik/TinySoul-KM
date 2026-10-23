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
        "workspace" => "workspace",
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

// -- card curation: user-side delete/edit of reflection-generated cards ------
//
// Cards live one day-file with one `## 卡片` section each. Curation rewrites
// that file and bumps the derived index entry (checksum/size/mtime/links) so
// the desktop views stay consistent. The running backend's in-memory index
// refreshes on its next own mutation or restart.

#[derive(Debug, Clone, PartialEq)]
struct ParsedCard {
    question: String,
    answer: String,
    tags: Vec<String>,
    refs: Vec<String>,
    confidence: String,
}

fn card_identity(question: &str, refs: &[String]) -> String {
    let mut sorted: Vec<&String> = refs.iter().collect();
    sorted.sort();
    format!(
        "{}\u{1f}{}",
        question.trim(),
        sorted
            .iter()
            .map(|r| r.trim().trim_start_matches("km:").to_string())
            .collect::<Vec<_>>()
            .join("\u{1f}")
    )
}

/// Split a card document into its verbatim frontmatter block and parsed
/// sections. The frontmatter block includes both `---` fences.
fn parse_card_document(markdown: &str) -> (String, Vec<ParsedCard>) {
    let mut lines = markdown.lines().peekable();
    let mut frontmatter = String::new();
    if lines.peek().map(|l| l.trim_end() == "---").unwrap_or(false) {
        frontmatter.push_str("---\n");
        lines.next();
        for line in lines.by_ref() {
            frontmatter.push_str(line);
            frontmatter.push('\n');
            if line.trim_end() == "---" {
                break;
            }
        }
    }
    let mut cards: Vec<ParsedCard> = Vec::new();
    let mut current: Option<ParsedCard> = None;
    let mut answer_lines: Vec<String> = Vec::new();
    let mut in_answer = false;
    let mut flush = |current: &mut Option<ParsedCard>, answer_lines: &mut Vec<String>| {
        if let Some(card) = current {
            card.answer = answer_lines.join("\n");
            cards.push(card.clone());
        }
        answer_lines.clear();
    };
    for line in lines {
        let trimmed = line.trim();
        if trimmed == "## 卡片" {
            flush(&mut current, &mut answer_lines);
            in_answer = false;
            current = Some(ParsedCard {
                question: String::new(),
                answer: String::new(),
                tags: Vec::new(),
                refs: Vec::new(),
                confidence: String::new(),
            });
            continue;
        }
        let Some(card) = current.as_mut() else {
            continue;
        };
        if let Some(rest) = trimmed.strip_prefix("**Q:") {
            card.question = rest.trim().trim_end_matches("**").trim().to_string();
            in_answer = true;
        } else if let Some(rest) = trimmed.strip_prefix("- 标签:") {
            in_answer = false;
            card.tags = rest
                .split(',')
                .map(|item| item.trim().to_string())
                .filter(|item| !item.is_empty())
                .collect();
        } else if let Some(rest) = trimmed.strip_prefix("- 来源:") {
            in_answer = false;
            for reference in rest.split(',') {
                let id = reference.trim().trim_start_matches("km:").to_string();
                if !id.is_empty() {
                    card.refs.push(id);
                }
            }
        } else if let Some(rest) = trimmed.strip_prefix("- 置信度:") {
            in_answer = false;
            card.confidence = rest.trim().to_string();
        } else if in_answer && !trimmed.is_empty() {
            answer_lines.push(trimmed.to_string());
        }
    }
    flush(&mut current, &mut answer_lines);
    (frontmatter, cards)
}

/// Canonical section body, byte-compatible with the Python writer's format.
fn render_card_section(card: &ParsedCard) -> String {
    let refs = card
        .refs
        .iter()
        .map(|id| format!("km:{id}"))
        .collect::<Vec<_>>()
        .join(", ");
    [
        "## 卡片".to_string(),
        String::new(),
        format!("**Q: {}**", card.question),
        String::new(),
        card.answer.clone(),
        String::new(),
        format!("- 标签: {}", card.tags.join(", ")),
        format!("- 来源: {refs}"),
        format!("- 置信度: {}", card.confidence),
        String::new(),
    ]
    .join("\n")
}

fn render_card_document(frontmatter: &str, cards: &[ParsedCard]) -> String {
    let body = cards
        .iter()
        .map(render_card_section)
        .collect::<Vec<_>>()
        .join("\n");
    if body.is_empty() {
        format!("{frontmatter}\n")
    } else {
        format!("{frontmatter}\n\n{body}")
    }
}

/// Minimal YAML scalar emission mirroring what Python's safe_dump produces
/// for card link titles: plain when unambiguous, single-quoted otherwise.
fn yaml_scalar(value: &str) -> String {
    let needs_quotes = value.is_empty()
        || value.contains(": ")
        || value.contains(" #")
        || value.ends_with(':')
        || value.trim() != value
        || value.starts_with(['&', '*', '!', '|', '>', '\'', '"', '%', '@', '`', '[', ']', '{', '}', '#', '-', '?', ',']);
    if needs_quotes {
        format!("'{}'", value.replace('\'', "''"))
    } else {
        value.to_string()
    }
}

/// Rewrite the frontmatter's `km_links` list in place, preserving every other
/// line verbatim (annotations and future keys survive curation untouched).
fn replace_km_links(frontmatter: &str, links: &[String]) -> String {
    let block: Vec<String> = if links.is_empty() {
        vec!["km_links: []".to_string()]
    } else {
        let mut block = vec!["km_links:".to_string()];
        block.extend(links.iter().map(|title| format!("- {}", yaml_scalar(title))));
        block
    };
    let lines: Vec<&str> = frontmatter.lines().collect();
    let mut output: Vec<String> = Vec::with_capacity(lines.len() + block.len());
    let mut replaced = false;
    let mut index = 0;
    while index < lines.len() {
        let line = lines[index];
        if line.starts_with("km_links:") && !replaced {
            output.extend(block.iter().cloned());
            replaced = true;
            index += 1;
            while index < lines.len() && lines[index].trim_start().starts_with("- ") {
                index += 1;
            }
            continue;
        }
        output.push(line.to_string());
        index += 1;
    }
    if !replaced && !links.is_empty() {
        // Insert before the closing fence; an empty list needs no key at all.
        let fence = output.iter().rposition(|line| line.trim_end() == "---");
        if let Some(position) = fence {
            let tail = output.split_off(position);
            output.extend(block.iter().cloned());
            output.extend(tail);
        }
    }
    let mut result = output.join("\n");
    if !result.ends_with('\n') {
        result.push('\n');
    }
    result
}

/// Canonical content checksum, mirroring the Python store's definition so the
/// bumped index entry stays byte-compatible with what the backend recomputes.
fn card_checksum(text: &str) -> String {
    let normalized = text
        .trim_start_matches('\u{feff}')
        .replace("\r\n", "\n")
        .replace('\r', "\n");
    let digest = Sha256::digest(normalized.as_bytes());
    format!("sha256:{:x}", digest)
}

/// Rewrite the day file's derived index entry after curation.
fn bump_card_index(
    project_root: &str,
    day: &str,
    text: &str,
    links: Option<Vec<String>>,
) -> Result<(), String> {
    let index_path = km_root(project_root)?
        .join(".tinysoul_knowledge")
        .join("index.json");
    let raw = fs::read_to_string(&index_path)
        .map_err(|e| format!("Cannot read knowledge index: {e}"))?;
    let mut value: serde_json::Value = serde_json::from_str(&raw)
        .map_err(|e| format!("Knowledge index is invalid: {e}"))?;
    let Some(entry) = value
        .get_mut("entries")
        .and_then(|entries| entries.get_mut(format!("{day}.md")))
        .and_then(|entry| entry.as_object_mut())
    else {
        return Ok(()); // entry absent: nothing derived to refresh
    };
    entry.insert("checksum".to_string(), serde_json::Value::String(card_checksum(text)));
    entry.insert("size".to_string(), serde_json::Value::Number(serde_json::Number::from(text.chars().count())));
    let mtime = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0);
    entry.insert("mtime".to_string(), serde_json::json!(mtime));
    if let Some(links) = links {
        entry.insert("links".to_string(), serde_json::json!(links));
    }
    let serialized = serde_json::to_string_pretty(&value)
        .map_err(|e| format!("Knowledge index is invalid: {e}"))?;
    atomic_write(&index_path, &serialized)
}

fn atomic_write(path: &Path, text: &str) -> Result<(), String> {
    let temp = path.with_extension("tmp-curation");
    fs::write(&temp, text).map_err(|e| format!("Cannot write {}: {e}", temp.display()))?;
    fs::rename(&temp, path).map_err(|e| format!("Cannot replace {}: {e}", path.display()))
}

fn card_file_path(project_root: &str, day: &str) -> Result<PathBuf, String> {
    if day.is_empty()
        || !day.chars().all(|c| c.is_ascii_digit() || c == '-')
        || !day.chars().next().map(|c| c.is_ascii_digit()).unwrap_or(false)
    {
        return Err(format!("Invalid card day: {day}"));
    }
    Ok(km_root(project_root)?.join("cards").join(format!("{day}.md")))
}

fn load_card_document(
    project_root: &str,
    day: &str,
) -> Result<(PathBuf, String, String, Vec<ParsedCard>), String> {
    let path = card_file_path(project_root, day)?;
    let markdown = fs::read_to_string(&path)
        .map_err(|e| format!("Cannot read card document {day}: {e}"))?;
    let (frontmatter, cards) = parse_card_document(&markdown);
    Ok((path, markdown, frontmatter, cards))
}

fn find_card_index<'a>(
    cards: &'a [ParsedCard],
    question: &str,
    source_ids: &[String],
) -> Option<usize> {
    let identity = card_identity(question, source_ids);
    cards
        .iter()
        .position(|card| card_identity(&card.question, &card.refs) == identity)
}

/// Resolve the union of source titles for the remaining cards, in first-seen
/// order; unresolvable ids fall back to the raw id (same as km_cards).
fn remaining_link_titles(
    project_root: &str,
    cards: &[ParsedCard],
) -> Result<Vec<String>, String> {
    let entries = km_live_entries(project_root)?;
    let by_id: std::collections::HashMap<&str, &KmIndexEntry> = entries
        .iter()
        .map(|(_, e)| (e.km_id.as_str(), e))
        .collect();
    let mut titles: Vec<String> = Vec::new();
    for card in cards {
        for id in &card.refs {
            let title = match by_id.get(id.as_str()) {
                Some(entry) if !entry.title.is_empty() => entry.title.clone(),
                _ => id.clone(),
            };
            if !titles.contains(&title) {
                titles.push(title);
            }
        }
    }
    Ok(titles)
}

#[tauri::command]
fn km_card_delete(
    project_root: String,
    day: String,
    question: String,
    source_ids: Vec<String>,
) -> Result<(), String> {
    let (path, _markdown, frontmatter, cards) = load_card_document(&project_root, &day)?;
    let position = find_card_index(&cards, &question, &source_ids)
        .ok_or_else(|| format!("Card not found in {day}: {question}"))?;
    let mut remaining = cards.clone();
    remaining.remove(position);
    let links = remaining_link_titles(&project_root, &remaining)?;
    let updated_frontmatter = replace_km_links(&frontmatter, &links);
    let text = render_card_document(&updated_frontmatter, &remaining);
    atomic_write(&path, &text)?;
    bump_card_index(&project_root, &day, &text, Some(links))
}

#[tauri::command]
fn km_card_update(
    project_root: String,
    day: String,
    question: String,
    source_ids: Vec<String>,
    new_question: String,
    new_answer: String,
    new_tags: Vec<String>,
    new_confidence: String,
) -> Result<(), String> {
    if new_question.trim().is_empty() {
        return Err("Card question cannot be empty".to_string());
    }
    let (path, _markdown, frontmatter, cards) = load_card_document(&project_root, &day)?;
    let position = find_card_index(&cards, &question, &source_ids)
        .ok_or_else(|| format!("Card not found in {day}: {question}"))?;
    let mut remaining = cards.clone();
    remaining[position].question = new_question.trim().to_string();
    remaining[position].answer = new_answer.replace("\r\n", "\n").trim().to_string();
    remaining[position].tags = new_tags
        .iter()
        .map(|tag| tag.trim().to_string())
        .filter(|tag| !tag.is_empty())
        .collect();
    remaining[position].confidence = if new_confidence.trim().is_empty() {
        "medium".to_string()
    } else {
        new_confidence.trim().to_string()
    };
    let text = render_card_document(&frontmatter, &remaining);
    atomic_write(&path, &text)?;
    bump_card_index(&project_root, &day, &text, None)
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
            km_card_delete,
            km_card_update,
            km_ingest
        ])
        .run(tauri::generate_context!())
        .expect("error while running TinySoul visualization");
}

#[cfg(test)]
mod card_curation_tests {
    use super::*;

    fn sample_markdown() -> String {
        let frontmatter = "---\nkm_source: card\nkm_id: card-41c9e73cb1c5\nkm_card_date: '2026-10-12'\nkm_imported: '2026-10-11T19:44:52+00:00'\nkm_links:\n- 混合检索设计讨论\n- 如何让大模型为你所用\n---\n\n";
        let card_a = ParsedCard {
            question: "混合检索怎么设计？".to_string(),
            answer: "词法+向量双路。".to_string(),
            tags: vec!["RRF".to_string()],
            refs: vec!["c-5e674ee0f0d3".to_string()],
            confidence: "high".to_string(),
        };
        let card_b = ParsedCard {
            question: "如何避免上下文腐化？".to_string(),
            answer: "控制注入量。".to_string(),
            tags: vec!["context".to_string()],
            refs: vec!["k-a118b1d747bc".to_string()],
            confidence: "medium".to_string(),
        };
        format!("{frontmatter}{}", render_card_document("---\nkm_source: card\nkm_id: card-41c9e73cb1c5\nkm_card_date: '2026-10-12'\nkm_imported: '2026-10-11T19:44:52+00:00'\nkm_links:\n- 混合检索设计讨论\n- 如何让大模型为你所用\n---", &[card_a, card_b]))
    }

    #[test]
    fn parse_round_trips_canonical_sections() {
        let markdown = sample_markdown();
        let (frontmatter, cards) = parse_card_document(&markdown);
        assert!(frontmatter.starts_with("---\nkm_source: card"));
        assert!(frontmatter.trim_end().ends_with("---"));
        assert_eq!(cards.len(), 2);
        assert_eq!(cards[0].question, "混合检索怎么设计？");
        assert_eq!(cards[0].refs, vec!["c-5e674ee0f0d3"]);
        assert_eq!(cards[0].answer, "词法+向量双路。");
        assert_eq!(cards[1].confidence, "medium");
        // re-rendering the parsed cards reproduces the canonical body
        assert!(render_card_document(&frontmatter, &cards).contains("**Q: 混合检索怎么设计？**"));
    }

    #[test]
    fn identity_ignores_ref_order_and_prefix() {
        let a = card_identity("Q", &["km:b".to_string(), "km:a".to_string()]);
        let b = card_identity(" Q ", &["a".to_string(), "b".to_string()]);
        assert_eq!(a, b);
    }

    #[test]
    fn delete_recomputes_km_links_from_remaining_cards() {
        let markdown = sample_markdown();
        let (frontmatter, cards) = parse_card_document(&markdown);
        let remaining: Vec<ParsedCard> = cards[1..].to_vec();
        let links = remaining_link_titles_without_index(&remaining);
        let updated = replace_km_links(&frontmatter, &links);
        assert!(updated.contains("km_links:\n- k-a118b1d747bc"));
        assert!(!updated.contains("混合检索设计讨论"));
        // other frontmatter lines survive verbatim
        assert!(updated.contains("km_imported: '2026-10-11T19:44:52+00:00'"));
    }

    #[test]
    fn replace_km_links_handles_missing_and_empty() {
        let without = "---\nkm_source: card\nkm_id: x\n---\n";
        assert_eq!(replace_km_links(without, &[]), without.to_string());
        let added = replace_km_links(without, &["T".to_string()]);
        assert!(added.contains("km_links:\n- T"));
        let emptied = replace_km_links(&sample_markdown(), &[]);
        assert!(emptied.contains("km_links: []"));
    }

    #[test]
    fn yaml_scalar_quotes_ambiguous_values() {
        assert_eq!(yaml_scalar("简单标题"), "简单标题");
        assert_eq!(yaml_scalar("a: b"), "'a: b'");
        assert_eq!(yaml_scalar("it's"), "it's");
        assert_eq!(yaml_scalar("'leading"), "'''leading'");
        assert_eq!(yaml_scalar(" padded "), "' padded '");
    }

    #[test]
    fn checksum_matches_python_store_definition() {
        assert_eq!(
            card_checksum("a\r\nb\n"),
            "sha256:911169ddaaf146aff539f58c26c489af3b892dff0fe283c1c264c65ae5aa59a2"
        );
    }

    /// Link-title resolution without a store on disk (test double).
    fn remaining_link_titles_without_index(cards: &[ParsedCard]) -> Vec<String> {
        let mut titles: Vec<String> = Vec::new();
        for card in cards {
            for id in &card.refs {
                if !titles.contains(id) {
                    titles.push(id.clone());
                }
            }
        }
        titles
    }
}
