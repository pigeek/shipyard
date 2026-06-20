import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getMe, logoutEverywhere, type Me } from "./api";
import { SUPPORTED, setLocale } from "./i18n";

function LanguageSwitch() {
  const { t, i18n } = useTranslation();
  return (
    <p style={{ fontSize: "0.85rem" }}>
      {t("language")}:{" "}
      {SUPPORTED.map((lng) => (
        <button
          key={lng}
          onClick={() => setLocale(lng)}
          disabled={i18n.resolvedLanguage === lng}
          style={{ marginRight: 6 }}
        >
          {lng}
        </button>
      ))}
    </p>
  );
}

export default function App() {
  const { t } = useTranslation();
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Bootstrap identity from the cookie session. A 401 means "not logged in";
    // the SSR site owns the auth pages, so we bounce there.
    getMe()
      .then(setMe)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <main style={wrap}>{t("loading")}</main>;

  if (!me) {
    const next = encodeURIComponent("/app");
    return (
      <main style={wrap}>
        <h1>{t("appName")}</h1>
        <p>{t("notSignedIn")}</p>
        <a href={`/auth/login?next=${next}`}>{t("logIn")}</a>
        <LanguageSwitch />
      </main>
    );
  }

  return (
    <main style={wrap}>
      <h1>{t("welcomeBack")}</h1>
      <p>
        {t("signedInAs")} <strong>{me.email}</strong>
        {me.is_verified ? "" : t("unverified")}
      </p>
      <p>{t("cookieNote")}</p>
      <button
        onClick={async () => {
          // Revokes every session server-side; the now-dead cookie is ignored.
          await logoutEverywhere();
          window.location.href = "/";
        }}
      >
        {t("logOutEverywhere")}
      </button>
      <LanguageSwitch />
    </main>
  );
}

const wrap: React.CSSProperties = {
  maxWidth: 640,
  margin: "4rem auto",
  fontFamily: "system-ui, sans-serif",
  lineHeight: 1.5,
};
