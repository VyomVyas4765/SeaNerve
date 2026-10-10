// Small inline icons, so nothing loads from the network.
import type { ReactNode } from 'react'

type P = { size?: number }

const svg = (size: number, children: ReactNode, fill = false) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill={fill ? 'currentColor' : 'none'}
    stroke={fill ? 'none' : 'currentColor'}
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    {children}
  </svg>
)

export const PlayIcon = ({ size = 16 }: P) => svg(size, <path d="M7 4.5v15l12.5-7.5z" />, true)
export const PauseIcon = ({ size = 16 }: P) =>
  svg(
    size,
    <>
      <rect x="6" y="4.5" width="4" height="15" rx="1" />
      <rect x="14" y="4.5" width="4" height="15" rx="1" />
    </>,
    true,
  )
export const RestartIcon = ({ size = 16 }: P) =>
  svg(
    size,
    <>
      <path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1" />
      <path d="M3.5 4v4.5H8" />
    </>,
  )
export const CheckIcon = ({ size = 14 }: P) => svg(size, <path d="M5 12.5l4.5 4.5L19 7.5" />)
export const CrossIcon = ({ size = 14 }: P) => svg(size, <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />)
export const FitIcon = ({ size = 15 }: P) =>
  svg(size, <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />)
export const LogoIcon = ({ size = 26 }: P) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
    <rect width="32" height="32" rx="8" fill="#12223a" />
    <path
      d="M4 18c2.5-5 4.5-5 6.5 0s4 5 6 0 4-11 6-11 3.5 8 5.5 11"
      fill="none"
      stroke="#2cc5b8"
      strokeWidth="2.6"
      strokeLinecap="round"
    />
  </svg>
)
