export async function checkHealth(signal: AbortSignal): Promise<void> {
  const response = await fetch('/api/health', { signal })
  if (!response.ok) throw new Error('Health request failed')
  const body: unknown = await response.json()
  if (
    typeof body !== 'object' || body === null ||
    !('status' in body) || body.status !== 'ok' ||
    !('database' in body) || body.database !== 'sqlite'
  ) {
    throw new Error('Invalid health response')
  }
}
