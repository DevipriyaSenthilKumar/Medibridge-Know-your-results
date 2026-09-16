import { useCallback, useState } from "react";

const STORE_KEY = "medibridge.auth";

function readStored() {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export default function useAuth() {
  const [auth, setAuth] = useState(readStored);

  const login = useCallback(async (email, password) => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email.trim(), password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Login failed.");
    }
    const data = await res.json();
    localStorage.setItem(STORE_KEY, JSON.stringify(data));
    setAuth(data);
    return data;
  }, []);

  const signup = useCallback(async (email, password) => {
    const res = await fetch("/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email.trim(), password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Sign up failed.");
    }
    const data = await res.json();
    localStorage.setItem(STORE_KEY, JSON.stringify(data));
    setAuth(data);
    return data;
  }, []);

  const logout = useCallback(async () => {
    if (auth?.token) {
      try {
        await fetch("/api/auth/logout", {
          method: "POST",
          headers: { Authorization: `Bearer ${auth.token}` },
        });
      } catch {
        /* best-effort server-side token revoke */
      }
    }
    localStorage.removeItem(STORE_KEY);
    setAuth(null);
  }, [auth]);

  const authHeaders = useCallback(
    () => (auth?.token ? { Authorization: `Bearer ${auth.token}` } : {}),
    [auth]
  );

  return { auth, login, signup, logout, authHeaders };
}