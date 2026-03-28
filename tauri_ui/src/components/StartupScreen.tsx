import { useState, useEffect } from "react";
import { checkHealth } from "../api/health";

interface StartupScreenProps {
  onReady: () => void;
}

export function StartupScreen({ onReady }: StartupScreenProps) {
  const [status, setStatus] = useState("Starting backend...");
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const pollHealth = async () => {
      while (!isReady) {
        const health = await checkHealth();
        if (health && health.ok) {
          setStatus("✓ Backend Ready");
          setIsReady(true);
          onReady();  // Notify parent -> ready to show main app
          break;
        } else {
          setStatus("Waiting for backend... (ensure backend is running)");
        }
        // If not ready, wait 500ms and try again
        await new Promise((resolve) => setTimeout(resolve, 500));
      }
    };

    pollHealth();
  }, [isReady, onReady]);

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
      alignItems: "center",
      height: "100vh",
      backgroundColor: "#f5f5f5",
      fontFamily: "sans-serif",
    }}>
      <h1>SLPFS Desktop</h1>
      <p style={{ fontSize: "18px", color: "#666" }}>{status}</p>
    </div>
  );
}