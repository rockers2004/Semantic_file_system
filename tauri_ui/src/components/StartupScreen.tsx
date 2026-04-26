import { useState, useEffect } from "react";
import { checkHealth } from "../api/health";

interface StartupScreenProps {
  onReady: () => void;
}

export function StartupScreen({ onReady }: StartupScreenProps) {
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const pollHealth = async () => {
      while (!isReady) {
        const health = await checkHealth();
        if (health && health.ok) {
          setIsReady(true);
          onReady();  // Notify parent -> ready to show main app
          break;
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
      backgroundColor: "#ffffff",
      fontFamily: "Inter, system-ui, sans-serif",
    }}>
      <h1 style={{ fontSize: "28px", fontWeight: "600", marginBottom: "16px" }}>My Files</h1>
      <div style={{ display: "flex", alignItems: "center", gap: "10px", color: "#86868b" }}>
        <div className="typing-indicator" style={{ display: "flex", gap: "4px" }}>
          <span style={{ width: "6px", height: "6px", background: "#86868b", borderRadius: "50%", animation: "bounce 1.4s infinite ease-in-out both", animationDelay: "-0.32s" }}></span>
          <span style={{ width: "6px", height: "6px", background: "#86868b", borderRadius: "50%", animation: "bounce 1.4s infinite ease-in-out both", animationDelay: "-0.16s" }}></span>
          <span style={{ width: "6px", height: "6px", background: "#86868b", borderRadius: "50%", animation: "bounce 1.4s infinite ease-in-out both" }}></span>
        </div>
        <p style={{ fontSize: "16px", margin: 0 }}>Starting up...</p>
      </div>
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: scale(0); }
          40% { transform: scale(1); }
        }
      `}</style>
    </div>
  );
}
