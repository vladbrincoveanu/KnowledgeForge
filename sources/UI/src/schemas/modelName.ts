/**
 * Client-side mirror of the backend `ModelName` Pydantic type.
 * Server is the source of truth — this is for pre-flight validation only.
 */
export const MODEL_NAME_RE =
  /^(anthropic\/[A-Za-z0-9._-]+|MiniMax-[A-Za-z0-9._-]+)$/;

export function isValidModelName(s: string): boolean {
  return MODEL_NAME_RE.test(s);
}
