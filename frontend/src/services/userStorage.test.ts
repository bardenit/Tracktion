import { describe, expect, it } from 'vitest'
import { getUserStringList, setUserStringList } from './userStorage'

describe('userStorage', () => {
  it.each(['{', '{}', '["oil", 4, null, "", " oil "]'])('sanitizes malformed custom lists', (stored) => {
    localStorage.setItem('tracktion-user:7:services', stored)
    expect(getUserStringList(7, 'services')).toEqual(stored.startsWith('[') ? ['oil'] : [])
  })

  it('namespaces lists by user', () => {
    setUserStringList(1, 'services', ['Oil'])
    setUserStringList(2, 'services', ['Tires'])
    expect(getUserStringList(1, 'services')).toEqual(['Oil'])
    expect(getUserStringList(2, 'services')).toEqual(['Tires'])
  })
})
