// Scientific records are canonical backend JSON schemas; view helpers preserve all fields.
export type Data = Record<string, any>;
export async function api<T = Data>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch("/api" + path, {
    method,
    headers:
      body instanceof FormData ? {} : { "Content-Type": "application/json" },
    body:
      body === undefined
        ? undefined
        : body instanceof FormData
          ? body
          : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : "Request validation failed",
    );
  }
  return response.json();
}
export const money = (value: number = 0) => "$" + value.toFixed(4);
export const short = (value: string = "") => value.slice(0, 8);
