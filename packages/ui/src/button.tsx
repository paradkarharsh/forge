import type { ButtonHTMLAttributes } from 'react';
export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement>;
export function Button({ className, type = 'button', ...props }: ButtonProps) { const classes = ['forge-button', className].filter(Boolean).join(' '); return <button {...props} className={classes} type={type} />; }
