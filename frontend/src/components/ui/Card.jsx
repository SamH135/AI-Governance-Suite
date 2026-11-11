import React from 'react';
import { clsx } from 'clsx';

const Card = ({ children, className = '', ...props }) => {
  return (
    <div className={clsx('card p-6', className)} {...props}>
      {children}
    </div>
  );
};

const CardHeader = ({ children, className = '' }) => {
  return (
    <div className={clsx('mb-4', className)}>
      {children}
    </div>
  );
};

const CardTitle = ({ children, className = '' }) => {
  return (
    <h3 className={clsx('text-lg font-semibold text-neutral-900', className)}>
      {children}
    </h3>
  );
};

const CardDescription = ({ children, className = '' }) => {
  return (
    <p className={clsx('text-sm text-neutral-600 mt-1', className)}>
      {children}
    </p>
  );
};

const CardContent = ({ children, className = '' }) => {
  return (
    <div className={className}>
      {children}
    </div>
  );
};

Card.Header = CardHeader;
Card.Title = CardTitle;
Card.Description = CardDescription;
Card.Content = CardContent;

export default Card;