import { useEffect, useRef, useState } from "react";

type ParticleSize = "small" | "medium" | "large";

interface Snowflake {
  x: number;
  y: number;
  size: number;
  sizeType: ParticleSize;
  speedY: number;
  speedX: number;
  opacity: number;
  targetOpacity: number;
  swayAmplitude: number;
  swayFrequency: number;
  swayOffset: number;
  rotation: number;
  rotationSpeed: number;
}

interface SnowAnimationProps {
  isActive: boolean;
}

const PARTICLE_CONFIG = {
  small: { size: 1.5, opacity: 0.4, speedMultiplier: 0.7 },
  medium: { size: 2.5, opacity: 0.65, speedMultiplier: 1 },
  large: { size: 4, opacity: 0.85, speedMultiplier: 1.3 },
};

export const SnowAnimation = ({ isActive }: SnowAnimationProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>();
  const snowflakesRef = useRef<Snowflake[]>([]);
  const isVisibleRef = useRef(true);
  const [isFadingOut, setIsFadingOut] = useState(false);
  const [shouldRender, setShouldRender] = useState(false);
  const reducedMotionRef = useRef(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    reducedMotionRef.current = mediaQuery.matches;

    const handleMotionPreferenceChange = (e: MediaQueryListEvent) => {
      reducedMotionRef.current = e.matches;
    };

    mediaQuery.addEventListener("change", handleMotionPreferenceChange);

    return () => {
      mediaQuery.removeEventListener("change", handleMotionPreferenceChange);
    };
  }, []);

  useEffect(() => {
    if (isActive) {
      setShouldRender(true);
      setIsFadingOut(false);
    } else {
      setIsFadingOut(true);
      const timer = setTimeout(() => {
        setShouldRender(false);
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [isActive]);

  useEffect(() => {
    if (!shouldRender) {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      return;
    }

    if (reducedMotionRef.current) {
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    const handleVisibilityChange = () => {
      isVisibleRef.current = document.visibilityState === "visible";
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    const getParticleCount = () => {
      const width = window.innerWidth;
      if (width < 768) return 80;
      if (width < 1200) return 150;
      return 250;
    };

    const getSizeType = (): ParticleSize => {
      const rand = Math.random();
      if (rand < 0.5) return "small";
      if (rand < 0.8) return "medium";
      return "large";
    };

    const SNOWFLAKE_COUNT = getParticleCount();
    snowflakesRef.current = [];

    for (let i = 0; i < SNOWFLAKE_COUNT; i++) {
      const sizeType = getSizeType();
      const config = PARTICLE_CONFIG[sizeType];
      const baseSpeed = canvas.height / 5000;

      snowflakesRef.current.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height - canvas.height,
        size: config.size,
        sizeType,
        speedY: (Math.random() * 1.5 + 1.2) * baseSpeed * config.speedMultiplier * 2.5,
        speedX: (Math.random() - 0.5) * 0.3,
        opacity: 0,
        targetOpacity: config.opacity,
        swayAmplitude: Math.random() * 25 + 15,
        swayFrequency: Math.random() * 0.0012 + 0.0006,
        swayOffset: Math.random() * Math.PI * 2,
        rotation: Math.random() * Math.PI * 2,
        rotationSpeed: (Math.random() - 0.5) * 0.015,
      });
    }

    const animate = (time: number) => {
      if (!isVisibleRef.current) {
        animationRef.current = requestAnimationFrame(animate);
        return;
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      snowflakesRef.current.forEach((flake) => {
        if (isFadingOut) {
          flake.opacity = Math.max(0, flake.opacity - 0.015);
        } else {
          flake.opacity = Math.min(flake.targetOpacity, flake.opacity + 0.008);
        }

        if (flake.opacity <= 0) return;

        const sway = Math.sin(time * flake.swayFrequency + flake.swayOffset) * flake.swayAmplitude;

        flake.y += flake.speedY;
        flake.x += flake.speedX + sway * 0.012;
        flake.rotation += flake.rotationSpeed;

        if (flake.y > canvas.height + 10) {
          flake.y = -10;
          flake.x = Math.random() * canvas.width;
          if (!isFadingOut) {
            flake.opacity = 0;
          }
        }

        if (flake.x > canvas.width + 30) {
          flake.x = -30;
        } else if (flake.x < -30) {
          flake.x = canvas.width + 30;
        }

        ctx.save();
        ctx.translate(flake.x, flake.y);
        ctx.rotate(flake.rotation);

        ctx.beginPath();
        ctx.arc(0, 0, flake.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 255, 255, ${flake.opacity})`;
        ctx.fill();

        ctx.restore();
      });

      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener("resize", resizeCanvas);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [shouldRender, isFadingOut]);

  if (!shouldRender) return null;

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none"
      style={{
        zIndex: 5,
        background: "transparent",
      }}
      aria-hidden="true"
    />
  );
};
