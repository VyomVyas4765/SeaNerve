// 256-entry lookup for waterfall cells: 128 is zero (warm white), above is red, below is blue.
const ZERO = [243, 239, 233]
const POS = [178, 24, 43]
const NEG = [33, 102, 172]

export const ZERO_CSS = `rgb(${ZERO.join(',')})`

export const LUT: Uint8ClampedArray = (() => {
  const lut = new Uint8ClampedArray(256 * 4)
  for (let i = 0; i < 256; i++) {
    const v = (i - 128) / 127
    const end = v >= 0 ? POS : NEG
    const t = Math.min(1, Math.abs(v)) ** 1.2 // noise stays a faint speckle
    for (let c = 0; c < 3; c++) lut[i * 4 + c] = ZERO[c] + (end[c] - ZERO[c]) * t
    lut[i * 4 + 3] = 255
  }
  return lut
})()
