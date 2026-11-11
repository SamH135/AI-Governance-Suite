# Unified AI Compliance Platform - Frontend

A modern React-based frontend application that combines features from three AI compliance products into a unified platform.

## Features

- **Authentication System**: Login, registration, and user management
- **AI Systems Management**: CRUD operations for AI systems
- **Compliance Testing**: Configure and run compliance tests with multiple evaluators
- **Prompt Engineering**: Advanced prompt creation and optimization tools
- **Document Generation**: Multi-step compliance document generation
- **Real-time Dashboard**: Live metrics and system monitoring
- **Responsive Design**: Mobile-first approach with desktop optimization

## Technology Stack

- **React 18.3.1** - Modern React with hooks and context
- **Vite 5.1.4** - Fast build tool and development server
- **Tailwind CSS 3.4.14** - Utility-first CSS framework
- **Material-UI 6.x** - React component library
- **React Router DOM 6.28.0** - Client-side routing
- **Recharts 2.13.3** - Chart and visualization library
- **Lucide React** - Modern icon library
- **Monaco Editor** - Code editor for prompt engineering

## Project Structure

```
src/
├── components/          # Reusable components
│   ├── ui/             # Basic UI components (Button, Input, Card, etc.)
│   └── layout/         # Layout components (Sidebar, Header, MainLayout)
├── pages/              # Page components
│   ├── auth/           # Authentication pages
│   ├── dashboard/      # Dashboard pages
│   ├── compliance/     # Compliance testing pages
│   ├── prompts/        # Prompt engineering pages
│   └── documents/      # Document generation pages
├── contexts/           # React contexts for state management
├── services/           # API service functions
├── hooks/              # Custom React hooks
├── utils/              # Utility functions
├── constants/          # Application constants
└── styles/             # Global styles and CSS
```

## Getting Started

### Prerequisites

- Node.js 18.0.0 or higher
- npm 9.0.0 or higher

### Installation

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm run dev
```

3. Open your browser and navigate to `http://localhost:3000`

### Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint
- `npm run lint:fix` - Fix ESLint issues
- `npm run format` - Format code with Prettier
- `npm test` - Run tests
- `npm run test:coverage` - Run tests with coverage

## Key Components

### Authentication
- Login and registration pages with form validation
- JWT token management and automatic refresh
- Protected routes and role-based access control

### Dashboard
- Real-time metrics and system health monitoring
- Quick action cards for common tasks
- Recent activity and test results

### Compliance Testing
- AI systems management with CRUD operations
- Test configuration with multiple evaluators
- Results visualization and export capabilities

### Prompt Engineering
- Monaco editor integration for prompt editing
- Template library and prompt optimization
- Real-time testing with multiple AI models

### Document Generation
- Multi-step wizard for compliance documentation
- Industry-specific templates and frameworks
- PDF generation and version control

## State Management

The application uses React Context API for state management:

- **AuthContext**: User authentication and session management
- **AppContext**: Application-wide state (theme, notifications, etc.)
- **WebSocketContext**: Real-time communication and live updates

## API Integration

The frontend is designed to work with the unified backend API. Currently using mock data for development, but can be easily switched to real API endpoints by updating the service files.

## Styling

- **Tailwind CSS** for utility-first styling
- **Material-UI** for complex components
- **Custom CSS classes** for reusable component styles
- **Dark mode support** (configurable via theme context)

## Development Guidelines

### Component Structure
- Use functional components with hooks
- Implement proper prop validation
- Follow consistent naming conventions
- Keep components focused and reusable

### State Management
- Use Context API for global state
- Implement custom hooks for data fetching
- Handle loading and error states consistently

### Styling
- Use Tailwind utility classes for styling
- Create reusable component variants
- Maintain consistent spacing and typography
- Ensure responsive design across all breakpoints

## Environment Variables

Create a `.env` file in the frontend directory:

```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_APP_NAME=AI Compliance Platform
VITE_APP_VERSION=1.0.0
VITE_ENABLE_ANALYTICS=true
VITE_ENABLE_WEBSOCKETS=true
```

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Contributing

1. Follow the existing code style and conventions
2. Write tests for new features
3. Update documentation as needed
4. Ensure responsive design compatibility
5. Test across different browsers and devices

## License

This project is part of the Unified AI Compliance Platform and is proprietary software.