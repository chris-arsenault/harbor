import { afterEach, expect, test } from "vitest";

import { getAuthRuntimeConfig, isAuthRequired } from "./config";

afterEach(() => {
  window.__APP_CONFIG__ = undefined;
});

test("runtime auth config reads Cognito IDs and auth-required flag", () => {
  window.__APP_CONFIG__ = {
    authRequired: "true",
    cognitoUserPoolId: "pool-id",
    cognitoClientId: "client-id",
  };

  expect(isAuthRequired()).toBe(true);
  expect(getAuthRuntimeConfig()).toEqual({
    cognitoUserPoolId: "pool-id",
    cognitoClientId: "client-id",
  });
});

test("missing runtime auth config is not required in test and local shells", () => {
  expect(isAuthRequired()).toBe(false);
  expect(getAuthRuntimeConfig()).toBeNull();
});
