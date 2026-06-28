export interface AuthRuntimeConfig {
  cognitoUserPoolId: string;
  cognitoClientId: string;
}

declare global {
  interface Window {
    __APP_CONFIG__?: {
      authRequired?: boolean | string;
      cognitoUserPoolId?: string;
      cognitoClientId?: string;
    };
  }
}

export function getAuthRuntimeConfig(): AuthRuntimeConfig | null {
  const raw = window.__APP_CONFIG__;
  if (!raw?.cognitoUserPoolId || !raw?.cognitoClientId) return null;
  return {
    cognitoUserPoolId: raw.cognitoUserPoolId,
    cognitoClientId: raw.cognitoClientId,
  };
}

export function isAuthRequired(): boolean {
  const value = window.__APP_CONFIG__?.authRequired;
  if (typeof value === "boolean") return value;
  if (typeof value === "string") return value.toLowerCase() === "true";
  return false;
}
