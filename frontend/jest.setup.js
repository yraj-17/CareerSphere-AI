// Extend Jest's expect with @testing-library/jest-dom matchers
// e.g. toBeInTheDocument(), toHaveTextContent(), etc.
import '@testing-library/jest-dom';

// jsdom does not implement scrollIntoView — mock it globally
if (typeof window !== 'undefined') {
  window.HTMLElement.prototype.scrollIntoView = jest.fn();
}
