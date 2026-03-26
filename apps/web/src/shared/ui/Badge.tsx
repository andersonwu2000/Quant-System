interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'profit' | 'loss' | 'warning' | 'info';
}

export function Badge({ children, variant = 'default' }: BadgeProps) {
  const colors = {
    default: 'bg-neutral-800 text-neutral-300',
    profit: 'bg-profit/10 text-profit',
    loss: 'bg-loss/10 text-loss',
    warning: 'bg-amber-500/10 text-amber-400',
    info: 'bg-blue-500/10 text-blue-400',
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colors[variant]}`}>
      {children}
    </span>
  );
}
