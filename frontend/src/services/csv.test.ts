import { describe, expect, it } from 'vitest'
import { csvBoolean, csvDate, csvNumber, exportCsv, parseCsvObjects } from './csv'

describe('RFC 4180 CSV', () => {
  it('round trips commas, quotes, CRLF and multiline fields', () => {
    const csv = exportCsv(['name', 'notes'], [{ name: 'ACME, Inc.', notes: 'said "hi"\r\nnext line' }])
    expect(parseCsvObjects(csv, ['name', 'notes'])).toEqual([{ name: 'ACME, Inc.', notes: 'said "hi"\r\nnext line' }])
  })

  it('rejects unexpected headers and malformed typed values', () => {
    expect(() => parseCsvObjects('b,a\r\n1,2', ['a', 'b'])).toThrow(/headers/)
    expect(() => csvNumber('1x', 'mileage')).toThrow()
    expect(() => csvDate('08/01/2026', 'date')).toThrow()
    expect(() => csvBoolean('yes', 'partial_fillup')).toThrow()
  })
})
