function storageKey(userId: number, name: string): string {
  return `tracktion-user:${userId}:${name}`
}

function sanitizeStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return [...new Set(value
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter(Boolean))]
}

export function getUserStringList(userId: number, name: string): string[] {
  try {
    return sanitizeStringList(JSON.parse(localStorage.getItem(storageKey(userId, name)) || '[]'))
  } catch {
    return []
  }
}

export function setUserStringList(userId: number, name: string, values: unknown): void {
  localStorage.setItem(storageKey(userId, name), JSON.stringify(sanitizeStringList(values)))
}
