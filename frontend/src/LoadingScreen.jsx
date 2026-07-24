import { useEffect, useState } from 'react'

export function LoadingScreen() {
  const [isVisible, setIsVisible] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false)
    }, 1200)
    return () => clearTimeout(timer)
  }, [])

  if (!isVisible) return null

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100%',
      height: '100%',
      background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      flexDirection: 'column',
      gap: '32px',
    }}>
      {/* Rocket Animation */}
      <div style={{
        fontSize: '80px',
        animation: 'rocket-launch 1s cubic-bezier(0.34, 1.56, 0.64, 1) forwards',
        transformOrigin: 'center center',
      }}>
        🚀
      </div>

      {/* Text */}
      <div style={{ textAlign: 'center' }}>
        <h1 style={{
          fontSize: '36px',
          fontWeight: '700',
          color: '#0f172a',
          margin: '0 0 8px 0',
          letterSpacing: '-0.5px',
        }}>
          ChainVigil
        </h1>
        <p style={{
          fontSize: '13px',
          color: '#64748b',
          margin: 0,
          letterSpacing: '1px',
          textTransform: 'uppercase',
          fontWeight: '500',
        }}>
          Initializing Detection Engine
        </p>
      </div>

      <style>{`
        @keyframes rocket-launch {
          0% {
            transform: translateY(100px) scale(0.6) rotate(45deg);
            opacity: 0;
          }
          10% {
            transform: translateY(80px) scale(0.8) rotate(20deg);
            opacity: 1;
          }
          50% {
            transform: translateY(-20px) rotate(-10deg) scale(1);
            opacity: 1;
          }
          100% {
            transform: translateY(-200px) rotate(0deg) scale(0.8);
            opacity: 0;
          }
        }
      `}</style>
    </div>
  )
}

export default LoadingScreen
