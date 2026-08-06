// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

describe('service worker privacy contract', () => {
  const source = readFileSync(resolve(process.cwd(), 'public/sw.js'), 'utf8')

  it('never stores API responses and retains static shell caching', () => {
    const apiBranchStart = source.indexOf('if (isApiCall(url))')
    const staticBranchStart = source.indexOf('if (isStaticAsset(url))')
    const apiBranch = source.slice(apiBranchStart, staticBranchStart)
    expect(apiBranchStart).toBeGreaterThan(-1)
    expect(apiBranchStart).toBeLessThan(staticBranchStart)
    expect(apiBranch).not.toContain('cache.put')
    expect(source).toContain("c.addAll(['/', '/index.html'])")
  })

  it('supports an acknowledged legacy cache purge', () => {
    expect(source).toContain('PURGE_TRACKTION_CACHES')
    expect(source).toContain('event.ports[0].postMessage')
  })
})
