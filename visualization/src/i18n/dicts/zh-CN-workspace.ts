/**
 * zh-CN segment: the workspace feature. Keys are the collapsed English source
 * strings; untranslated entries fall back to English.
 */
export const workspaceText: Record<string, string> = {
  // WorkspacePage
  "Manifest refresh failed: {message}": "清单刷新失败：{message}",
  "Everything": "全部",
  "Folder: {dir}": "文件夹：{dir}",
  "Not connected to a backend.": "未连接到后端。",
  "The manifest could not be read": "无法读取清单",
  "The Workspace index is unavailable right now.": "工作区索引当前不可用。",
  "Retry": "重试",
  "Not in the manifest": "不在清单中",
  "is not part of the {day} Workspace index.": "不属于 {day} 的工作区索引。",
  "Back to the tree": "返回目录树",
  "Workspace": "工作区",
  "Select a file from the tree, create one, or drop files to upload.":
    "从目录树选择文件、新建文件，或拖入文件上传。",
  "Archived view of {day} — read-only.": "{day} 的归档视图 —— 只读。",
  "Search workspace": "搜索工作区",
  "Search the workspace…": "搜索工作区…",

  // Sidebar
  "Content search reads the active workspace — switched back to it.":
    "内容搜索仅读取活动工作区 —— 已切换回活动工作区。",
  "Workspace day": "工作区日期",
  "Active workspace": "活动工作区",
  "Active · {day}": "活动 · {day}",
  "{day} (archived)": "{day}（已归档）",
  "Files": "文件",
  "Trash": "回收站",
  "Filter…": "筛选…",
  "Filter files": "筛选文件",
  "New file": "新建文件",
  "New folder": "新建文件夹",
  "Reading the manifest…": "正在读取清单…",
  "No files yet": "暂无文件",
  "No matches": "无匹配结果",
  "Create a file or drop files here to upload.": "在此新建文件或拖入文件上传。",
  "Drop files to upload (existing names are refused)":
    "拖入文件即可上传（同名文件将被拒绝）",
  "Path (e.g. notes/todo.md)": "路径（例如 notes/todo.md）",
  "Create file": "创建文件",
  "Path (e.g. notes/assets)": "路径（例如 notes/assets）",
  "Create folder": "创建文件夹",
  "Unsaved edits": "未保存的修改",
  "Reading the trash…": "正在读取回收站…",
  "Trash is empty": "回收站为空",
  "Trashed resources stay restorable here.": "已移入回收站的资源可在此恢复。",
  "+{count} inside": "内含 {count} 项",
  "Restored {path}.": "已恢复 {path}。",
  "Restore": "恢复",
  "Show more": "显示更多",

  // FilePanel
  "Moved to trash.": "已移入回收站。",
  "View trash": "查看回收站",
  "Archived · read-only": "已归档 · 只读",
  "edited": "已编辑",
  "Append text": "追加文本",
  "Find and replace": "查找并替换",
  "Move or rename": "移动或重命名",
  "Tags": "标签",
  "Download": "下载",
  "Copy reference": "复制引用",
  "Quote in conversation": "在对话中引用",
  "Move to trash": "移入回收站",
  "This file changed on disk while you have unsaved edits.":
    "磁盘上的文件已更改，而你有未保存的修改。",
  "Reload": "重新加载",
  "Keep editing": "继续编辑",
  "Directory — its files appear in the tree.": "目录 —— 其文件显示在目录树中。",
  "Target path": "目标路径",
  "Move": "移动",
  "to the trash? It stays restorable from the Trash tab — there is no permanent delete here.":
    "到回收站？它仍可在回收站标签页中恢复——此处没有永久删除。",
  "Cancel": "取消",

  // Modals
  "Kept as-is: {tags}": "原样保留：{tags}",
  "Save tags": "保存标签",
  "Text appended to the end of the file…": "追加到文件末尾的文本…",
  "Append": "追加",
  "Find (must match exactly once)": "查找（必须恰好匹配一次）",
  "Replace with": "替换为",
  "Replace": "替换",

  // TextFileView
  "Edit": "编辑",
  "Split": "分栏",
  "Preview": "预览",
  "Discard": "放弃",
  "Save": "保存",
  "Rendered": "渲染视图",
  "Source": "源码",
  "Lines {range}": "第 {range} 行",
  "Show rendered": "显示渲染结果",
  "truncated page": "已截断的页面",
  "This file cannot be edited in the page (full read rejected): {message}":
    "页面中无法编辑此文件（完整读取被拒绝）：{message}",
  "File editor": "文件编辑器",
  "Empty file.": "空文件。",

  // BlobView
  "Media type": "媒体类型",
  "Size": "大小",
  "Description": "描述",
  "This file type is not embedded in the page. Download it to open with a local application.":
    "此文件类型不会在页面中内嵌显示，请下载后用本地应用打开。",
  "The image could not be read: {error}": "无法读取图片：{error}",

  // mutations / download / useWorkspaceText
  "Another workspace operation is still running.": "另一个工作区操作仍在进行中。",
  "Save failed": "保存失败",
  "Create file failed": "创建文件失败",
  "Create folder failed": "创建文件夹失败",
  "Move failed": "移动失败",
  "Update tags failed": "更新标签失败",
  "Append failed": "追加失败",
  "Replace failed": "替换失败",
  "Move to trash failed": "移入回收站失败",
  "Restore failed": "恢复失败",
  "\"{path}\" is not a valid workspace path.": "“{path}”不是有效的工作区路径。",
  "{file} (invalid path)": "{file}（路径无效）",
  "{file} ({message})": "{file}（{message}）",
  "Uploaded {count} file.": "已上传 {count} 个文件。",
  "Uploaded {count} files.": "已上传 {count} 个文件。",
  "{failed} of {total} uploads failed: {detail}":
    "{total} 个上传中 {failed} 个失败：{detail}",
  "Download failed: {message}": "下载失败：{message}",
};
