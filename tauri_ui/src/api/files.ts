import { BACKEND_URL } from "./health";


export interface TreeEntry {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
  modified: string;
}

interface TreeResponse {
  ok: boolean;
  data: {
    root: string;
    path: string;
    depth: number;
    entries: TreeEntry[];
  };
}

interface ConfigResponse {
  ok: boolean;
  data: {
    root_path: string;
    max_depth: number;
  };
  error?: { code?: string; message?: string; details?: unknown } | null;
}

export interface FileReadResponse {
  ok: boolean;
  data: {
    path: string;
    content: string;
    encoding: string;
    size: number;
    modified: string;
  };
  error: null | { code: string; message: string; details?: unknown };
  meta: unknown;
}

export interface SearchResult {
  path: string;
  score: number;
  snippet: string;
  is_dir: false;
}

interface SearchResponse {
  ok: boolean;
  data: {
    query: string;
    total: number;
    results: SearchResult[];
  };
  error?:  { code?: string; message?: string; details?: unknown } | null;
  meta?: unknown;
}

export interface CommandResultItem {
  path: string;
  score: number;
  snippet: string;
  is_dir: false;
}

interface CommandResponse {
  ok: boolean;
  data: {
    kind: "command_placeholder" | "search";
    input: string;
    intent: "command" | "search";
    message: string;
    parsed: { raw: string; action: string; args: string[] } | null;
    results: CommandResultItem[];
  };
  error?: { code?: string; message?: string; details?: unknown } | null;
  meta?: unknown;
}

export async function readFile(path: string): Promise<FileReadResponse["data"]> {
  const response = await fetch(`${BACKEND_URL}/api/v1/file/read`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(`File read failed: ${response.status} ${message}`);
  }

  const json = (await response.json()) as FileReadResponse;
  if (!json.ok) {
    throw new Error(json.error?.message || "File read failed");
  }

  return json.data;
}

export async function fetchTree(path?: string): Promise<TreeResponse["data"]> {
  const params = new URLSearchParams();
  if (path) {
    params.set("path", path);
  }
  params.set("depth", "1");

  const response = await fetch(`${BACKEND_URL}/api/v1/tree?${params.toString()}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Tree API failed: ${response.status} ${text}`);
  }

  const json = (await response.json()) as TreeResponse;
  if (!json.ok) {
    throw new Error("Tree API returned unsuccessful response");
  }

  return json.data;
}

export async function getConfig(): Promise<ConfigResponse["data"]> {
  const response = await fetch(`${BACKEND_URL}/api/v1/config`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Config API failed: ${response.status} ${text}`);
  }

  const json = (await response.json()) as ConfigResponse;
  if (!json.ok) {
    throw new Error(json.error?.message || "Failed to load config");
  }

  return json.data;
}

export async function updateRootPath(rootPath: string): Promise<ConfigResponse["data"]> {
  const response = await fetch(`${BACKEND_URL}/api/v1/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ root_path: rootPath }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Set root failed: ${response.status} ${text}`);
  }

  const json = (await response.json()) as ConfigResponse;
  if (!json.ok) {
    throw new Error(json.error?.message || "Failed to update root path");
  }

  return json.data;
}

export async function searchFiles(query: string, k = 10, mode = "normal"): Promise<SearchResponse["data"]> {
  const response = await fetch(`${BACKEND_URL}/api/v1/search`, {
    method: "POST",
    headers: { "Content-Type":"application/json" },
    body: JSON.stringify({ query, k, mode }),
  });
  
  if(!response.ok) {
    const text = await response.text();
    throw new Error(`Search API failed: ${response.status} ${text}`);
  }

  const json = (await response.json()) as SearchResponse;
  if(!json.ok) {
    throw new Error(json.error?.message || "Search failed");
  }

  return json.data;
}

export async function runCommand(text: string): Promise<CommandResponse["data"]> {
  const response = await fetch(`${BACKEND_URL}/api/v1/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    const textResponse = await response.text();
    throw new Error(`Command API failed: ${response.status} ${textResponse}`);
  }

  const json = (await response.json()) as CommandResponse;
  if (!json.ok) {
    throw new Error(json.error?.message || "Command failed");
  }

  return json.data;
}