# AI Rules

## Tech Stack
- React 18 with TypeScript
- React Router for navigation (routes in src/App.tsx)
- Tailwind CSS for styling
- shadcn/ui components for UI elements
- lucide-react icons for icons

## Library Usage Rules
- **UI Components**: Use shadcn/ui components; do not create new UI components from scratch unless absolutely necessary.
- **Styling**: Apply Tailwind CSS classes extensively; avoid custom CSS files.
- **Icons**: Use lucide-react icons; import individually as needed.
- **Routing**: Keep all route definitions in src/App.tsx; do not split routes across multiple files.
- **State Management**: Use React hooks or context; avoid external state management libraries unless required.
- **Dependencies**: Only add new npm packages after explicit approval; prefer built-in features or existing stack.
- **Performance**: Implement lazy loading/code splitting as needed; keep bundle size minimal.
- **Testing**: Do not add testing libraries; focus on core functionality.
- **Eject**: Never eject Create React App; stay within the default setup.