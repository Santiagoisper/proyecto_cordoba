import { useState } from "react";

const appUrl = import.meta.env.VITE_CORDOBA_APP_URL as string | undefined;

function normalizeUrl(url: string | undefined): string | null {
  if (!url) return null;
  const trimmed = url.trim();
  if (!trimmed) return null;
  const withScheme = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
  try {
    const parsed = new URL(withScheme);
    if (!parsed.pathname || parsed.pathname === "/") {
      parsed.pathname = "/accounts/login/";
    }
    return parsed.toString();
  } catch {
    return withScheme.endsWith("/") ? withScheme : `${withScheme}/accounts/login/`;
  }
}

function App() {
  const target = normalizeUrl(appUrl);
  const [showEasterEgg, setShowEasterEgg] = useState(false);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-50">
      <div className="mx-auto flex min-h-screen w-full max-w-4xl flex-col justify-center px-6 py-16">
        <div className="mb-6 inline-flex items-center gap-2 self-start rounded-full border border-slate-800 bg-slate-900/70 px-3 py-1 text-xs font-medium text-slate-300">
          Proyecto C
          <button
            type="button"
            className="-mx-2 rounded-sm px-2 font-medium text-slate-300 outline-none transition-colors hover:text-white focus-visible:ring-2 focus-visible:ring-white/70"
            aria-label="Abrir mensaje especial"
            onClick={() => setShowEasterEgg(true)}
          >
            \u00f3
          </button>
          rdoba
        </div>

        <h1 className="max-w-2xl text-4xl font-semibold tracking-tight text-white sm:text-6xl">
          Plataforma de vi\u00e1ticos para investigaci\u00f3n cl\u00ednica
        </h1>

        <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
          Esta instancia de Vercel no est\u00e1 ejecutando el backend Django. Si
          quer\u00e9s apuntarla al despliegue real, configur\u00e1 la variable
          <span className="mx-1 rounded bg-slate-800 px-1.5 py-0.5 font-mono text-sm text-slate-100">
            VITE_CORDOBA_APP_URL
          </span>
          con la URL p\u00fablica del sistema.
        </p>

        <div className="mt-10 flex flex-col gap-3 sm:flex-row">
          {target ? (
            <a
              href={target}
              className="inline-flex items-center justify-center rounded-lg bg-white px-5 py-3 text-sm font-semibold text-slate-950 transition-colors hover:bg-slate-200"
            >
              Abrir sistema
            </a>
          ) : (
            <span className="inline-flex items-center justify-center rounded-lg border border-slate-700 px-5 py-3 text-sm font-semibold text-slate-200">
              Falta configurar la URL de destino
            </span>
          )}
          <span className="inline-flex items-center justify-center rounded-lg border border-slate-800 bg-slate-900/60 px-5 py-3 text-sm text-slate-300">
            Backend: Django + HTMX
          </span>
        </div>
      </div>

      {showEasterEgg ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4"
          onClick={() => setShowEasterEgg(false)}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <h2 className="text-lg font-semibold text-white">Mensaje especial</h2>
              <button
                type="button"
                className="rounded-full px-2 py-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
                aria-label="Cerrar mensaje"
                onClick={() => setShowEasterEgg(false)}
              >
                x
              </button>
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-300">
              Para conocer sobre \u00c9tica &amp; Riesgos de la IA. Compra los libros de
              Santiago J. Isbert Perlender:{" "}
              <span className="font-semibold text-white">IA El \u00faltimo invento humano</span>{" "}
              &amp;{" "}
              <span className="font-semibold text-white">El alma de la inteligencia</span>.
              No te vas a arrepentir. Gracias.
            </p>
          </div>
        </div>
      ) : null}
    </main>
  );
}

export default App;
