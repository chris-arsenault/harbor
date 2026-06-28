import {
  AuthenticationDetails,
  CognitoUser,
  CognitoUserPool,
  type CognitoUserSession,
} from "amazon-cognito-identity-js";

import { getAuthRuntimeConfig } from "./config";

export interface SessionSnapshot {
  accessToken: string;
  email: string | null;
  username: string | null;
}

export interface SignInChallenge {
  kind: "softwareTokenMfa";
  submitCode: (code: string) => Promise<SignInResult>;
}

export type SignInResult =
  | { kind: "authenticated"; session: SessionSnapshot }
  | { kind: "challenge"; challenge: SignInChallenge };

let cachedPool: CognitoUserPool | null = null;
let cachedPoolKey: string | null = null;

const ENROLL_VIA_AHARA_BUSINESS =
  "Multi-factor authentication is not set up for this account. Enroll an " +
  "authenticator in the Ahara account portal, then sign in here.";

function getPool(): CognitoUserPool | null {
  const config = getAuthRuntimeConfig();
  if (!config) return null;
  const key = `${config.cognitoUserPoolId}:${config.cognitoClientId}`;
  if (!cachedPool || cachedPoolKey !== key) {
    cachedPool = new CognitoUserPool({
      UserPoolId: config.cognitoUserPoolId,
      ClientId: config.cognitoClientId,
    });
    cachedPoolKey = key;
  }
  return cachedPool;
}

export function isAuthConfigured(): boolean {
  return getPool() != null;
}

export function getCurrentSession(): Promise<CognitoUserSession | null> {
  const user = getPool()?.getCurrentUser();
  if (!user) return Promise.resolve(null);
  return new Promise((resolve, reject) => {
    user.getSession((err: Error | null, session: CognitoUserSession | null) => {
      if (err) {
        reject(err);
        return;
      }
      resolve(session?.isValid() ? session : null);
    });
  });
}

export async function getAccessToken(): Promise<string | null> {
  const session = await getCurrentSession();
  return session?.getAccessToken().getJwtToken() ?? null;
}

export async function getSessionSnapshot(): Promise<SessionSnapshot | null> {
  const session = await getCurrentSession();
  if (!session) return null;
  const idPayload = session.getIdToken().decodePayload() as Record<string, unknown>;
  return {
    accessToken: session.getAccessToken().getJwtToken(),
    email: readString(idPayload.email),
    username:
      readString(idPayload["cognito:username"]) ??
      readString(idPayload.username) ??
      readString(idPayload.email),
  };
}

export function signIn(username: string, password: string): Promise<SignInResult> {
  const pool = getPool();
  if (!pool) return Promise.reject(new Error("Cognito auth is not configured"));
  const user = new CognitoUser({ Username: username, Pool: pool });
  const details = new AuthenticationDetails({ Username: username, Password: password });

  return new Promise<SignInResult>((resolve, reject) => {
    user.authenticateUser(details, buildAuthCallbacks(user, resolve, reject));
  });
}

export function signOut(): void {
  getPool()?.getCurrentUser()?.signOut();
}

function buildAuthCallbacks(
  user: CognitoUser,
  resolve: (result: SignInResult) => void,
  reject: (err: Error) => void
) {
  return {
    onSuccess: () => resolveAuthenticated(resolve, reject),
    onFailure: (err: Error) => reject(err),
    newPasswordRequired: () => reject(new Error("new password required")),
    totpRequired: () => resolve(mfaChallenge(user)),
    mfaSetup: () => reject(new Error(ENROLL_VIA_AHARA_BUSINESS)),
  };
}

function mfaChallenge(user: CognitoUser): SignInResult {
  return {
    kind: "challenge",
    challenge: {
      kind: "softwareTokenMfa",
      submitCode: (code: string) =>
        new Promise<SignInResult>((resolve, reject) => {
          user.sendMFACode(
            code.trim(),
            buildAuthCallbacks(user, resolve, reject),
            "SOFTWARE_TOKEN_MFA"
          );
        }),
    },
  };
}

function resolveAuthenticated(
  resolve: (result: SignInResult) => void,
  reject: (err: Error) => void
): void {
  getSessionSnapshot()
    .then((session) => {
      if (!session) throw new Error("session missing after login");
      resolve({ kind: "authenticated", session });
    })
    .catch((err: unknown) => {
      reject(err instanceof Error ? err : new Error(String(err)));
    });
}

function readString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}
