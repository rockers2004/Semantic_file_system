export interface HealthResponse {
  ok: boolean;
  data: {
    health_status: string;
    status: string;
    slpfs_runtime_loaded: boolean;
    multimodal_runtime_loaded: boolean;
    ollama_status: string;
    vector_store_status: string;
    multimodal_store_status: string;
    current_root: string | null;
    multimodal_db_path: string | null;
    slpfs_runtime_error: string | null;
    multimodal_runtime_error: string | null;
    runtime_errors: {
      slpfs: string | null;
      multimodal: string | null;
    };
    subsystems: {
      slpfs: Record<string, unknown>;
      multimodal: Record<string, unknown>;
    };

    // Legacy compatibility fields
    backend_status?: string;
    runtime_loaded?: boolean;
    ollama_status_legacy?: string;
    model_status?: string;
    indexed_file_count?: number;
  };
  error: null | any;
  meta: any;
}

export const BACKEND_URL = "http://127.0.0.1:8000";

export async function checkHealth(): Promise<HealthResponse | null> {
  try {
    const response = await fetch(`${BACKEND_URL}/api/v1/health`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
    
    if (!response.ok) {
      return null;
    }
    
    return await response.json();
  } catch (error) {
    console.error("Health check failed:", error);
    return null;
  }
}

export async function waitForBackend(
  maxAttempts: number = 30,
  delayMs: number = 500
): Promise<boolean> {
  for (let i = 0; i < maxAttempts; i++) {
    const health = await checkHealth();
    if (health && health.ok) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, delayMs));
  }
  return false;
}
