import i18n from "i18next";
import { initReactI18next } from "react-i18next";

// Inline catalogs keep the seed simple; move to JSON + a backend loader as the
// app grows. The SSR site (gettext) and this SPA share the `locale` cookie, so
// switching language on either surface carries to the other.
const en = {
  loading: "Loading…",
  appName: "Shipyard",
  notSignedIn: "You are not signed in.",
  logIn: "Log in",
  welcomeBack: "Welcome back",
  signedInAs: "Signed in as",
  unverified: " (unverified)",
  cookieNote: "This React shell runs same-origin on the cookie session — no token in JS.",
  logOutEverywhere: "Log out everywhere",
  language: "Language",
};

const fr: typeof en = {
  loading: "Chargement…",
  appName: "Shipyard",
  notSignedIn: "Vous n'êtes pas connecté.",
  logIn: "Connexion",
  welcomeBack: "Bon retour",
  signedInAs: "Connecté en tant que",
  unverified: " (non vérifié)",
  cookieNote: "Cette interface React s'exécute en même origine sur la session cookie — aucun jeton en JS.",
  logOutEverywhere: "Déconnexion partout",
  language: "Langue",
};

export const SUPPORTED = ["en", "fr"] as const;

function cookieLocale(): string | undefined {
  const m = document.cookie.match(/(?:^|;\s*)locale=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : undefined;
}

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, fr: { translation: fr } },
  lng: cookieLocale() ?? navigator.language.split("-")[0],
  fallbackLng: "en",
  supportedLngs: [...SUPPORTED],
  interpolation: { escapeValue: false },
});

/** Persist the choice in the shared `locale` cookie and switch the SPA live. */
export function setLocale(lng: string): void {
  document.cookie = `locale=${lng};path=/;max-age=${60 * 60 * 24 * 365};samesite=lax`;
  void i18n.changeLanguage(lng);
}

export default i18n;
