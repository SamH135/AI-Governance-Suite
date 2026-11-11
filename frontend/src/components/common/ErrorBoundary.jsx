import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import Button from '../ui/Button';
import Card from '../ui/Card';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Log error for debugging
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.setState({
      error,
      errorInfo
    });
    
    // Optional: Send error to monitoring service
    if (window.gtag) {
      window.gtag('event', 'exception', {
        description: error.toString(),
        fatal: false
      });
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    // Optional: Call parent retry function if provided
    if (this.props.onRetry) {
      this.props.onRetry();
    } else {
      // Reload the page as fallback
      window.location.reload();
    }
  };

  render() {
    if (this.state.hasError) {
      // Custom error UI
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.handleRetry);
      }

      // Default error UI
      return (
        <div className="flex items-center justify-center min-h-64 p-4">
          <Card className="max-w-md w-full">
            <Card.Header>
              <div className="flex items-center space-x-3">
                <AlertTriangle className="w-6 h-6 text-red-500" />
                <Card.Title>Something went wrong</Card.Title>
              </div>
            </Card.Header>
            <Card.Content>
              <div className="space-y-4">
                <p className="text-neutral-600">
                  {this.props.message || 'An unexpected error occurred while rendering this component.'}
                </p>
                
                {/* Show error details in development */}
                {process.env.NODE_ENV === 'development' && this.state.error && (
                  <details className="mt-4">
                    <summary className="text-sm text-neutral-500 cursor-pointer hover:text-neutral-700">
                      Error Details (Development)
                    </summary>
                    <div className="mt-2 p-3 bg-red-50 rounded-lg border border-red-200">
                      <code className="text-sm text-red-800 block whitespace-pre-wrap">
                        {this.state.error.toString()}
                        {this.state.errorInfo && this.state.errorInfo.componentStack}
                      </code>
                    </div>
                  </details>
                )}

                <div className="flex space-x-3">
                  <Button
                    onClick={this.handleRetry}
                    variant="primary"
                    size="sm"
                    className="flex items-center space-x-2"
                  >
                    <RefreshCw className="w-4 h-4" />
                    <span>Try Again</span>
                  </Button>
                  <Button
                    onClick={() => window.location.href = '/'}
                    variant="ghost"
                    size="sm"
                  >
                    Go Home
                  </Button>
                </div>
              </div>
            </Card.Content>
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}

// HOC wrapper for functional components
export const withErrorBoundary = (Component, errorBoundaryProps = {}) => {
  const WrappedComponent = (props) => (
    <ErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </ErrorBoundary>
  );
  
  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`;
  return WrappedComponent;
};

export default ErrorBoundary;