/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_API_KEY: string;
  readonly VITE_OLLAMA_URL: string;
  readonly VITE_OLLAMA_MODEL: string;
  readonly VITE_OLLAMA_DISABLED: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
