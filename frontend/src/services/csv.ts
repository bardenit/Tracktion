export type CsvValue = unknown

export function parseCsv(text: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let field = ''
  let quoted = false
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i]
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { field += '"'; i += 1 }
      else if (ch === '"') quoted = false
      else field += ch
    } else if (ch === '"') {
      if (field) throw new Error('Unexpected quote in CSV field')
      quoted = true
    } else if (ch === ',') { row.push(field); field = '' }
    else if (ch === '\n') { row.push(field); rows.push(row); row = []; field = '' }
    else if (ch === '\r') {
      if (text[i + 1] === '\n') i += 1
      row.push(field); rows.push(row); row = []; field = ''
    } else field += ch
  }
  if (quoted) throw new Error('Unterminated quoted CSV field')
  if (field || row.length) { row.push(field); rows.push(row) }
  return rows
}

export function parseCsvObjects(text: string, headers: readonly string[]): Record<string, string>[] {
  const rows = parseCsv(text)
  if (!rows.length || rows[0].length !== headers.length || rows[0].some((h, i) => h !== headers[i])) {
    throw new Error(`CSV headers must be exactly: ${headers.join(',')}`)
  }
  return rows.slice(1).filter((r) => !(r.length === 1 && r[0] === '')).map((r, index) => {
    if (r.length !== headers.length) throw new Error(`CSV row ${index + 2} has ${r.length} columns; expected ${headers.length}`)
    return Object.fromEntries(headers.map((h, i) => [h, r[i]]))
  })
}

function quote(value: CsvValue): string {
  const raw = value == null ? '' : String(value)
  return /[",\r\n]/.test(raw) ? `"${raw.replace(/"/g, '""')}"` : raw
}

export function exportCsv(headers: readonly string[], rows: readonly Record<string, CsvValue>[]): string {
  return [headers.join(','), ...rows.map((row) => headers.map((h) => quote(row[h])).join(','))].join('\r\n')
}

export function csvNumber(value: string, field: string): number {
  if (!/^-?(?:\d+\.?\d*|\.\d+)$/.test(value)) throw new Error(`${field} must be a number`)
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) throw new Error(`${field} must be a finite number`)
  return parsed
}

export function csvDate(value: string, field: string, optional = false): string | undefined {
  if (!value && optional) return undefined
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(Date.parse(`${value}T00:00:00Z`))) throw new Error(`${field} must be YYYY-MM-DD`)
  return value
}

export function csvBoolean(value: string, field: string): boolean {
  if (value === 'true') return true
  if (value === 'false') return false
  throw new Error(`${field} must be true or false`)
}
