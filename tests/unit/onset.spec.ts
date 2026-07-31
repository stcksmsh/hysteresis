import { describe, it, expect } from 'vitest'
import { SpectralFlux } from '../../src/audio/worklet/onset'

describe('SpectralFlux', () => {
  it('is zero for an unchanging spectrum', () => {
    const flux = new SpectralFlux(4)
    const mags = new Float32Array([1, 2, 3, 4])
    flux.update(mags) // seeds internal previous-spectrum state
    expect(flux.update(mags)).toBe(0)
  })

  it('sums only positive bin-to-bin increases, ignoring decreases', () => {
    const flux = new SpectralFlux(4)
    flux.update(new Float32Array([1, 1, 1, 1]))
    // bin 0: +2 (counts), bin 1: -0.5 (ignored), bin 2: +1 (counts), bin 3: unchanged
    const result = flux.update(new Float32Array([3, 0.5, 2, 1]))
    expect(result).toBeCloseTo(2 + 1, 5)
  })

  it('reports a spike on a sudden broadband jump', () => {
    const flux = new SpectralFlux(4)
    flux.update(new Float32Array([0, 0, 0, 0]))
    const spike = flux.update(new Float32Array([5, 5, 5, 5]))
    expect(spike).toBeCloseTo(20, 5)
  })
})
