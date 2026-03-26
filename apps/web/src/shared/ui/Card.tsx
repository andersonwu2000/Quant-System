import type { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
}

export function Card({ children, className = '', hover }: CardProps) {
  return (
    <div className={`rounded-lg border border-white/10 bg-[#1a1a1a] p-5 ${
      hover ? 'transition-colors duration-150 hover:bg-[#262626] hover:border-white/15 cursor-pointer' : ''
    } ${className}`}>
      {children}
    </div>
  );
}
