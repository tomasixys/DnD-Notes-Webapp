export function withExpectedRevision(
  endpoint: string,
  revision: number,
  additional: Record<string, number> = {},
): string {
  const [path, existingQuery = ""] = endpoint.split("?", 2)
  const query = new URLSearchParams(existingQuery)
  query.set("expected_revision", String(revision))
  for (const [key, value] of Object.entries(additional)) {
    query.set(key, String(value))
  }
  return `${path}?${query.toString()}`
}
