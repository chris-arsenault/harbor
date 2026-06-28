import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { getAuthRuntimeConfig, isAuthRequired } from "./config";
import {
  getSessionSnapshot,
  isAuthConfigured,
  signIn,
  signOut,
  type SessionSnapshot,
  type SignInChallenge,
  type SignInResult,
} from "./cognito";
import "./AuthProvider.css";

type AuthState =
  | { kind: "loading" }
  | { kind: "disabled" }
  | { kind: "configurationError" }
  | { kind: "anonymous"; error: string | null }
  | { kind: "mfa"; challenge: SignInChallenge; error: string | null; pending: boolean }
  | { kind: "authenticated"; session: SessionSnapshot };

interface AuthContextValue {
  state: AuthState;
  login: (username: string, password: string) => Promise<void>;
  submitMfaCode: (code: string) => Promise<void>;
  cancelMfa: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { readonly children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    void loadInitialAuthState((next) => {
      if (!cancelled) setState(next);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      state,
      login: async (username, password) => login(setState, username, password),
      submitMfaCode: async (code) => submitMfaCode(state, setState, code),
      cancelMfa: () => {
        signOut();
        setState({ kind: "anonymous", error: null });
      },
      logout: () => {
        signOut();
        setState({ kind: "anonymous", error: null });
      },
    }),
    [state]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function AuthGate({ children }: { readonly children: ReactNode }) {
  const { state, login, submitMfaCode, cancelMfa, logout } = useAuth();
  if (state.kind === "loading") return <LoadingScreen />;
  if (state.kind === "disabled") return <>{children}</>;
  if (state.kind === "configurationError") return <ConfigurationError />;
  if (state.kind === "mfa") {
    return (
      <MfaScreen
        error={state.error}
        pending={state.pending}
        onCancel={cancelMfa}
        onSubmit={submitMfaCode}
      />
    );
  }
  if (state.kind === "authenticated") {
    return (
      <AuthenticatedShell session={state.session} onLogout={logout}>
        {children}
      </AuthenticatedShell>
    );
  }
  return <LoginScreen error={state.error} onLogin={login} />;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}

async function loadInitialAuthState(apply: (state: AuthState) => void): Promise<void> {
  if (!isAuthConfigured()) {
    apply(isAuthRequired() ? { kind: "configurationError" } : { kind: "disabled" });
    return;
  }
  try {
    const session = await getSessionSnapshot();
    apply(session ? { kind: "authenticated", session } : { kind: "anonymous", error: null });
  } catch (err) {
    apply({
      kind: "anonymous",
      error: err instanceof Error ? err.message : "authentication failed",
    });
  }
}

async function login(
  setState: (state: AuthState) => void,
  username: string,
  password: string
): Promise<void> {
  setState({ kind: "loading" });
  try {
    applySignInResult(setState, await signIn(username, password));
  } catch (err) {
    setState({ kind: "anonymous", error: err instanceof Error ? err.message : "login failed" });
  }
}

async function submitMfaCode(
  state: AuthState,
  setState: (state: AuthState) => void,
  code: string
): Promise<void> {
  if (state.kind !== "mfa") return;
  setState({ kind: "mfa", challenge: state.challenge, error: null, pending: true });
  try {
    applySignInResult(setState, await state.challenge.submitCode(code));
  } catch (err) {
    setState({
      kind: "mfa",
      challenge: state.challenge,
      error: err instanceof Error ? err.message : "verification failed",
      pending: false,
    });
  }
}

function applySignInResult(setState: (state: AuthState) => void, result: SignInResult): void {
  if (result.kind === "authenticated") {
    setState({ kind: "authenticated", session: result.session });
    return;
  }
  setState({ kind: "mfa", challenge: result.challenge, error: null, pending: false });
}

function AuthenticatedShell({
  children,
  onLogout,
  session,
}: {
  readonly children: ReactNode;
  readonly onLogout: () => void;
  readonly session: SessionSnapshot;
}) {
  return (
    <div className="auth-app">
      <div className="auth-status">
        <span>{session.username ?? session.email ?? "signed in"}</span>
        <button type="button" onClick={onLogout}>
          sign out
        </button>
      </div>
      {children}
    </div>
  );
}

function LoginScreen({
  error,
  onLogin,
}: {
  readonly error: string | null;
  readonly onLogin: (username: string, password: string) => Promise<void>;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const configured = getAuthRuntimeConfig() != null;

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await onLogin(username, password);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="auth-card" onSubmit={(event) => void submit(event)}>
      <AuthTitle title="Authenticate to continue" />
      {error && <div className="auth-error">{error}</div>}
      <AuthField label="Username or email" value={username} onValue={setUsername} />
      <AuthField label="Password" type="password" value={password} onValue={setPassword} />
      <button disabled={!configured || submitting || !username.trim() || !password} type="submit">
        {submitting ? "signing in..." : "sign in"}
      </button>
    </form>
  );
}

function MfaScreen({
  error,
  onCancel,
  onSubmit,
  pending,
}: {
  readonly error: string | null;
  readonly onCancel: () => void;
  readonly onSubmit: (code: string) => Promise<void>;
  readonly pending: boolean;
}) {
  const [code, setCode] = useState("");
  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSubmit(code);
    setCode("");
  };

  return (
    <form className="auth-card" onSubmit={(event) => void submit(event)}>
      <AuthTitle title="Two-factor authentication" />
      {error && <div className="auth-error">{error}</div>}
      <AuthField label="Authenticator code" value={code} onValue={setCode} numeric />
      <button disabled={pending || code.length < 6} type="submit">
        {pending ? "verifying..." : "verify"}
      </button>
      <button disabled={pending} type="button" onClick={onCancel}>
        back to sign in
      </button>
    </form>
  );
}

function AuthField({
  label,
  numeric,
  onValue,
  type = "text",
  value,
}: {
  readonly label: string;
  readonly numeric?: boolean;
  readonly onValue: (value: string) => void;
  readonly type?: "password" | "text";
  readonly value: string;
}) {
  return (
    <label className="auth-field">
      <span>{label}</span>
      <input
        autoComplete={type === "password" ? "current-password" : "username"}
        inputMode={numeric ? "numeric" : undefined}
        maxLength={numeric ? 6 : undefined}
        type={type}
        value={value}
        onChange={(event) => onValue(numeric ? onlyDigits(event.target.value) : event.target.value)}
      />
    </label>
  );
}

function AuthTitle({ title }: { readonly title: string }) {
  return (
    <>
      <div className="auth-eyebrow">harbor</div>
      <h1>{title}</h1>
    </>
  );
}

function ConfigurationError() {
  return (
    <div className="auth-card">
      <AuthTitle title="Authentication is not configured" />
      <div className="auth-error">
        Harbor requires Cognito runtime config. Set the user pool and app client IDs.
      </div>
    </div>
  );
}

function LoadingScreen() {
  return <div className="auth-loading">checking session...</div>;
}

function onlyDigits(value: string): string {
  return value.replace(/\D/g, "");
}
