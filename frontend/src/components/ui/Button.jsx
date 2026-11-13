import { clsx } from 'clsx';
import LoadingSpinner from './LoadingSpinner';
import logger from '../../utils/logger.js';

const Button = ({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  className = '',
  ...props
}) => {
  logger.debug(`Button rendered: variant=${variant}, size=${size}, loading=${loading}, disabled=${disabled}`, 'Button.jsx', 'Button');
  const baseClasses = 'relative inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed pr-10';
  
  const variants = {
    primary: 'bg-brand-600 hover:bg-brand-700 text-white focus:ring-brand-500',
    secondary: 'bg-neutral-100 hover:bg-neutral-200 text-neutral-900 focus:ring-neutral-500',
    outline: 'border border-neutral-300 bg-white hover:bg-neutral-50 text-neutral-700 focus:ring-brand-500',
    ghost: 'hover:bg-neutral-100 text-neutral-700 focus:ring-neutral-500',
    danger: 'bg-red-600 hover:bg-red-700 text-white focus:ring-red-500'
  };

  const sizes = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base'
  };

  const classes = clsx(
    baseClasses,
    variants[variant],
    sizes[size],
    className
  );

  const handleClick = (e) => {
    if (props.onClick) {
      logger.debug('Button clicked', 'Button.jsx', 'handleClick');
      props.onClick(e);
    }
  };

  return (
    <button
      className={classes}
      disabled={disabled || loading}
      {...props}
      onClick={handleClick}
    >
      {loading && <LoadingSpinner size="sm" className="mr-2" />}
      {children}
    </button>
  );
};

export default Button;