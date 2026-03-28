export interface HealthResponse {
  ok: boolean;
  data: {
    backend: string;
    ollama: string;
    model: string;
  };
  error: null | any;
  meta: any;
}

export const BACKEND_URL = "http://127.0.0.1:8765";

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