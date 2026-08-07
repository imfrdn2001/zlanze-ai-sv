import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

class AppErrorBoundary extends React.Component<
  React.PropsWithChildren,
  { error: Error | null }
> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error("Zlanze AI frontend failed", error);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <main className="startup-error">
        <h1>Zlanze AI could not load</h1>
        <p>{this.state.error.message}</p>
        <button
          onClick={() => {
            localStorage.removeItem("zlanze-ai-advisor-sessions-v1");
            localStorage.removeItem("zlanze-ai-advisor-active-session-v1");
            window.location.reload();
          }}
        >
          Repair local session and reload
        </button>
      </main>
    );
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppErrorBoundary><App /></AppErrorBoundary>
  </React.StrictMode>,
);
