import React from 'react'

/* ===== UI PRIMITIVES — Deep Research Engine ===== */
/* Style in components.css. No external UI lib. */

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: 'sm' | 'md'
}
export function Button({ variant = 'primary', size = 'md', className = '', ...props }: ButtonProps) {
  const cls = `btn-${variant}${size === 'sm' ? ' btn-sm' : ''}${className ? ` ${className}` : ''}`
  return <button className={cls} {...props} />
}

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}
export function Input({ className = '', ...props }: InputProps) {
  return <input className={`input${className ? ` ${className}` : ''}`} {...props} />
}

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {}
export function Card({ className = '', ...props }: CardProps) {
  return <div className={`card${className ? ` ${className}` : ''}`} {...props} />
}

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'info'

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
}
export function Badge({ variant = 'default', className = '', ...props }: BadgeProps) {
  const cls = variant === 'default' ? 'badge' : `badge badge-${variant}`
  return <span className={`${cls}${className ? ` ${className}` : ''}`} {...props} />
}

interface TabsProps {
  value: string
  onChange: (value: string) => void
  tabs: Array<{ value: string; label: string }>
  label?: string
}
export function Tabs({ value, onChange, tabs, label }: TabsProps) {
  return (
    <div className="tabs" role="tablist" aria-label={label ?? 'Tabs'}>
      {tabs.map((t) => (
        <button
          key={t.value}
          role="tab"
          aria-selected={value === t.value}
          data-state={value === t.value ? 'active' : 'inactive'}
          className="tabs-trigger"
          onClick={() => onChange(t.value)}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}

interface DrawerProps {
  open: boolean
  title: string
  onClose: () => void
  children: React.ReactNode
  footer?: React.ReactNode
}
export function Drawer({ open, title, onClose, children, footer }: DrawerProps) {
  if (!open) return null
  return (
    <>
      <div className="drawer-overlay" onClick={onClose} aria-hidden="true" />
      <div className="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <div className="drawer-header">
          <h2 className="drawer-title" id="drawer-title">{title}</h2>
          <button className="drawer-close" onClick={onClose} aria-label="Fechar painel">
            <span aria-hidden="true">✕</span>
          </button>
        </div>
        <div className="drawer-body">{children}</div>
        {footer ? <div className="drawer-footer">{footer}</div> : null}
      </div>
    </>
  )
}