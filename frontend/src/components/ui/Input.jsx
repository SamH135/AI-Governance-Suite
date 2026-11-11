import React from 'react';
import { clsx } from 'clsx';

const Input = ({
  label,
  error,
  className = '',
  ...props
}) => {
  const inputClasses = clsx(
    'input',
    error && 'border-red-300 focus:border-red-500 focus:ring-red-500',
    className
  );

  return (
    <div className="space-y-1">
      {label && (
        <label className="block text-sm font-medium text-neutral-700">
          {label}
        </label>
      )}
      <input
        className={inputClasses}
        {...props}
      />
      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}
    </div>
  );
};

export default Input;