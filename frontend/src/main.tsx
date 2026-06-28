import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import "@fontsource-variable/archivo";
import "@fontsource-variable/jetbrains-mono";

import { App } from "./App";
import { AuthGate, AuthProvider } from "./auth/AuthProvider";
import "./styles.css";

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <AuthProvider>
      <AuthGate>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </AuthGate>
    </AuthProvider>
  </React.StrictMode>
);
