import { useEffect, useState } from "react";
import { getMe, logoutEverywhere, type Me } from "./api";

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Bootstrap identity from the cookie session. A 401 means "not logged in";
    // the SSR site owns the auth pages, so we bounce there.
    getMe()
      .then(setMe)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <main style={wrap}>Loading…</main>;

  if (!me) {
    const next = encodeURIComponent("/app");
    return (
      <main style={wrap}>
        <h1>Shipyard</h1>
        <p>You are not signed in.</p>
        <a href={`/auth/login?next=${next}`}>Log in</a>
      </main>
    );
  }

  return (
    <main style={wrap}>
      <h1>Welcome back</h1>
      <p>
        Signed in as <strong>{me.email}</strong>
        {me.is_verified ? "" : " (unverified)"}
      </p>
      <p>This React shell runs same-origin on the cookie session — no token in JS.</p>
      <button
        onClick={async () => {
          // Revokes every session server-side; the now-dead cookie is ignored.
          await logoutEverywhere();
          window.location.href = "/";
        }}
      >
        Log out everywhere
      </button>
    </main>
  );
}

const wrap: React.CSSProperties = {
  maxWidth: 640,
  margin: "4rem auto",
  fontFamily: "system-ui, sans-serif",
  lineHeight: 1.5,
};
