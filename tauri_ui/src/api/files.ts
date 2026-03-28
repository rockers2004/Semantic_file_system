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
