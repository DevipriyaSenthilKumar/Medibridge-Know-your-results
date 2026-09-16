import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("MediBridge render error:", error, info.componentStack);
  }

  reset = () => this.setState({ error: null });

  render() {
    if (this.state.error) {
      return (
        <div
          role="alert"
          className="mx-auto mt-6 max-w-3xl rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900"
        >
          <h2 className="text-lg font-semibold">Something went wrong</h2>
          <p className="mt-1 text-sm">
            {this.props.fallback || "An unexpected problem occurred while showing this report."}
          </p>
          <pre className="mt-3 overflow-x-auto rounded-lg bg-red-100/60 p-3 text-xs text-red-800">
            {String(this.state.error?.message || this.state.error)}
          </pre>
          <button type="button" onClick={this.reset} className="btn-secondary mt-4">
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}