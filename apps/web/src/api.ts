let ownerToken = "";
export function setToken(token: string) {
  ownerToken = token;
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${ownerToken}`,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data: unknown = await response.json();
  if (!response.ok) {
    const detail =
      typeof data === "object" && data !== null && "detail" in data
        ? String(data.detail)
        : "Request failed";
    throw new Error(detail);
  }
  return data as T;
}

export function units(value: number | string | bigint): string {
  const n = BigInt(value);
  const sign = n < 0n ? "-" : "";
  const absolute = n < 0n ? -n : n;
  return `${sign}${absolute / 1000000n}.${(absolute % 1000000n).toString().padStart(6, "0").replace(/0+$/, "") || "00"}`;
}
export function percent(part: string, total: bigint): string {
  return total === 0n ? "0" : ((BigInt(part) * 100n) / total).toString();
}
