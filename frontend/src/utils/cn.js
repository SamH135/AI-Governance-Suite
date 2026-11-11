import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import logger from './logger.js';

export function cn(...inputs) {
  logger.debug(`cn utility called with ${inputs.length} inputs`, 'cn.js', 'cn');
  const result = twMerge(clsx(inputs));
  logger.debug(`cn utility returning: ${result}`, 'cn.js', 'cn');
  return result;
}