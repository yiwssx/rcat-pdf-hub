"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import {
  ApiHttpError, AuthConfig, AuthMe, getAuthConfig, getMe, ldapLogin,
  logoutSession, SESSION_AUTH,
} from "../../lib/api";

type Phase = "checking" | "authenticated" | "unauthenticated" | "error";
type AuthState = {
  phase: Phase;
  config: AuthConfig | null;
  identity: AuthMe | null;
  error: string;
};
type AuthContextValue = AuthState & {
  retry: () => Promise<void>;
  signInSession: () => Promise<void>;
  signInLdap: (username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);
const initialState: AuthState = { phase: "checking", config: null, identity: null, error: "" };

export function PdfHubAuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>(initialState);
  // Ignore stale network completions after logout, retry or provider unmount.
  const revision = useRef(0);

  const retry = useCallback(async () => {
    const current = ++revision.current;
    setState(previous => ({ ...previous, phase: "checking", identity: null, error: "" }));
    try {
      const config = await getAuthConfig();
      if (current !== revision.current) return;
      try {
        const identity = await getMe(SESSION_AUTH);
        if (current === revision.current) setState({ phase: "authenticated", config, identity, error: "" });
      } catch (error) {
        if (current !== revision.current) return;
        setState({
          phase: error instanceof ApiHttpError && error.status === 401 ? "unauthenticated" : "error",
          config,
          identity: null,
          error: error instanceof ApiHttpError && error.status === 401 ? "" : "ไม่สามารถตรวจสอบสถานะบัญชีได้ โปรดลองอีกครั้ง",
        });
      }
    } catch {
      if (current === revision.current) setState({
        phase: "error", config: null, identity: null,
        error: "ไม่สามารถเชื่อมต่อระบบยืนยันตัวตนได้ โปรดลองอีกครั้ง",
      });
    }
  }, []);

  useEffect(() => {
    void retry();
    return () => { revision.current += 1; };
  }, [retry]);

  async function signInSession() {
    const current = ++revision.current;
    const identity = await getMe(SESSION_AUTH);
    if (current === revision.current) setState(previous => ({
      ...previous, phase: "authenticated", identity, error: "",
    }));
  }

  async function signInLdap(username: string, password: string) {
    const current = ++revision.current;
    const identity = await ldapLogin(username, password);
    if (current === revision.current) setState(previous => ({
      ...previous, phase: "authenticated", identity, error: "",
    }));
  }

  async function signOut() {
    revision.current += 1;
    try {
      await logoutSession();
    } finally {
      setState(previous => ({ ...previous, phase: "unauthenticated", identity: null, error: "" }));
    }
  }

  return (
    <AuthContext.Provider value={{ ...state, retry, signInSession, signInLdap, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function usePdfHubAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("PdfHubAuthProvider is required");
  return context;
}
